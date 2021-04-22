import copy
import unittest
from decimal import Decimal
from typing import List

from abccore.DAG import Wallet, Checkpoint, State, Transaction, Acknowledge
from abccore.prefix_tree import Tree

from abcckpt.checkpointservice import CkptService
from abcckpt.ckptproposal import Ckpt_Proposal, PostCheckpoint
from abcckpt.pre_checkpoint import AgentService
from tests.testUtil import TestUtility


class TestCkptProposal(unittest.TestCase):

    def setUp(self) -> None:
        testutil = TestUtility()
        tree = testutil.get_manual_tree()
        self.proposal = Ckpt_Proposal(tree, b'last_ckpt_id', 1, 99, b'Test', CkptService(tree))

    # no acks passed skip for now.
    # def test_checkpoint_stake(self):
    #     self.assertEqual(len(self.proposal.stake_list), 3, "Extracted stake count is not Equal.")

    # def test_gen_ckpt_hash(self):
    #     hash = self.proposal.gen_ckpt_hash(self.proposal.Ckpt)
    #     self.assertNotEqual(hash, None, "Checkpoint Hash generation unsuccessful")


class TestPostCheckpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.testutil = TestUtility()

    def test_checkpointVerify(self):
        tree = self.testutil.get_manual_tree()
        ckptservice = CkptService()
        ckptservice.set_checkpoint(tree)
        proposal = Ckpt_Proposal(tree, ckptservice.checkpoint.id, 1, 99, b'Miner', ckptservice)
        check2 = proposal.Ckpt

        status = PostCheckpoint.checkpoint_verify(tree, check2, ckptservice, AgentService())
        self.assertTrue(status)

    def test_verification_with_missing_txn(self):
        tree = Tree()

        w1: Wallet = Wallet(TestUtility.pub_key1, Decimal(50), b'Genesis', 0)  # gen(150)===>1(50)
        w2 = Wallet(TestUtility.pub_key2, Decimal(50), b'Genesis', 1)  # gen(100)===>2(50)
        w3 = Wallet(TestUtility.pub_key3, Decimal(50), b'Genesis', 2)  # gen(50)===>3(50)

        outputs: List[Wallet] = [w1, w2, w3]
        time = 0.01
        gen: Checkpoint = Checkpoint(b'Genesis', 0, time, 0, [], outputs,
                                     {TestUtility.pub_key1: Decimal(50), TestUtility.pub_key2: Decimal(50),
                                      TestUtility.pub_key3: Decimal(50)}, 0,
                                     Decimal(150), Decimal(150), b'Genesis')

        tree.add(gen.id, gen)

        w4 = Wallet(TestUtility.pub_key1, Decimal(24))
        w5 = Wallet(TestUtility.pub_key2, Decimal(24))
        w1.set_state(State.SPENT)

        trans1 = Transaction([w1], TestUtility.outputs_helper([w1], [w4, w5]), validator_key=TestUtility.pub_key2)

        tree.add(trans1.get_identifier(), trans1)

        ack1: Acknowledge = Acknowledge(trans1.get_identifier(), None, TestUtility.pub_key1)
        ack2 = Acknowledge(trans1.get_identifier(), None, TestUtility.pub_key2)
        ack3 = Acknowledge(trans1.get_identifier(), None, TestUtility.pub_key3)

        tree.add(ack1.get_identifier(), ack1)
        tree.add(ack2.get_identifier(), ack2)
        tree.add(ack3.get_identifier(), ack3)

        w6 = Wallet(TestUtility.pub_key3, Decimal(20))
        w7 = Wallet(TestUtility.pub_key1, Decimal(5))
        w5.set_state(State.SPENT)
        w2.set_state(State.SPENT)
        tree1 = copy.deepcopy(tree)
        trans2 = Transaction([w5, w2], TestUtility.outputs_helper([w5, w2], [w6, w7]), TestUtility.pub_key3)

        tree.add(trans2.get_identifier(), trans2)
        ack1 = Acknowledge(trans2.get_identifier(), None, TestUtility.pub_key1)
        ack2 = Acknowledge(trans2.get_identifier(), None, TestUtility.pub_key2)
        ack3 = Acknowledge(trans2.get_identifier(), None, TestUtility.pub_key3)

        tree.add(ack1.get_identifier(), ack1)
        tree.add(ack2.get_identifier(), ack2)
        tree.add(ack3.get_identifier(), ack3)

        ckptservice = CkptService()
        ckptservice.set_checkpoint(tree)
        proposal = Ckpt_Proposal(tree, gen.id, 1, 99, b'Miner', ckptservice)
        check2 = proposal.Ckpt

        status = PostCheckpoint.checkpoint_verify(tree1, check2, ckptservice, AgentService())
        print(status)
        assert status == (False, 'PENDING')

    def test_empty_ckpt(self):
        tree = Tree()

        w1: Wallet = Wallet(TestUtility.pub_key1, Decimal(50), b'Genesis', 0)  # gen(150)===>1(50)
        w2 = Wallet(TestUtility.pub_key2, Decimal(50), b'Genesis', 1)  # gen(100)===>2(50)
        w3 = Wallet(TestUtility.pub_key3, Decimal(50), b'Genesis', 2)  # gen(50)===>3(50)

        outputs: List[Wallet] = [w1, w2, w3]
        time = 0.01
        gen: Checkpoint = Checkpoint(b'Genesis', 0, time, 0, [], outputs,
                                     {TestUtility.pub_key1: Decimal(50), TestUtility.pub_key2: Decimal(50),
                                      TestUtility.pub_key3: Decimal(50)}, 0,
                                     Decimal(150), Decimal(150), b'Genesis')
        tree.add(gen.id, gen)

        ckptservice = CkptService()
        ckptservice.set_checkpoint(tree)
        proposal = Ckpt_Proposal(tree, gen.id, 1, 99, b'Miner', ckptservice)
        check2 = proposal.Ckpt

        status = PostCheckpoint.checkpoint_verify(tree, check2, ckptservice, AgentService())
        print(status)
        assert status == (False, 'EMPTY')
