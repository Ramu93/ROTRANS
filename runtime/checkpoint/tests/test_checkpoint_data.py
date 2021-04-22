import unittest
from random import randint
from abccore.agent import outputs_helper
from abcckpt.checkpointservice import CkptService
from abcckpt.ckptproposal import *
from abccore.prefix_tree import *
from tests.testUtil import TestUtility
from abccore.DAG import Transaction
import logging
import copy

logging.getLogger().setLevel(logging.INFO)


class TestTree(unittest.TestCase):
    wallets = []
    # broken test
    @unittest.skip
    def test_with_randomTransaction(self):
        tree = Tree()
        transactions = []
        time = 0.012
        self.gen_genesis()
        d = {}
        for wall in self.wallets:
            if not wall.origin in d:
                d[wall.origin] = Decimal(0)
            d[wall.origin] += wall.value
        gen: Checkpoint = Checkpoint(origin=b'Genesis', height=0, locktime=time, length=0, utxos=[],
                                     outputs=copy.copy(self.wallets),
                                     stake_list=d, nutxo=0, tstake=0, tcoins=0, miner=b'Genesis')

        tree.add(gen.id, gen)

        self.wallets = copy.copy(gen.outputs)

        for i in range(500):
            trans = self.gen_transaction()

            transactions.append(trans)
            assert tree.add(trans.get_identifier(), trans)
            ack1: Acknowledge = Acknowledge(trans.get_identifier(), None, TestUtility.pub_key1)
            ack2 = Acknowledge(trans.get_identifier(), None, TestUtility.pub_key2)
            ack3 = Acknowledge(trans.get_identifier(), None, TestUtility.pub_key3)
            assert tree.add(ack1.get_identifier(),ack1)
            assert tree.add(ack2.get_identifier(), ack2)
            assert tree.add(ack3.get_identifier(), ack3)

        proposal = Ckpt_Proposal(tree, gen.generate_hash_id(), 1, 99, TestUtility().pub_key1,
                                 CkptService().set_checkpoint(tree))
        ckpt = proposal.Ckpt
        self.assertEqual(ckpt.total_coins, ckpt.total_stake)

    def gen_transaction(self):
        """Picks a random number from 1 to 5 of existing wallets at random and creates a new transaction with it,
        transfering a random percentage of the value to a new wallet
        """

        number_wallets = randint(1, min(5, len(self.wallets)))
        inputs = []
        in_sum = Decimal(0)
        for number in range(0, number_wallets):
            i = randint(0, len(self.wallets) - 1)
            inputs.append(self.wallets.pop(i))
            in_sum += inputs[len(inputs) - 1].get_value()

        out_sum = in_sum * randint(1, 99) / 100

        outputs = outputs_helper(inputs, [Wallet(int.to_bytes(randint(0, 100), 32, "big"), Decimal(out_sum))])
        i = 0
        for wallet in outputs:
            wallet.id = i
            i += 1
            self.wallets.append(wallet)
        for input in inputs:
            input.set_state(State.SPENT)

        return Transaction(inputs, outputs, TestUtility.validator_list[randint(0, 3)])

    def gen_genesis(self):
        """Generates a genesis with up to 20 wallets of different owners"""
        self.wallets.clear()
        size = randint(1, 20)
        for i in range(size):
            val = Decimal(100)
            wall = Wallet(int.to_bytes(i, 32, "big"), val)
            wall.set_origin_id(b'Genesis', i)
            self.wallets.append(wall)
        logging.info("Total genesis value generated: " + str(get_wallet_value(self.wallets)))


class Test_manual_transaction(unittest.TestCase):

    def test_with_manual_transaction(self):
        testutil = TestUtility()
        tree = testutil.get_manual_tree()
        ckptservice = CkptService()
        ckptservice.set_checkpoint(copy.copy(tree))
        proposal = Ckpt_Proposal(tree, ckptservice.get_ckpt_id(), 1, 99, testutil.pub_key1, ckptservice)
        print("Total coins: " + str(proposal.Ckpt.total_coins))
        print("Total stake: " + str(proposal.Ckpt.total_stake))
        self.assertEqual(proposal.Ckpt.total_stake, proposal.Ckpt.total_coins)
