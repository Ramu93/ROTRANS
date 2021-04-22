import os
from random import randrange as randrange
import unittest
from copy import deepcopy

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)
from abcnet import nettesthelpers

from abccore.agent import *
from abccore.DAG import *
from abccore.genesis_key_generator import load_genesis_keys
from tests import tree_test


class TestAgent(unittest.TestCase):
    def test_add_keypair(self):
        agent = Agent()
        agent.add_keypair()
        self.assertEqual(len(agent.a_data.keyset), 2)

    def test_send_money(self) -> Agent:
        """This function tests if the send_money() method works as intended. A gets balance from genesis and uses
        send_money() to create a Transaction and an Acknowledge, which are then put into its dict check_out.
        B gets those two items in its dict input_queue and runs its perform_maintenance.
        The test is correct, iff there are noe errors in execution.
        """
        agent_a = Agent()
        key_bytes = bytes.fromhex(
            "b45467f907401eb614e56a2920847e3900eb89559f66f39f822c0e42a938d261"
        )
        agent_a.add_pregenerated_keypair(
            Ed25519PrivateKey.from_private_bytes(key_bytes), True
        )
        agent_b = Agent()
        b_keys = agent_b.get_pub_key_bytes()
        agent_a._Agent__send_money(b_keys[0], Decimal(1), b_keys[0])

        for item in agent_a.check_out:
            agent_b.input_queue[item.id] = (item.item_type(), item)

        cs = nettesthelpers.pseude_cs()
        agent_b.perform_maintenance(cs)
        return agent_a

    def test_save_unconfirmed_data(self):
        agent_a = self.test_send_money()
        agent_a.save_data()
        return True

    def test_load_unconfirmed_data(self):
        agent_a = self.test_send_money()
        agent_a.save_data()
        agent_b = Agent()
        print("Load data:")
        agent_b.load_data()
        return True

    def test_get_pub_keys(self):
        pass  # TODO

    def test_outputs_helper_manual(self):
        val = 3
        pay_value = 1
        inputs = [Wallet("a1", 1), Wallet("a2", 2)]
        outputs = [Wallet("b", pay_value)]

        remaining_value = val - (pay_value + calculate_fee(pay_value))

        outputs_correct = [Wallet("b", 1), Wallet("a2", remaining_value)]

        # Test
        helper_outputs = outputs_helper(inputs, outputs)
        same = True
        for i in range(max(len(outputs_correct), len(helper_outputs))):
            try:
                if not outputs_correct[i].equals(helper_outputs[i]):
                    same = False
            except:
                same = False

        assert same

    def test_outputs_helper_positive_1(self):
        """inputs are completely spent in outputs"""
        val = randrange(2, 1000)

        inputs = [Wallet("a", val)]
        outputs = [Wallet("b", val - calculate_fee(val))]
        # Test
        helper_outputs = outputs_helper(inputs, outputs)
        same = True
        for i in range(max(len(outputs), len(helper_outputs))):
            try:
                if not outputs[i].equals(helper_outputs[i]):
                    same = False
            except:
                same = False

        assert same

        inputs = [Wallet("a", val), Wallet("b", 1)]
        outputs = [Wallet("a", val - calculate_fee(val + 1) + 1)]
        # Test
        helper_outputs = outputs_helper(inputs, outputs)
        same = True
        for i in range(max(len(outputs), len(helper_outputs))):
            try:
                if not outputs[i].equals(helper_outputs[i]):
                    same = False
            except:
                same = False

        assert same

    def test_outputs_helper_positive_2_1(self):
        """inputs are not completely spent in outputs"""
        val = Decimal(randrange(2, 1000))

        inputs = [Wallet("a", val)]
        pay_value = val - 2
        remaining_value = val - (pay_value + calculate_fee(pay_value))
        outputs = [Wallet("b", pay_value)]
        outputs_correct = [Wallet("b", pay_value), Wallet("a", remaining_value)]
        # Test
        helper_outputs = outputs_helper(inputs, outputs)
        same = True
        for i in range(max(len(outputs_correct), len(helper_outputs))):
            try:
                if not outputs_correct[i].equals(helper_outputs[i]):
                    same = False
            except:
                same = False

        assert same

    def test_outputs_helper_positive_2_2(self):
        """inputs are not completely spent in outputs"""
        val = Decimal(randrange(2, 1000))

        inputs = [Wallet("a", val), Wallet("b", 1)]
        pay_value = 1
        remaining_value = val - (pay_value + calculate_fee(pay_value))
        outputs = [Wallet("c", pay_value)]
        outputs_correct = [
            Wallet("c", pay_value),
            Wallet("b", 1),
            Wallet("a", remaining_value),
        ]
        # Test
        helper_outputs = outputs_helper(inputs, outputs)
        same = True
        for i in range(max(len(outputs_correct), len(helper_outputs))):
            try:
                if not outputs_correct[i].equals(helper_outputs[i]):
                    same = False
            except:
                same = False

        assert same

    def test_outputs_helper_positive_2_3(self):
        """outputs only redistribute money between inputs -> money laundering -> whole inputs will be taxed"""
        val = Decimal(10)

        inputs = [Wallet(bytes("a", "utf-8"), val)]
        pay_value = Decimal(5)
        remaining_value = val - (pay_value + calculate_fee(Decimal(10)))
        outputs = [Wallet(bytes("a", "utf-8"), pay_value)]
        outputs_correct = [
            Wallet(bytes("a", "utf-8"), pay_value),
            Wallet(bytes("a", "utf-8"), remaining_value),
        ]
        # Test
        helper_outputs = outputs_helper(inputs, outputs)
        same = True
        for i in range(max(len(outputs_correct), len(helper_outputs))):
            try:
                if not outputs_correct[i].equals(helper_outputs[i]):
                    same = False
            except:
                same = False

        assert same

    def test_save(self):
        """This is a manual test!"""

        agent = Agent()
        tree = Tree()
        generator = tree_test.Generator()

        generator.gen_genesis()
        for i in range(100):
            trans = generator.gen_transaction()
            tree.add(trans.get_identifier(), trans)
            agent.a_data.stake.append(trans.get_identifier())

        agent.a_data.tree = tree
        agent.a_data.balance = trans.get_outputs()
        agent.a_data.add_keypair()
        agent.save_data()
        print("test end")

    def test_load(self):
        """This is a manual test!"""
        agent = Agent()
        agent.load_data(filename="genesis.db")
        print("test end")

    def test_save_and_update(self):
        """This is a manual test!"""
        return (
            True  # TODO does currently not work, the Ack to to added needs a signature!
        )
        agent = Agent()
        tree = Tree()
        generator = tree_test.Generator()

        generator.gen_genesis()
        for i in range(100):
            trans = generator.gen_transaction()
            tree.add(trans.get_identifier(), trans)
            agent.a_data.stake.append(trans.get_identifier())

        agent.a_data.tree = tree
        agent.a_data.balance = trans.get_outputs()
        agent.a_data.add_keypair()
        agent.a_data.save_data(self.pending_transactions, self.orphaned_nodes)
        print("save done")

        trans = generator.gen_transaction()
        tree.add(trans.get_identifier(), trans)
        agent.a_data.add_to_save(trans)
        print("update add txn done")

        ack = Acknowledge(trans.get_identifier(), agent.a_data.last_ack, None)
        if ack.get_prev_ack() is None:
            ack.prev_ack = ack.get_identifier()
        agent.a_data.add_to_save(ack)
        print("update add ack done")

        agent.a_data.stake.append(trans.get_identifier())
        agent.a_data.update_last_ack(ack)
        print("update last ack done")

    def test_load_and_update(self):
        """This is a manual test!"""
        return True  # TODO: doesn't work; needs to be adjusted for correct Transaction generation
        agent = Agent()
        agent.load_data()
        print("load done")

        # new transaction
        trans = Transaction(
            [agent.a_data.balance[0], agent.a_data.balance[1]],
            outputs_helper(
                [agent.a_data.balance[0], agent.a_data.balance[1]],
                [agent.a_data.balance[0]],
            ),
            None,
        )

        agent.a_data.tree.add(trans.get_identifier(), trans)
        agent.a_data.add_to_save(trans)
        print("update add txn done")

        ack = Acknowledge(trans.get_identifier(), agent.a_data.last_ack, None)
        if ack.get_prev_ack() is None:
            ack.prev_ack = ack.get_identifier()
        agent.add_to_save(ack)
        print("update add ack done")

        agent.a_data.stake.append(trans.get_identifier())
        agent.a_data.update_last_ack(ack)
        print("update last ack done")

        wallet = trans.get_outputs()[1]
        wallet.set_state(State.SPENT)
        agent.a_data.update_wallet(wallet)
        print("update wallet done")

    def test_demo_save(self):
        """This is a manual test!"""
        agent = Agent()
        tree = Tree()

        keys = load_genesis_keys()
        wallets = [
            Wallet(
                keys[0]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[1]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[2]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[3]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[4]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[5]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[6]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[7]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[8]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
            Wallet(
                keys[9]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
                Decimal(10)
            ),
        ]

        genesis_node = Genesis(wallets)
        tree.add(genesis_node.get_identifier(), genesis_node)

        agent.a_data.tree = tree

        agent.a_data.save_data(self.pending_transactions, self.orphaned_nodes, filename="genesis.db")
        print("test end")

    def test_positive_validate_trans(self):
        """Tests correct behaviour of AgentData.validate_trans()."""
        agent = Agent()
        tree = Tree()
        generator = tree_test.Generator()
        genesis = generator.gen_genesis()
        tree.add(genesis.get_identifier(), deepcopy(genesis))

        for i in range(1):
            trans = generator.gen_transaction()
            tree.add(trans.get_identifier(), deepcopy(trans))

        agent.a_data.tree = tree
        assert agent.a_data.validate_trans(trans)
        # agent.validate_trans(trans, None)

        for input_wallet in (
            agent.a_data.tree.search(trans.get_identifier()).get_node().get_inputs()
        ):
            wallet_origin_node = agent.a_data.tree.search(input_wallet.get_origin())
            wallet_origin_trans = wallet_origin_node.get_node()
            wallet = wallet_origin_trans.get_outputs()[input_wallet.get_id()]

            assert wallet.get_state() == State.UNSPENT

    def test_negative_validate_trans_1(self):
        """Tests correct behaviour of AgentData.validate_trans()."""
        agent = Agent()
        tree = Tree()
        generator = tree_test.Generator()
        genesis = generator.gen_genesis()
        tree.add(genesis.get_identifier(), deepcopy(genesis))

        for i in range(10):
            trans = generator.gen_transaction()
            tree.add(trans.get_identifier(), trans)

        trans_copy = deepcopy(trans)

        for wallet in trans.get_inputs():
            wallet.set_state(State.SPENT)

        agent.a_data.tree = tree
        assert not agent.a_data.validate_trans(trans_copy)

        for input_wallet in (
            agent.a_data.tree.search(trans.get_identifier()).get_node().get_inputs()
        ):
            wallet_origin_node = agent.a_data.tree.search(input_wallet.get_origin())
            wallet_origin_trans = wallet_origin_node.get_node()
            wallet = wallet_origin_trans.get_outputs()[input_wallet.get_id()]

            assert not wallet.get_state() == State.UNSPENT

    def test_negative_validate_trans_2(self):
        """Tests correct behaviour of AgentData.validate_trans()."""
        agent = Agent()
        tree = Tree()
        generator = tree_test.Generator()
        genesis = generator.gen_genesis()
        tree.add(genesis.get_identifier(), deepcopy(genesis))

        for i in range(10):
            trans = generator.gen_transaction()
            tree.add(trans.get_identifier(), deepcopy(trans))

        for wallet in trans.get_inputs():
            wallet.value = Decimal(0)

        trans_tree_copy = tree.search(trans.get_identifier()).get_node()

        agent.a_data.tree = tree
        assert not agent.a_data.validate_trans(trans)

        for input_wallet in (
            agent.a_data.tree.search(trans.get_identifier()).get_node().get_inputs()
        ):
            wallet_origin_node = agent.a_data.tree.search(input_wallet.get_origin())
            wallet_origin_trans = wallet_origin_node.get_node()
            wallet = wallet_origin_trans.get_outputs()[input_wallet.get_id()]

            assert wallet.get_state() == State.UNSPENT

    def test_negative_authentication(self):
        """Tests if an agent not owning the inputs of a transaction is able to sign it."""
        agent = Agent()
        generator = tree_test.Generator()
        generator.gen_genesis()

        trans = generator.gen_transaction()

        assert agent.a_data._AgentData__create_signature(trans)
        assert not agent.a_data.validate_signature(trans)

        print("test end")

    def test_positive_acknowledge(self):
        """This tests the complete process of acknowledging a transaction"""
        agent = Agent()
        agent.a_data.keyset = []

        # add Keys from Genesis to Agent Keys
        key_bytes = bytes.fromhex(
            "b45467f907401eb614e56a2920847e3900eb89559f66f39f822c0e42a938d261"
        )
        agent.add_pregenerated_keypair(
            Ed25519PrivateKey.from_private_bytes(key_bytes), True
        )
        key_bytes = bytes.fromhex(
            "a3bf22d30bad4bf1fbfa42025ff15d46c8815f9e98c5d6fd5d3cbc72fd804d82"
        )
        agent.add_pregenerated_keypair(
            Ed25519PrivateKey.from_private_bytes(key_bytes), True
        )

        trans = agent.a_data.send_money(agent.get_pub_key_bytes()[1], 1, agent.get_pub_key_bytes()[1])

        assert agent._Agent__acknowledge(trans)


if __name__ == "__main__":
    unittest.main()
