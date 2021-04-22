from decimal import Decimal
from typing import List, Dict, Callable, Any, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abcckpt import ckptParser
from abcckpt import fast_vrf
from abccore.DAG import Wallet
from abccore.checkpoint_service import CheckpointService
from abccore.prefix_tree import Tree
from abcnet import transcriber
from abcnet.services import BaseApp
from abcnet.structures import MsgType, Message
from abcckpt.ckptItems import CkptItemType, Priority, CkptHash, CkptData, ValidatorVote, MajorityVotes
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState
from abcckpt.content_handler import ContentHandler
from abcckpt.hash_handler import HashHandler
from abcckpt.pre_checkpoint import PreCheckpoint, AgentService, PreCkptItemProcessor
from abcckpt.prio_cr_handler import PriorityCrHandler
from abcckpt.prio_handler import PriorityHandler
from abcckpt.proposal_cr_handler import ProposalCrHandler
from abcckpt.stab_abc_consens import StabVotingHandler
from abcckpt.vote_cr_handler import VoteCrHandler


def inject_ckpt_items_into_oracle():
    from abcnet import settings
    type_oracle = settings.NetStatSettings.item_type_oracle()
    type_oracle.update({
        CkptItemType.PRIORITY: "PRIO",
        CkptItemType.CKPT_HASH: "CKPT_HASH",
        CkptItemType.VALVOTE: "VOTE",
        CkptItemType.CKPT_DATA: "CKPT_DATA",
        CkptItemType.MAJVOTES: "MAJORITY_VOTES"
    })
    packer_oracle = settings.NetStatSettings.item_packer_oracle()

    def pack_state(state: CkptCreationState) -> Dict:
        return {
            "last_common_string": state.last_common_string.hex(),
            "round": state.round,
            "step_status": state.step_status.name,
            "chosen_validator": state.chosen_validator.hex() if state.chosen_validator is not None else 'Not set',
            "content_hash": state.content_hash.hex() if state.content_hash is not None else 'Not set',
            "current_common_str": state.current_common_str.hex()
        }

    def pack_priority(p: Priority) -> Dict:
        return {
            "state": pack_state(p.state),
            "pub_k": p.pub_k.hex(),
            "stake": str(p.stake),
            "proof": p.proof.hex()[:15] + "...",
            "votes": p.votes
        }

    def pack_hash(p: CkptHash) -> Dict:
        return {
            "state": pack_state(p.state),
            "checkpoint hash": p.ckpt_hash.hex(),
        }

    def pack_content(p: CkptData) -> Dict:
        return {
            "state": pack_state(p.state),
            "checkpoint hash": p.ckpt_hash.hex(),
            # "total_stake": str(p.ckpt_total_stake),
            # "total coins": p.ckpt_total_coins,
        }

    def pack_vote(p: ValidatorVote) -> Dict:
        return {
            "state": pack_state(p.state),
            "voted item type": p.voted_item_type,
            "voted item id": p.voted_item_id,
        }

    def pack_majority_vote(p: MajorityVotes) -> Dict:
        return {
            "state": pack_state(p.state),
            "voted item id": p.voted_item_qualifier
            # number of votes?
        }

    parser = CkptItemsParser()
    packer_oracle.update({
        CkptItemType.PRIORITY: lambda b:
        pack_priority(parser.decode_item_bytes(CkptItemType.PRIORITY, b)),
    })
    packer_oracle.update({
        CkptItemType.CKPT_HASH: lambda b:
        pack_hash(parser.decode_item_bytes(CkptItemType.CKPT_HASH, b)),
    })
    packer_oracle.update({
        CkptItemType.CKPT_DATA: lambda b:
        pack_content(parser.decode_item_bytes(CkptItemType.CKPT_DATA, b)),
    })
    packer_oracle.update({
        CkptItemType.MAJVOTES: lambda b:
        pack_majority_vote(parser.decode_item_bytes(CkptItemType.MAJVOTES, b)),
    })
    packer_oracle.update({
        CkptItemType.VALVOTE: lambda b:
        pack_vote(parser.decode_item_bytes(CkptItemType.VALVOTE, b)),
    })


def pseudo_pc(common_str: bytes = None) -> PreCheckpoint:
    if common_str is None:
        common_str = b'test_common_str'
    return PreCheckpoint(CkptCreationState(common_str))


def add_prio_app(ba: BaseApp, ckpt_service: CheckpointService, pc: PreCheckpoint) \
        -> PriorityHandler:
    if pc is None:
        pc = pseudo_pc()
    ph = PriorityHandler(pre_ckpt=pc, ckpt_service=ckpt_service)
    ba.register_app_layer("prio_handler", ph)
    return ph


def add_hash_app(ba: BaseApp, pc: PreCheckpoint) \
        -> HashHandler:
    if pc is None:
        pc = pseudo_pc()
    ph = HashHandler(pre_ckpt=pc)
    ba.register_app_layer("hash_handler", ph)
    return ph


