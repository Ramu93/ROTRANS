import logging
from typing import Any, List, Dict, Optional

from abcnet.handlers import AbstractItemHandler
from abcnet.services import ChannelService
from abcnet.structures import Message
from abcnet.timer import SimpleTimer

from abcckpt import ckpt_constants
from abcckpt.ckptItems import CkptItemType, ValidatorVote, CkptHash
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState, StateTransitionObserver
from abcckpt.ckpt_creation_state import PreCkptStatus as ps, PreCkptStatus
from abcckpt.pre_checkpoint import PreCheckpoint, PreCkptItemProcessor
from abcckpt.vote_cr_handler import VoteCrHandler

logger = logging.getLogger(__name__)


class HashHandler(AbstractItemHandler, StateTransitionObserver, PreCkptItemProcessor):
    """
    Class for processing checkpoint proposal hash in step AGREE_HASH in checkpoint creation. OK or PASS votes are
    created after verifying the hash received.
    """
    ckpt_hash: CkptHash
    vote_creator: VoteCrHandler

    def __init__(self, pre_ckpt: PreCheckpoint):
        super(HashHandler, self).__init__([CkptItemType.CKPT_HASH], CkptItemsParser())
        self.pc: PreCheckpoint = pre_ckpt

        self.ckpt_hash: Optional[CkptHash] = None
        self.hash_timer: Optional[SimpleTimer] = None

        self.vote_sent = False

        self.queued_hash: List[CkptHash] = []
        self.queued_votes: Dict[bytes, List[ValidatorVote]] = {}
        self.verified_hash: Dict[str, CkptHash] = {}
        self.rejected_hash: List[bytes] = []
        self.fetch_list = set()
        self.timeout_timers = [
            (self.try_vote, SimpleTimer(4.0)),
            (self.send_request_for_missing, SimpleTimer(4.0)),
            (self.send_content_of_requested, SimpleTimer(2.0))
        ]
    def transition(self, votes: List, voted_hash_id):
        if voted_hash_id is None:
            # PASS majority
            new_state = CkptCreationState.copy(self.pc.state,
                                               next_round=True,
                                               step_status=ps.AGREE_VALIDATOR)
            new_state.voted_chosen_val(None)
            new_state.voted_content_hash(None)
            logger.warning(f"PASS case: State transition to AGREE_VALIDATOR")
            self.pc.state_transition(new_state, votes)
        # If ok is reached:
        else:
            if not isinstance(voted_hash_id, str) and voted_hash_id not in self.verified_hash:
                raise Exception(f"Transition is invoked with an invalid hash item: {voted_hash_id}")

            voted_hash = self.verified_hash[voted_hash_id].ckpt_hash
            new_state = CkptCreationState.copy(self.pc.state, step_status=ps.AGREE_CONTENT)
            assert new_state.chosen_validator is not None
            new_state.voted_content_hash(voted_hash)
            self.pc.state_transition(new_state, votes)
            self.reset_queues()
            logger.info(f"State transition to AGREE_CONTENT")
            logger.info(f"Voted hash ID is:{voted_hash_id}")
            logger.info(f"Voted chosen hash ID:{voted_hash.hex()[:6]}")



    def reset_queues(self):
        logger.info(f"Clearing hash handler queues")
        self.ckpt_hash: Optional[CkptHash] = None
        self.queued_hash: List[CkptHash] = []
        self.queued_votes: Dict[bytes, List[ValidatorVote]] = {}
        self.verified_hash: Dict[str, CkptHash] = {}
        self.rejected_hash: List[bytes] = []
        self.fetch_list = set()
        self.vote_sent = False


    def set_handlers(self, vote_creator: VoteCrHandler):
        self.vote_creator: VoteCrHandler = vote_creator

    def __verify_hash(self, hash):
        sign_pk = hash.signature[0]
        return sign_pk == self.pc.state.chosen_validator

    def process_hash(self, hash: CkptHash):
        if hash.item_qualifier() in self.verified_hash:
            return
        auth_result = hash.verify_signature()
        item_id = hash.item_qualifier()

        if not auth_result:
            logger.debug(f"Invalid signature for hash msg:{item_id}")
            return

        logger.info(f"Procesing hash of checkpoint: {hash.ckpt_hash.hex()[:6]}")
        if self.pc.state == hash.state:
            if self.__verify_hash(hash):
                self.ckpt_hash = hash
                logger.info("Verified hash of checkpoint: %s", hash.ckpt_hash.hex()[:6])
                self.verified_hash[hash.item_qualifier()] = hash
            else:
                self.rejected_hash.append(hash.item_qualifier())
                logger.debug(f"Rejected hash message id:{item_id}")
        else:
            if self.pc.state.round + 1 == hash.state.round:
                self.queued_hash.append(hash)

    def has_timer_run_out(self):
        if self.hash_timer is None:
            return False
        return self.hash_timer.check()

    def check_hash_timeout(self):
        if self.has_timer_run_out() and self.ckpt_hash is not None and not self.vote_sent and len(
                self.verified_hash) == 1:
            # create vote for a hash received and verified
            self.vote_creator.create_vote(self.ckpt_hash.item_qualifier(), CkptItemType.CKPT_HASH)
            self.vote_sent = True

        if not self.vote_sent and (self.has_timer_run_out() or len(self.verified_hash) > 1):
            # create PASS vote if no hash received within timeout or multiple hashes received from chosen validator
            self.vote_creator.create_vote(None, CkptItemType.CKPT_HASH)
            self.vote_sent = True

    def handle_state_transition(self, state: CkptCreationState):
        self.reset_queues()
        if state.step_status == PreCkptStatus.AGREE_HASH:
            self.hash_timer = SimpleTimer(ckpt_constants.PROPOSAL_HASH_RCV_TIME, start=True)

    def perform_maintenance(self, cs: ChannelService, force_maintenance=False):
        self.check_state_transition()
        if self.pc.state.step_status == PreCkptStatus.AGREE_HASH:
            # self.send_request_for_missing(cs)
            for maintenance_method, timer in self.timeout_timers:
                if timer():
                    maintenance_method(cs)

    def try_vote(self, cs):
        self.check_hash_timeout()

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any):  # items()
        if item_type == CkptItemType.CKPT_HASH and item_content is not None and isinstance(item_content, CkptHash) \
                and not self.has_hash(item_content.item_qualifier()):
            self.process_hash(item_content)

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int,
                              item_qualifier: str):  # checklist()
        if not self.has_hash(item_qualifier):
            self.fetch_list.add((item_type, item_qualifier))

    def send_request_for_missing(self, cs: ChannelService):
        if self.fetch_list:
            cs.broadcast_channel().fetch_items(list(self.fetch_list))
            self.fetch_list.clear()

    def has_hash(self, item_qualifier):
        if item_qualifier in self.verified_hash or item_qualifier in self.rejected_hash:
            return True
        return False

    def check_item_exists(self, item_qualifier) -> bool:
        if item_qualifier in self.verified_hash:
            return True
        elif item_qualifier in self.rejected_hash:
            logger.error("Checking hash item in invalid queues, trying to initiate transition an invalid hash item")
            return True
        self.fetch_list.add((CkptItemType.CKPT_HASH, item_qualifier))
        return False

    # def send_new(self, cs: "ChannelService"):
    # def send_checklist(self, cs: "ChannelService"):
    def send_content_of_requested(self, cs: ChannelService):
        for type, item_qualifier in self.fetch_list:
            if item_qualifier in self.verified_hash:
                cs.broadcast_channel().items([self.verified_hash[item_qualifier]])
