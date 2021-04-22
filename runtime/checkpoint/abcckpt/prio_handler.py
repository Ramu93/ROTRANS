import logging
from decimal import Decimal
from typing import Any, List, Dict, Optional

from abccore.checkpoint_service import CheckpointService
from abcnet.handlers import AbstractItemHandler
from abcnet.services import ChannelService
from abcnet.structures import Message
from abcnet.timer import SimpleTimer

from abcckpt import ckpt_constants
from abcckpt.ckptItems import CkptItemType, Priority, ValidatorVote
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState, StateTransitionObserver
from abcckpt.pre_checkpoint import PreCheckpoint, PreCkptItemProcessor
from abcckpt.ckpt_creation_state import PreCkptStatus as ps, PreCkptStatus
from abcckpt.sortition import ValidatorProperties, verify_sortition
from abcckpt.vote_cr_handler import VoteCrHandler

logger = logging.getLogger(__name__)


class PriorityHandler(AbstractItemHandler, StateTransitionObserver, PreCkptItemProcessor):
    """
    This handler is for collecting priority objects and voting for the maximum priority seen.
    """

    vote_creator: VoteCrHandler

    def __init__(self, pre_ckpt: PreCheckpoint, ckpt_service: CheckpointService):
        super(PriorityHandler, self).__init__([CkptItemType.PRIORITY], CkptItemsParser())
        self.pc: PreCheckpoint = pre_ckpt
        self.ckpt_service = ckpt_service

        self.max_priority: Optional[Priority] = None

        self.prio_timer: Optional[SimpleTimer] = SimpleTimer(ckpt_constants.CKPT_PRIORITY_RCV_TIMEOUT, start=True)

        self.vote_sent = False

        self.queued_prios = []
        self.verified_prios: Dict[str, Priority] = {}
        self.rejected_prios: List[str] = []

        self.fetch_list = set()
        self.timeout_timers = [
            (self.try_vote, SimpleTimer(ckpt_constants.VOTE_TRY_TIME_OUT)),
            (self.send_request_for_missing, SimpleTimer(1.0)),
            (self.send_content_of_requested, SimpleTimer(1.0))
        ]

    def set_handlers(self, vote_creator: VoteCrHandler):
        self.vote_creator: VoteCrHandler = vote_creator

    def transition(self, votes: List[ValidatorVote], voted_prio_id: str):
        if voted_prio_id is None:
            # PASS majority
            new_state = CkptCreationState.copy(self.pc.state,
                                               next_round=True,
                                               step_status=ps.AGREE_VALIDATOR)
            new_state.voted_chosen_val(None)
            new_state.voted_content_hash(None)
            logger.warning(f"PASS case: State transition to AGREE_VALIDATOR")
            self.pc.state_transition(new_state, votes)
        else:
            if not isinstance(voted_prio_id, str) and voted_prio_id not in self.verified_prios:
                raise Exception(f"Transition is invoked with an invalid priority item: {voted_prio_id}")

            voted_pb_key = self.verified_prios[voted_prio_id].pub_k
            new_state = CkptCreationState.copy(self.pc.state, step_status=ps.AGREE_HASH)
            new_state.voted_chosen_val(voted_pb_key)
            assert new_state.content_hash is None
            self.pc.state_transition(new_state, votes)
            # self.reset_queues()
            logger.info(f"State transition to AGREE_HASH")
            logger.info(f"Voted priority message ID is:{voted_prio_id}")
            logger.info(f"Voted chosen pub key:{voted_pb_key}")



    def handle_state_transition(self, state: CkptCreationState):
        self.reset_queues()



    def reset_queues(self):
        logger.info(f"Clearing priority handler queues")
        self.max_priority: Optional[Priority] = None
        self.vote_sent = False
        self.prio_timer.reset()
        self.queued_prios = []
        self.verified_prios: Dict[str, Priority] = {}
        self.rejected_prios: List[str] = []
        self.fetch_list.clear()

    def verify_validator_vote(self, validator: ValidatorProperties) -> bool:
        """Verifies other validator vote and VRF proof.

            :param validator: validator object received for verification
            """

        # seed verification
        if validator.sortition.seed == self.pc.state.get_current_common_str():
            logger.debug("Valid seed value")

        else:
            logger.warning("Invalid seed received: " + str(validator.sortition.seed) + " calculated seed:" + str(
                self.pc.state.get_current_common_str()))

        return verify_sortition(validator)

    def __check_max_priority(self, priority: Priority,peer_id):

        if self.max_priority is None or priority.is_greater_than(self.max_priority):
            logger.info("Peer: %s current max priority: %s", peer_id,self.max_priority)

            self.max_priority = priority
            if peer_id:
                logger.info("Peer: %s", peer_id)
            logger.info("Found a new max priority: %s", priority)

    def __verify_priority(self, priority: Priority) -> bool:
        """
        Verify the priority message received. Checks if stake value is correct and above participation threshold and
        proceeds to check if votes are valid. If checks are valid, priority message is entered in handled_items and
        returns True
        """
        stake = Decimal(priority.stake)
        item_id = priority.item_qualifier()
        # stake verification
        # logger.debug(f"Verifying stake value: {stake} in prioirty message id: {item_id}")
        stake_list_value = self.ckpt_service.delegated_stake(priority.pub_k)
        if stake == stake_list_value:
            # logger.debug(f"Valid stake value: {stake}")

            if stake > ckpt_constants.CKPT_PARTICIPATION_STAKE_TH:
                logger.debug(f"Checking priority msg: {item_id}")
                if self.verify_validator_vote(priority.get_validator_prop()):
                    self.verified_prios[item_id] = priority
                    return True
                else:
                    logger.debug(f"Invalid votes({priority.votes}) received.")
                    return False
            else:
                logger.debug(f"Participation stake threshold is not met, stake received is : {stake}")
                return False
        else:
            logger.debug(f"Invalid stake received: {stake}")
            logger.debug(f"Calculated stake: {stake_list_value}")
            return False

    def process_prio(self, priority: Priority, peer_id=None):
        if priority.item_qualifier() in self.verified_prios:
            return True
        auth_result = priority.verify_signature()
        item_id = priority.item_qualifier()

        if not auth_result:
            logger.debug(f"Invalid signature for priority msg:{item_id}")
            return
        if self.pc.state == priority.state:
            if self.__verify_priority(priority):
                self.__check_max_priority(priority,peer_id)
            else:
                self.rejected_prios.append(item_id)
                logger.debug(f"Rejected priority message id:{item_id}")
        else:
            if self.pc.state.round + 1 == priority.state.round:
                self.queued_prios.append(priority)
            else:
                logger.debug(f"Rejected priority message id:{item_id}")

    def get_max_priority(self):
        return self.max_priority

    def initialise_prio(self, self_priority: Priority):
        self.max_priority = self_priority

    def check_prio_timeout(self,cs: ChannelService):
        if self.prio_timer is not None and self.prio_timer.check() and not self.vote_sent:
            if self.max_priority is not None:
                # create vote for max priority, PASS vote if no priorities received and has no priority initialised
                logger.info("Voting time: The largest priority seen by peer: %s is %s. ",cs.contact.identifier, self.max_priority)
                self.vote_creator.create_vote(self.max_priority.item_qualifier(), CkptItemType.PRIORITY)
                self.vote_sent = True
            else:
                logger.warning("No priority seen by peer %s in the given timespan. Nothing to vote for so voting pass.",cs.contact.identifier)
                self.vote_creator.create_vote(None, CkptItemType.PRIORITY)
                self.vote_sent = True

    def perform_maintenance(self, cs: ChannelService, force_maintenance=False):
        self.check_state_transition()
        if self.pc.state.step_status == PreCkptStatus.AGREE_VALIDATOR:
            # self.send_request_for_missing(cs)
            for maintenance_method, timer in self.timeout_timers:
                if timer():
                    maintenance_method(cs)

    def try_vote(self, cs):
        if not self.pc.ckpt_creation_timer.check():
            logger.info("Not creating vote on priority as the time for creating a checkpoint has not come yet. "
                        "Remaining wait time: %s", self.pc.ckpt_creation_timer)
            return
        self.check_prio_timeout(cs)

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any):  # items()
        if item_type == CkptItemType.PRIORITY and item_content is not None and isinstance(item_content, Priority) \
                and not self.has_priority(item_content.item_qualifier()):
            self.process_prio(item_content,cs.contact.identifier)

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int,
                              item_qualifier: str):  # checklist()
        if not self.has_priority(item_qualifier):
            self.fetch_list.add((item_type, item_qualifier))

    def send_request_for_missing(self, cs: ChannelService):
        if self.fetch_list:
            cs.broadcast_channel().fetch_items(list(self.fetch_list))
            self.fetch_list.clear()

    def has_priority(self, item_qualifier) -> bool:
        if item_qualifier in self.verified_prios or item_qualifier in self.rejected_prios:
            return True
        return False

    def check_item_exists(self, item_qualifier) -> bool:
        if item_qualifier in self.verified_prios:
            return True
        elif item_qualifier in self.rejected_prios:
            logger.error("Transition is invoked with an invalid priority item")
            return True
        self.fetch_list.add((CkptItemType.PRIORITY, item_qualifier))
        return False

    def has_verified_priority(self, item_qualifier) -> bool:
        # Check before transition call from consens
        if item_qualifier in self.verified_prios:
            return True
        return False
    # def send_new(self, cs: "ChannelService"):
    # def send_checklist(self, cs: "ChannelService"):
    def send_content_of_requested(self, cs: ChannelService):
        for type, item_qualifier in self.fetch_list:
            if item_qualifier in self.verified_prios:
                cs.broadcast_channel().items([self.verified_prios[item_qualifier]])