def add_stab_vote_handler_app(ba: BaseApp, ckpt_service: CheckpointService, pc: PreCheckpoint,
                              processors: List[PreCkptItemProcessor] = None) \
        -> StabVotingHandler:
    svh = StabVotingHandler(pc, ckpt_service)
    if processors is not None:
        svh.set_handlers(*processors)
    ba.register_app_layer("stab_vote_handler", svh)
    return svh


def ckpt_protocol_app(ba: BaseApp, ckpt_service: CheckpointService, agent: AgentService, pc: PreCheckpoint):
    ph = add_prio_app(ba, ckpt_service, pc)
    hh = add_hash_app(ba, pc)
    ch = ContentHandler(pc, agent, ckpt_service)
    ba.register_app_layer("content_handler", ch)

    svh = add_stab_vote_handler_app(ba, ckpt_service, pc)

    priority_creator = PriorityCrHandler(pc, ckpt_service, agent)
    ba.register_app_layer("priority_creator", priority_creator)
    vote_creator = VoteCrHandler(pc, agent)
    ba.register_app_layer("vote_creator", vote_creator)
    proposal_creator = ProposalCrHandler(pc, agent, ckpt_service)
    ba.register_app_layer("proposal_creator", proposal_creator)

    ph.set_handlers(vote_creator)
    hh.set_handlers(vote_creator)
    ch.set_handlers(vote_creator)
    svh.set_handlers(ph, hh, ch)

    priority_creator.set_handlers(ph)
    vote_creator.set_handlers(svh)
    proposal_creator.set_handler(hh, ch)


class CheckpointServiceTestCase(CheckpointService):
    private_keys: List[Ed25519PrivateKey] = []

    pub_keys: List[bytes] = []

    stake_distribution: Dict[bytes, Decimal] = {}

    owner1: Ed25519PrivateKey
    owner1_pub_key: bytes

    @classmethod
    def stake_sum(cls) -> Decimal:
        return sum(cls.stake_distribution.values())

    @classmethod
    def delegated_stake(cls, pb_key) -> Decimal:
        return cls.stake_distribution.get(pb_key, Decimal(0.0))

    @classmethod
    def owned_wallets(cls, pb_key) -> List[Wallet]:
        raise Exception("This method should not be used in the checkpoint creation tests.")


class CheckpointCase1(CheckpointServiceTestCase):
    validator_count = 10

    private_keys: List[Ed25519PrivateKey] = []

    pub_keys: List[bytes] = []

    stake_distribution: Dict[bytes, Decimal] = {}

    owner1: Ed25519PrivateKey

    owner1_pub_key: bytes

    @classmethod
    def init_case(cls):
        for i in range(cls.validator_count):
            private_key = fast_vrf.gen_key(i)
            pub_key = fast_vrf.encode_pub_key(private_key.public_key())
            cls.private_keys.append(private_key)
            cls.pub_keys.append(fast_vrf.encode_pub_key(private_key.public_key()))
            cls.stake_distribution[pub_key] = Decimal(100.0)

            del private_key
            del pub_key

        cls.owner1: Ed25519PrivateKey = fast_vrf.gen_key("Owner_1")
        cls.owner1_pub_key: bytes = fast_vrf.encode_pub_key(cls.owner1.public_key())
        cls.stake_distribution[cls.owner1_pub_key] = Decimal(50.0)

    @classmethod
    def get_ckpt_id(cls):
        return b'test_common_str'

    @classmethod
    def get_height(cls):
        return 0

    @classmethod
    def get_ckpt_origin(self) -> bytes:
        return b'test_common_str'


CheckpointCase1.init_case()
CheckpointCase1: CheckpointService


class AgentSerivceMock(AgentService):

    def __init__(self, pv_keys: List[Ed25519PrivateKey], dag):
        self.pv_keys = pv_keys
        self.dag = dag

    def get_keypairs(self) -> List[Ed25519PrivateKey]:
        return self.pv_keys

    def get_DAG(self) -> Tree:
        return self.dag


parser = ckptParser.CkptItemsParser()


def ckptitems_matcher(filter_msg_type: MsgType, filter_item_type: CkptItemType):
    assert filter_msg_type in [MsgType.items_content, MsgType.items_request,
                               MsgType.items_checklist, MsgType.items_notfound]

    def annotation(items_matcher: Callable[[List[Union[str, Any]]], Any]):
        def new_matcher(msg: Message):
            m_type = transcriber.parse_message_type(msg)
            if m_type != filter_msg_type:
                return False

            if filter_msg_type == MsgType.items_content:
                items = transcriber.parse_item_contents(msg)
            else:
                items = transcriber.parse_item_qualifier(msg)
            filtered_items = list(map(lambda i: i[1], filter(lambda i: i[0] == filter_item_type, items)))
            if not filtered_items:
                return False
            if filter_msg_type == MsgType.items_content:
                filtered_items = [parser.decode_item_bytes(filter_item_type, i) for i in filtered_items]

            return items_matcher(filtered_items)

        return new_matcher

    return annotation
