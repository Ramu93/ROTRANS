import unittest

from abcckpt.checkpointservice import CkptService
from tests.testUtil import TestUtility
from abccore.DAG import Checkpoint


class CheckpointServiceTest(unittest.TestCase):

    def test_get_stakesum(self):
        dag = TestUtility().get_manual_tree()
        service = CkptService()
        service.set_checkpoint(dag)
        checkpoint = service.checkpoint
        sum = service.stake_sum()
        self.assertEqual(sum, 150, "Stake sum does not match from the checkpoint.")
