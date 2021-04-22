import unittest

from abcnet.transcriber import Transcriber

from abcckpt.ckptItems import CkptItemType, Priority
from abcckpt.prio_cr_handler import PriorityCrHandler
from tests.test_priority import initialize_pc
from abcckpt.vote_cr_handler import VoteCrHandler


class TestVoteCR(unittest.TestCase):
    def test_send_vote(self):
        sk, pkb, skb, stake, common_string, state, ckpt, preckpt, consens = initialize_pc()

        prio_cr = PriorityCrHandler(preckpt)
        if not prio_cr.create_my_prio():
            raise Exception("Priority not created")
        prio: Priority = prio_cr.priority
        vote_cr = VoteCrHandler(preckpt)
        vote_cr.create_vote(prio.item_qualifier(), CkptItemType.PRIORITY)
        for key in vote_cr.votes.keys():
            prio = vote_cr.votes[key]
            prio.add_signature(sk)
            t = Transcriber()
            prio.encode(t)
                # from abcnet.services import ChannelService
                # from abcnet.structures import PeerContactInfo
                # def pseudo_peer(name=None) -> PeerContactInfo:
                #     if name is None:
                #         from uuid import uuid4
                #         name = str(uuid4())
                #     from abcnet.nettesthelpers import rand_bind
                #     return PeerContactInfo(name, None, rand_bind(), rand_bind())

                # cs = ChannelService()
                # vote_cr.send_checklist(cs)
                # msg = None
                # vote_cr.handle_item_request(cs, msg, CkptItemType.PRIORITY, prio.item_qualifier())
                # vote_cr.send_content_of_requested(cs)
