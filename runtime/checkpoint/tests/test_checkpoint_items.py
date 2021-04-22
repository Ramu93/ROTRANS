import unittest

from abcckpt import ckpttesthelpers
from tests.testUtil import TestUtility
from abcckpt.ckptItems import CkptData


class TestCkptItems(unittest.TestCase):
    def test_item_creation(self):
        util = TestUtility()
        pc = ckpttesthelpers.pseudo_pc()
        state = pc.state
        ckpt_net = CkptData(state, util.get_sample_checkpoint())
