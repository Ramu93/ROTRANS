import logging
from typing import Any, List, Dict, Optional

from abcckpt import ckpt_constants
from abccore.checkpoint_service import CheckpointService
from abcnet.handlers import AbstractItemHandler
from abcnet.services import ChannelService
from abcnet.structures import Message
from abcnet.timer import SimpleTimer
from abcckpt.ckptItems import CkptItemType, ValidatorVote, CkptHash, CkptData
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState, StateTransitionObserver
from abcckpt.ckpt_creation_state import PreCkptStatus as ps, PreCkptStatus
from abcckpt.ckpt_syncronizer import CkptSync
from abcckpt.ckptproposal import PostCheckpoint
from abcckpt.pre_checkpoint import PreCheckpoint, PreCkptItemProcessor, AgentService
from abcckpt.vote_cr_handler import VoteCrHandler

logger = logging.getLogger(__name__)


class ContentHandler(AbstractItemHandler, StateTransitionObserver, PreCkptItemProcessor):
    """
    Class for processing checkpoint proposal content in step AGREE_CONTENT in checkpoint creation. OK or PASS votes are
    created after verifying the proposal received.
    """
    ckpt_hash: CkptHash
    vote_creator: VoteCrHandler
    ckpt_sync: CkptSync

    def __init__(self, pre_ckpt: PreCheckpoint, agent_service: AgentService, ckpt_service: CheckpointService):
        super(ContentHandler, self).__init__([CkptItemType.CKPT_DATA], CkptItemsParser())
        self.pc: PreCheckpoint = pre_ckpt
        self.agent_service = agent_service
        self.ckpt_service = ckpt_service

        self.ckpt_hash: Optional[CkptHash] = None
        self.content_timer: Optional[SimpleTimer] = None
        self.vote_sent = False

        self.pending_content_timer: Optional[SimpleTimer] = None
        self.finalzd_content: Dict[str, CkptData] = {}

        self.queued_content: List[CkptData] = []
        self.queued_votes: Dict[bytes, List[ValidatorVote]] = {}
        self.verified_content: Dict[str, CkptData] = {}
        self.rejected_content: List[bytes] = []
        self.fetch_list = set()
        self.timeout_timers = [
            (self.try_vote, SimpleTimer(4.0)),
            (self.send_request_for_missing, SimpleTimer(1.0)),
            (self.send_content_of_requested, SimpleTimer(1.0))

        ]

    def transition(self, votes: List, voted_content_hash_id):
        if voted_content_hash_id is None:
            # PASS majority
            new_state = CkptCreationState.copy(self.pc.state, next_round=True)
            new_state.voted_chosen_val(None)
            new_state.voted_content_hash(None)
            new_state.step_status = PreCkptStatus.AGREE_VALIDATOR
            logger.warning(f"PASS case: State transition to AGREE_VALIDATOR")
            self.pc.state_transition(new_state, votes)

        # If ok is reached:
        else:
            if not isinstance(voted_content_hash_id, str) and voted_content_hash_id not in self.finalzd_content:
                raise Exception(f"Transition is invoked with an invalid content item: {voted_content_hash_id}")

            ckpt = self.finalzd_content[voted_content_hash_id]
            # Inject the new checkpoint into the agent:
            # self.agent_service.inject_checkpoint(ckpt.checkpoint_data)
            # TODO add votes check to ckpt sync handler
            self.ckpt_sync.update_ckpt(ckpt.checkpoint_data, external=True)
            voted_content_hash = ckpt.get_ckpt_hash()

            self.reset_queues()
            logger.info(f"AGREE CONTENT round completed. AGREE_VALIDATOR state set ")
            logger.info(f"Voted content message ID is:{voted_content_hash_id}")
            logger.info(f"Voted checkpoint hash:{voted_content_hash.hex()[:6]}")


    def reset_queues(self):
        logger.info(f"Clearing content handler queues")
        self.ckpt_hash: Optional[CkptHash] = None
        self.queued_content = []
        self.queued_votes: Dict[bytes, List[ValidatorVote]] = {}
        self.verified_content: Dict[str, CkptData] = {}
        self.finalzd_content: Dict[str, CkptData] = {}
        self.fetch_list.clear()
        self.vote_sent = False


    def set_handlers(self, vote_creator: VoteCrHandler, ckpt_sync: CkptSync):
        self.vote_creator: VoteCrHandler = vote_creator
        self.ckpt_sync = ckpt_sync


    def process_content(self, content: CkptData):
        if content.item_qualifier() in self.verified_content:
            return
        auth_result = content.verify_signature()
        item_id = content.item_qualifier()
        if not auth_result:
            logger.warning(f"Invalid signature for hash msg:{item_id}")
            return

        if self.pc.state != content.state:
            logger.warning("Rejected content because of wrong state %s != %s", self.pc.state, content.state)
            return

        if self.pc.state.content_hash != content.ckpt_hash:
            logger.warning("Rejected content because its hash %s is not the same as the chosen hash: %s",
                           content.ckpt_hash.hex(), self.pc.state.content_hash.hex())
            return

        sign_pk = content.signature[0]
        if sign_pk != self.pc.state.chosen_validator:
            logger.warning("Rejected content because it is not signed by the chosen validator: %s"
                           " but it is instead signed by %s.",
                           self.pc.state.chosen_validator.hex(), sign_pk.hex())
            return

        self.verified_content[content.item_qualifier()] = content
        self.pending_content_timer = SimpleTimer(ckpt_constants.PROPOSAL_TXNS_RCV_TIME, start=True)
        logger.info("Received checkpoint content with the expected hash: %s", content.ckpt_hash.hex()[:6])
        return


    def has_timer_run_out(self):
        if self.content_timer is None:
            return False
        return self.content_timer.check()

    def create_pass_vote(self):
        self.vote_creator.create_vote(None, CkptItemType.CKPT_DATA)
        self.vote_sent = True

    def try_vote(self, cs):
        self.process_verified_content()
        self.check_content_timeout()

    def process_verified_content(self):
        if len(self.verified_content) == 1 and not self.vote_sent:
            content: CkptData = next(iter(self.verified_content.values()))
            if not self.pending_content_timer.check():
                content_check, status = self.__verify_content(content)
                if status == 'PENDING':
                    logger.info("Checkpoint content verification is pending, hash: %s", content.ckpt_hash.hex()[:6])
                    return
                if content_check:
                    self.finalzd_content[content.item_qualifier()] = content
                    logger.info("Finalized checkpoint content with the expected hash: %s, content ID:%s", content.ckpt_hash.hex()[:6], content.item_qualifier()[:6])
                elif not content_check:
                    logger.warning("Invalid content, rejecting content ID : %s", content.item_qualifier())
                    # PASS vote if content from chosen validator is invalid
                    self.create_pass_vote()
            else:
                logger.warning("Pending txns check timedout, rejecting content ID: %s",content.item_qualifier())
                #PASS vote if content from chosen validator could not be validated within timer for checking pending txns
                self.create_pass_vote()

    def __verify_content(self, content):
        local_dag = self.agent_service.get_DAG()
        ckpt_data = content.checkpoint_data
        content_check, status = PostCheckpoint.checkpoint_verify(local_dag, ckpt_data, self.ckpt_service,
                                                                 self.agent_service)
        return content_check, status

    def check_content_timeout(self):
        if not self.vote_sent and len(self.finalzd_content) == 1:
            # create vote for hash of content received and verified
            content: CkptData = next(iter(self.verified_content.values()))
            self.vote_creator.create_vote(content.item_qualifier(), CkptItemType.CKPT_DATA)
            self.vote_sent = True
        # if not self.vote_sent and (self.has_timer_run_out() or len(self.verified_content) > 1):
        if not self.vote_sent:
            # create PASS vote if no content received within timeout or multiple contents received from chosen validator
            if self.has_timer_run_out():
                logger.info(f"PASS vote created as no content received within timeout")
                self.create_pass_vote()
            elif len(self.verified_content) > 1:
                logger.info(f"PASS vote creates as multiple contents received from chosen validator")
                self.create_pass_vote()

    def handle_state_transition(self, state: CkptCreationState):
        self.reset_queues()
        if state.step_status == PreCkptStatus.AGREE_CONTENT:
            self.content_timer = SimpleTimer(ckpt_constants.CKPT_PROPOSAL_RCV_TIMEOUT, start=True)

    def perform_maintenance(self, cs: ChannelService, force_maintenance=False):
        self.check_state_transition()
        if self.pc.state.step_status == PreCkptStatus.AGREE_CONTENT:
            # self.send_request_for_missing(cs)
            for maintenance_method, timer in self.timeout_timers:
                if timer():
                    maintenance_method(cs)

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any):  # items()
        if item_type == CkptItemType.CKPT_DATA and item_content is not None and isinstance(item_content, CkptData) \
                and not self.has_content(item_content.item_qualifier()):
            self.process_content(item_content)

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int,
                              item_qualifier: str):  # checklist()
        if not self.has_content(item_qualifier):
            self.fetch_list.add((item_type, item_qualifier))

    def send_request_for_missing(self, cs: ChannelService):
        if self.fetch_list:
            cs.broadcast_channel().fetch_items(list(self.fetch_list))
            self.fetch_list.clear()

    def has_content(self, item_qualifier):
        if item_qualifier in self.verified_content or item_qualifier in self.rejected_content or item_qualifier in self.finalzd_content:
            return True
        return False

    def check_item_exists(self, item_qualifier) -> bool:
        if item_qualifier in self.finalzd_content:
            return True
        elif item_qualifier in self.rejected_content or item_qualifier in self.verified_content:
            logger.error("Checking content item in invalid queues, trying to initiate transition an invalid content item")
            return True
        self.fetch_list.add((CkptItemType.CKPT_DATA, item_qualifier))
        return False

    def send_content_of_requested(self, cs: ChannelService):
        for type, item_qualifier in self.fetch_list:
            if item_qualifier in self.verified_content:
                cs.broadcast_channel().items([self.verified_content[item_qualifier]])
