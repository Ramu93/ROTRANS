import logging
from typing import Tuple, Optional

from abccore.checkpoint_service import CheckpointService
from abccore.prefix_tree import Tree
from abcnet.handlers import AbstractItemHandler
from abcnet.services import ChannelService
from abcnet.structures import Message
from abcnet.timer import SimpleTimer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abcckpt import fast_vrf
from abcckpt.ckptItems import CkptItemType, CkptData, CkptHash
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState, StateTransitionObserver, PreCkptStatus
from abcckpt.ckpt_creation_state import PreCkptStatus as ps
from abcckpt.ckptproposal import Ckpt_Proposal
from abcckpt.pre_checkpoint import PreCheckpoint, AgentService
from abcckpt.hash_handler import HashHandler
from abcckpt.content_handler import ContentHandler

logger = logging.getLogger(__name__)


class CheckpointContentCreator:
    """
    Class for creating the checkpoint proposal, used by the chosen validator once AGREE_HASH state is reached.
    """
    @staticmethod
    def create_ckpt(state: CkptCreationState, dagtree: Tree, chosen_pbkey: bytes,
                    ckpt_service: CheckpointService) -> Optional[CkptData]:
        proposal_state = CkptCreationState.copy(state, step_status=ps.AGREE_CONTENT)
        ack_len = 0
        height = ckpt_service.get_height() + 1
        miner: bytes = chosen_pbkey
        try:
            ckpt_prop = Ckpt_Proposal(dagtree, proposal_state.last_common_string, height, ack_len, miner, ckpt_service)

        except Exception as e:
            logger.error(f"Exception in proposal creation.", exc_info=True)
            return None
        proposal_state.voted_content_hash(ckpt_prop.Ckpt.id)
        ckpt_data = CkptData(proposal_state, ckpt_prop.Ckpt)
        return ckpt_data



class ProposalCrHandler(AbstractItemHandler, StateTransitionObserver):
    """
    Item creator class for hash and proposal in step AGREE_HASH, proposal content is broadcasted only after AGREE_CONTENT state is reached.
    """
    def __init__(self, pre_ckpt: PreCheckpoint, agent_service: AgentService, ckpt_service: CheckpointService):
        super(ProposalCrHandler, self).__init__([CkptItemType.CKPT_HASH, CkptItemType.CKPT_DATA],
                                                CkptItemsParser())
        # Global Set of Data
        self.pc: PreCheckpoint = pre_ckpt
        self.agent_service: AgentService = agent_service
        self.ckpt_service = ckpt_service

        self.hash_handler: Optional[HashHandler] = None
        self.content_handler: Optional[ContentHandler] = None
        self.creator = CheckpointContentCreator()

        self.proposal: Optional[CkptData] = None
        self.ckpt_hash: Optional[CkptHash] = None

        self.is_chosen_validator_ = False
        self.chosen_key: Optional[Ed25519PrivateKey] = None
        self.chosen_pb_key: Optional[bytes] = None
        self.checklist = {}
        self.requested_items = set()

        self.timeout_timers = [
            (self.send_checklist, SimpleTimer(2.0)),
            (self.send_content_of_requested, SimpleTimer(1.0))
        ]

    def set_handler(self, hash_handler, content_handler):
        self.hash_handler = hash_handler
        self.content_handler = content_handler

    def create_proposal(self, peer_id=None) -> bool:

        self.proposal = self.creator.create_ckpt(self.pc.state, self.agent_service.get_DAG(), self.chosen_pb_key,
                                                 self.ckpt_service)
        if self.proposal is None:
            logger.info("Couldn't create proposal object..")
            return False
        self.ckpt_hash = CkptHash(self.pc.state, self.proposal.get_ckpt_hash())
        if self.proposal is not None and self.ckpt_hash is not None:
            logger.info("%s created checkpoint proposal with hash %s.", peer_id, self.proposal.ckpt_hash.hex()[:5])
            self.proposal.add_signature(self.chosen_key)
            self.ckpt_hash.add_signature(self.chosen_key)
            return True
        else:
            return False
    def reset_values(self):
        logger.info(f"Clear proposal creation calculations")
        self.is_chosen_validator_ = False
        self.ckpt_hash = None
        self.proposal = None
        self.checklist.clear()
        self.chosen_key = None
        self.chosen_pb_key = None

    def is_chosen_validator(self) -> Tuple[bool, Optional[Ed25519PrivateKey]]:
        chosen_validator = self.pc.state.chosen_validator
        if chosen_validator is None:
            return False, None
        for sk in self.agent_service.get_keypairs():
            pb_key = fast_vrf.encode_pub_key(sk.public_key())
            if pb_key == chosen_validator:
                return True, sk
        return False, None

    def handle_state_transition(self, state):
        self.is_chosen_validator_, chosen_key = self.is_chosen_validator()
        self.chosen_key = chosen_key
        if self.is_chosen_validator_:
            self.chosen_pb_key = fast_vrf.encode_pub_key(self.chosen_key.public_key())
            logger.info("I was selected as chosen validator to propose the next checkpoint.")
        if self.pc.state.step_status == ps.AGREE_CONTENT and self.is_chosen_validator_:
            self.checklist[self.proposal.item_qualifier()] = self.proposal
        if not self.is_chosen_validator_:
            self.proposal = None
            self.ckpt_hash = None
            self.checklist.clear()


    def perform_maintenance(self, cs: ChannelService, force_maintenance=False):
        self.check_state_transition()
        if self.pc.state.step_status != ps.AGREE_VALIDATOR and self.is_chosen_validator_:
            if self.proposal is None:
                logger.info(f"Going to create checkpoint proposal")
                proposal_created = self.create_proposal(cs.contact.identifier)
                if not proposal_created:
                    logger.error(f"Unable to create proposal")
                    # TODO: handle case
                else:
                    self.checklist[self.ckpt_hash.item_qualifier()] = self.ckpt_hash

            # self.send_checklist(cs)
            # self.send_content_of_requested(cs)
            for maintenance_method, timer in self.timeout_timers:
                if timer():
                    maintenance_method(cs)

    def send_checklist(self, cs: "ChannelService"):
        if self.checklist:
            cs.broadcast_channel().checklist(list(self.checklist.values()))

    def send_content_of_requested(self, cs: ChannelService):
        if self.pc.state.step_status == PreCkptStatus.AGREE_HASH:
            if self.ckpt_hash is not None:
                self.hash_handler.process_hash(self.ckpt_hash)
        elif self.pc.state.step_status == PreCkptStatus.AGREE_CONTENT:
            if self.proposal is not None:
                self.content_handler.process_content(self.proposal)

        for type, item_qualifier in self.requested_items:
            checklist = {}
            if self.ckpt_hash is not None:
                if item_qualifier == self.ckpt_hash.item_qualifier():
                    checklist[self.ckpt_hash.item_qualifier()] = self.ckpt_hash
            if self.proposal is not None:
                if item_qualifier == self.proposal.item_qualifier():
                    checklist.update({self.proposal.item_qualifier(): self.proposal})
            cs.broadcast_channel().items(list(checklist.values()))
        self.requested_items.clear()

    def handle_item_request(self, cs: "ChannelService", msg: Message, item_type: int,
                            item_qualifier: str):  # fetch_items()
        self.requested_items.add((item_type, item_qualifier))
