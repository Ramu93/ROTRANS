import unittest
from decimal import *

from abcnet.transcriber import Transcriber, Parser
from cryptography.hazmat.primitives import serialization

from abcckpt import fast_vrf
from abcckpt.ckptItems import Priority, CkptItemType
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState
from abcckpt.pre_checkpoint import ValidatorData, PreCheckpoint
from abcckpt.prio_cr_handler import PriorityCrHandler
from abcckpt.prio_handler import PriorityHandler
from abcckpt.sortition import SortitionProperties


class CkptTemp:
    def __init__(self, total_stake):
        self.total_stake = total_stake

    def get_validator_stake(self, pk):
        return self.total_stake


def initialize_pc():
    sk = fast_vrf.gen_key()
    pkb = sk.public_key().public_bytes(encoding=serialization.Encoding.Raw,
                                       format=serialization.PublicFormat.Raw)
    skb = fast_vrf.encode_sec_key(sk)
    stake = Decimal(800)
    common_string = b'12345'
    state = CkptCreationState(common_string)

    ckpt = CkptTemp(stake)
    preckpt = PreCheckpoint(state)
    consens = None
    common_string = state.current_common_str

    return sk, pkb, skb, stake, common_string, state, ckpt, preckpt, consens


def create_priority_obj() -> Priority:
    sk, pkb, skb, stake, common_string, state, ckpt, preckpt, consens = initialize_pc()
    status, proof = fast_vrf.hash_vrf_prove(skb, common_string, True)
    assert status == 'VALID'
    status, sample = fast_vrf.hash_vrf_proof_to_hash(proof, True)
    assert status == 'VALID'
    sort_obj = SortitionProperties.calculate(common_string, skb, stake)
    prio = Priority(state, pkb, stake, proof, sort_obj.votes)
    prio.add_signature(sk)
    return prio


class TestPriorityPR:

    def priority_pr_ver(self,prio:Priority):
        sk, pkb, skb, stake, common_string, state, ckpt, preckpt, consens = initialize_pc()

        # prio=create_priority_obj()
        t = Transcriber()
        prio.encode(t)
        p = Parser(t.msg.parts[0])
        prio_parsed = CkptItemsParser.decode_item(CkptItemType.PRIORITY, p)
        assert prio_parsed == prio
        prio_handler = PriorityHandler(preckpt)
        prio_handler.initialise_prio(prio)
        prio_handler.process_prio(prio)
        assert prio == prio_handler.verified_prios[prio.item_qualifier()]
        print(f"prio votes: {prio_handler.verified_prios[prio.item_qualifier()].votes}")

    def priority_pr_rej(self,prio:Priority):
        sk, pkb, skb, stake, common_string, state, ckpt, preckpt, consens = initialize_pc()

        # prio=create_priority_obj()
        t = Transcriber()
        prio.encode(t)
        prio.votes = 789
        prio_handler = PriorityHandler(preckpt)
        prio_handler.initialise_prio(prio)
        prio_handler.process_prio(prio)
        print(f"prio id: {prio_handler.rejected_prios[0]}")
        assert prio.item_qualifier() == prio_handler.rejected_prios[0]


class TestPriorityCR(unittest.TestCase):
    def test_send_prio(self):
        sk, pkb, skb, stake, common_string, state, ckpt, preckpt, consens = initialize_pc()

        prio_cr = PriorityCrHandler(preckpt)
        if prio_cr.create_my_prio():
            prio = prio_cr.priority
            t = Transcriber()
            prio.encode(t)
            p = Parser(t.msg.parts[0])
            prio_parsed = CkptItemsParser.decode_item(CkptItemType.PRIORITY, p)
            assert prio_parsed == prio
            # from abcnet.services import ChannelService
            # from abcnet.structures import PeerContactInfo
            #
            # def pseudo_peer(name=None) -> PeerContactInfo:
            #     if name is None:
            #         from uuid import uuid4
            #         name = str(uuid4())
            #     from abcnet.nettesthelpers import rand_bind
            #     return PeerContactInfo(name, None, rand_bind(), rand_bind())

            # cs = ChannelService(pseudo_peer())
            # prio_cr.send_checklist(cs)
            # msg = None
            # prio_cr.handle_item_request(cs, msg, CkptItemType.PRIORITY, prio.item_qualifier())
            # prio_cr.send_content_of_requested(cs)

            prio_pr_test=TestPriorityPR()
            prio_pr_test.priority_pr_ver(prio)
            prio_pr_test.priority_pr_rej(prio)
