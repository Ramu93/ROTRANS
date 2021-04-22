import logging

from abccore.checkpoint_service import CheckpointService
from abcnet.handlers import AbstractItemHandler
from abcnet.services import ChannelService
from abcnet.structures import Message
from abcnet.timer import SimpleTimer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abcckpt import fast_vrf
from abcckpt.ckptItems import CkptItemType, Priority
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import StateTransitionObserver, CkptCreationState, PreCkptStatus
from abcckpt.pre_checkpoint import PreCheckpoint, AgentService
from abcckpt.ckpt_creation_state import PreCkptStatus as ps
from abcckpt.prio_handler import PriorityHandler
from abcckpt.sortition import SortitionProperties

logger = logging.getLogger(__name__)


class PriorityCrHandler(AbstractItemHandler, StateTransitionObserver):
    """
    Item creator Class for priority in step AGREE_VALIDATOR in checkpoint creation, used for choosing a validator for next step.
    """
    priority_handler: "PriorityHandler"

    def __init__(self, pre_ckpt: PreCheckpoint, ckpt_service: CheckpointService, agent_service: AgentService):
        super(PriorityCrHandler, self).__init__([CkptItemType.PRIORITY], CkptItemsParser())
        # Global Set of Data
        self.pc: PreCheckpoint = pre_ckpt
        self.ckpt_service: CheckpointService = ckpt_service
        self.agent_service: AgentService = agent_service

        self.priority: Priority = None

        self.requested_items = set()
        self.priority_created_flag = False
        self.timeout_timers = [
            (self.send_checklist, SimpleTimer(4.5)),
            (self.send_content_of_requested, SimpleTimer(1.5)),
            (self.requeue_current_priority, SimpleTimer(.5))
        ]

    def set_handlers(self, priority_handler: "PriorityHandler"):
        if priority_handler is None:
            raise ValueError("Priority handler is None.")
        self.priority_handler = priority_handler

    @staticmethod
    def create_prio(state: CkptCreationState, skey: Ed25519PrivateKey, ckpt_service: CheckpointService) -> Priority:
        pkb = fast_vrf.encode_pub_key(skey.public_key())
        stake = ckpt_service.delegated_stake(pkb)
        sort_obj = SortitionProperties.calculate(state.get_current_common_str(), skey, stake)
        return Priority(state, pkb, stake, sort_obj.proof, sort_obj.votes)

    def handle_state_transition(self, state: CkptCreationState):
        # State transition performed
        if state.step_status == PreCkptStatus.AGREE_VALIDATOR:
            self.create_my_prio()

    def create_my_prio(self, peer_id=None):
        self.priority = None
        for skey in self.agent_service.get_keypairs():
            prio = self.create_prio(self.pc.state, skey, self.ckpt_service)
            if self.priority != prio:
                if self.priority is None or prio.is_greater_than(self.priority):
                    self.priority = prio
                    self.priority.add_signature(skey)

        if self.priority is not None:
            logger.info("Created priority for peer %s: %s", peer_id, self.priority)
        else:
            logger.warning("Couldn't create priority for peer: %s", peer_id)

    def perform_maintenance(self, cs: ChannelService,force_maintenance=False):
        self.check_state_transition()
        if self.pc.state.step_status == ps.AGREE_VALIDATOR:
            for maintenance_method, timer in self.timeout_timers:
                if timer():
                    maintenance_method(cs)

    def send_checklist(self, cs: "ChannelService"):
        if self.priority:
            checklist = {self.priority.item_qualifier(): self.priority}
            cs.broadcast_channel().checklist(list(checklist.values()))

    def send_content_of_requested(self, cs: ChannelService):
        for type, item_qualifier in self.requested_items:
            if self.priority is not None:
                if item_qualifier == self.priority.item_qualifier():
                    cs.broadcast_channel().items([self.priority])

    def requeue_current_priority(self, cs: ChannelService):
        if self.priority is not None:
            self.priority_handler.process_prio(self.priority, cs.contact.identifier)

    def handle_item_request(self, cs: "ChannelService", msg: Message, item_type: int,
                            item_qualifier: str):  # fetch_items()
        self.requested_items.add((item_type, item_qualifier))


