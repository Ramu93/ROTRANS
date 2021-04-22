import unittest
from tests.testUtil import TestUtility
from abcckpt.ckptproposal import Ckpt_Proposal
from abcckpt.checkpointservice import CheckpointService
class Test_Checkpoint(unittest.TestCase):
    """
    This test only works when abc is imported as submodule.
    """

    def test_get_txn_list(self):
        testutil=TestUtility()
        ckpt=testutil.get_gen_checkpoint()
        txn_list=ckpt.get_transaction_list()
        print(txn_list)