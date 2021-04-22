import unittest
from unittest.mock import MagicMock

from abcnet import transcriber
from abcnet.nettesthelpers import pseudo_peer, net_app, MockMsgSender, RecordMsgReceiver
from abcnet.simenv import configure_mocked_network_env
from abcnet.structures import Message, MsgType

from abcckpt.ckptItems import CkptItemType, CkptHash
from abcckpt.ckpt_creation_state import PreCkptStatus
from abcckpt import ckpttesthelpers
from abcckpt.ckpttesthelpers import CheckpointCase1

configure_mocked_network_env()
ckpttesthelpers.inject_ckpt_items_into_oracle()

class SimulatePriorityRound(unittest.TestCase):


    def setUp(self):
        ba = net_app(pseudo_peer("P1"))
        pc = ckpttesthelpers.pseudo_pc()
        hash_handler = ckpttesthelpers.add_hash_app(ba, pc)
        vote_cr_handler = MagicMock()
        hash_handler.set_handlers(vote_cr_handler)
        hash_handler.hash_timer = MagicMock()
        hash_handler.hash_timer.check = MagicMock(return_value=False)  # No voting
        our_contact = ba.cs.contact
        hash_handler.check_state_transition()
        self.pc = pc
        self.ba = ba
        self.hash_handler = hash_handler
        self.vote_cr_handler = vote_cr_handler
        self.our_contact = our_contact

    def test_simu(self):

        # prio_owner_1 = PriorityCrHandler.create_prio(self.pc.state, CheckpointCase1.owner1, CheckpointCase1)

        self.pc.state.voted_chosen_val(CheckpointCase1.owner1_pub_key)
        self.pc.state.step_status=PreCkptStatus.AGREE_HASH

        ckpt_hash=CkptHash(self.pc.state, b'dummybytes')
        ckpt_hash.add_signature(CheckpointCase1.owner1)
        # self.hash_handler.process_hash(ckpt_hash)

        hash_owner_1 = ckpt_hash
        assert hash_owner_1.verify_signature() ==True
        sender = MockMsgSender()
        sender.direct_message(self.our_contact).checklist([hash_owner_1])

        receiver = RecordMsgReceiver()
        receiver.subscribe(self.our_contact)

        self.ba.handle_remaining_messages()
        self.ba.maintain(force_maintenance=True)

        def prio_request_matcher(msg: Message) -> bool:
            if transcriber.parse_message_type(msg) != MsgType.items_request:
                return False
            items = transcriber.parse_item_qualifier(msg)
            for item_type, item_id in items:
                if item_type == CkptItemType.CKPT_HASH and item_id == hash_owner_1.item_qualifier():
                    return True
            return False

        assert receiver.next_matching_msg(prio_request_matcher) is not None

        sender.direct_message(self.our_contact).items([hash_owner_1])
        self.ba.handle_remaining_messages()


    def tearDown(self) -> None:
        self.ba.close()
