import unittest
from unittest.mock import MagicMock

from abcnet import transcriber
from abcnet.nettesthelpers import pseudo_peer, pseude_cs, net_app, MockMsgSender, RecordMsgReceiver
from abcnet.simenv import configure_mocked_network_env
from abcnet.structures import Message, MsgType

from abcckpt.ckptItems import CkptItemType
from abcckpt.prio_cr_handler import PriorityCrHandler
from abcckpt import ckpttesthelpers
from abcckpt.ckpttesthelpers import CheckpointCase1

configure_mocked_network_env()
ckpttesthelpers.inject_ckpt_items_into_oracle()

class SimulatePriorityRound(unittest.TestCase):


    def setUp(self):
        ba = net_app(pseudo_peer("P1"))
        pc = ckpttesthelpers.pseudo_pc()
        prio_handler = ckpttesthelpers.add_prio_app(ba, CheckpointCase1, pc)
        vote_cr_handler = MagicMock()
        prio_handler.set_handlers(vote_cr_handler)
        prio_handler.prio_timer = MagicMock()
        prio_handler.prio_timer.check = MagicMock(return_value=False)  # No voting
        our_contact = ba.cs.contact
        prio_handler.check_state_transition()
        self.pc = pc
        self.ba = ba
        self.prio_handler = prio_handler
        self.vote_cr_handler = vote_cr_handler
        self.our_contact = our_contact

    def test_simu(self):

        prio_owner_1 = PriorityCrHandler.create_prio(self.pc.state, CheckpointCase1.owner1, CheckpointCase1)

        prio_cr = PriorityCrHandler(self.pc, CheckpointCase1,
                                    ckpttesthelpers.AgentSerivceMock([CheckpointCase1.owner1], None))
        prio_cr.create_my_prio()
        prio_owner_1 = prio_cr.priority
        assert prio_owner_1.verify_signature() ==True
        sender = MockMsgSender()
        sender.direct_message(self.our_contact).checklist([prio_owner_1])

        receiver = RecordMsgReceiver()
        receiver.subscribe(self.our_contact)

        self.ba.handle_remaining_messages()
        self.ba.maintain(force_maintenance=True)

        def prio_request_matcher(msg: Message) -> bool:
            if transcriber.parse_message_type(msg) != MsgType.items_request:
                return False
            items = transcriber.parse_item_qualifier(msg)
            for item_type, item_id in items:
                if item_type == CkptItemType.PRIORITY and item_id == prio_owner_1.item_qualifier():
                    return True
            return False

        assert receiver.next_matching_msg(prio_request_matcher) is not None

        sender.direct_message(self.our_contact).items([prio_owner_1])
        self.ba.handle_remaining_messages()


    def tearDown(self) -> None:
        self.ba.close()
