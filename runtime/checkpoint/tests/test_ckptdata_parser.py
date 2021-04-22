import unittest

from abcnet.transcriber import Parser

from abcckpt import ckpttesthelpers
from abccore.network_datastructures import Transcriber

from abcckpt.ckptItems import CkptData, CkptItemType
from abcckpt.ckptParser import CkptItemsParser
from tests.testUtil import TestUtility



class TestCkptdata(unittest.TestCase):
    def test_ckptdata_encoding_decoding(self):
        util = TestUtility()

        ckpt = util.get_sample_checkpoint()

        pc = ckpttesthelpers.pseudo_pc()
        state = pc.state
        ckptdatav1 = CkptData(state,ckpt)

        transcriber = Transcriber()
        ckptdatav1.encode(transcriber)

        parser = Parser(transcriber.msg.parts[0])
        ckptdatav2 = CkptItemsParser().decode_item(CkptItemType.CKPT_DATA, parser)

        self.assertEqual(ckptdatav1._id, ckptdatav2._id)
        self.assertEqual(ckptdatav1.checkpoint_data.total_stake, ckptdatav2.checkpoint_data.total_stake)
        self.assertEqual(ckptdatav1.checkpoint_data.total_coins, ckptdatav2.checkpoint_data.total_coins)


        # verify signature
