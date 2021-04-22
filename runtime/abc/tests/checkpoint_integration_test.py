import unittest

from abccore.agent import *
from abcnet.settings import configure_logging
from checkpointservice import CkptService

configure_logging('log_conf/test_setting.yaml')


class TestAgent(unittest.TestCase):
    def test_ckpt_integration_1(self):
        """Tests if pending_transactions is consistent"""
        # create Agents
        agent_a = Agent()
        agent_b = Agent()
        args = []

        # Make pre test calculations
        pre_test_calucaltion(agent_a, agent_b, args)

        # Create Checkpoint
        agent_a.checkpoint_service = CkptService(agent_a.a_data.tree)
        ckpt = agent_a.checkpoint_service.generate_checkpoint(agent_a.a_data.tree, 10000, agent_a.get_pub_key_bytes()[1])

        # Apply Checkpoint
        agent_a.switch_to_ckpt(ckpt)
        agent_b.switch_to_ckpt(ckpt)

        # Compute TXNs of utxo list
        ckpt: Checkpoint
        transactions_set = set()
        for wallet in ckpt.get_utxos():
            transactions_set.add(wallet.get_origin())

        # Check for consistency
        for transaction in transactions_set:
            assert agent_a.a_data.tree.search(transaction) is not None
            assert agent_b.a_data.tree.search(transaction) is not None

    def test_ckpt_integration_2(self):
        """Tests if pending_transactions is consistent"""
        # create Agents
        agent_a = Agent()
        agent_b = Agent()
        args = []

        # Make pre test calculations
        pre_test_calucaltion(agent_a, agent_b, args)

        # Create Checkpoint
        agent_a.checkpoint_service = CkptService(agent_a.a_data.tree)
        ckpt = agent_a.checkpoint_service.generate_checkpoint(agent_a.a_data.tree, 10000, agent_a.get_pub_key_bytes()[1])

        # Apply Checkpoint
        agent_a.switch_to_ckpt(ckpt)
        agent_b.switch_to_ckpt(ckpt)

        # Check for consistency
        assert args[0] == agent_a.pending_transactions
        assert args[1] == agent_b.pending_transactions

    def test_ckpt_integration_3(self):
        """Tests if confirmed TXNs are added to pending TXNs"""
        # create Agents
        agent_a = Agent()
        agent_b = Agent()
        args = []

        # Make pre test calculations
        pre_test_calucaltion(agent_a, agent_b, args)

        # Create Checkpoint
        agent_a.checkpoint_service = CkptService(agent_a.a_data.tree)
        ckpt = agent_a.checkpoint_service.generate_checkpoint(agent_a.a_data.tree, 10000, agent_a.get_pub_key_bytes()[1])

        # Compute TXNs of utxo list; for part 2
        ckpt: Checkpoint
        transactions_set = set()
        for wallet in ckpt.get_utxos():
            transactions_set.add(wallet.get_origin())

        # Compute ACKs of TXNs which were added after utxo TXNs; for part 2
        ack_set_a = set()
        dependend_nodes_a = agent_a.a_data.tree.search_dependend_nodes(ckpt.get_utxos())
        for pair in dependend_nodes_a:
            if pair[1] is ItemType.ACK:
                ack_set_a.add(pair[0])
        ack_set_b = set()
        dependend_nodes_b = agent_b.a_data.tree.search_dependend_nodes(ckpt.get_utxos())
        for pair in dependend_nodes_b:
            if pair[1] is ItemType.ACK:
                ack_set_b.add(pair[0])

        # Move TXNs from pending_transactions to tree
        for key in agent_a.pending_transactions:
            pair = agent_a.pending_transactions.get(key)
            agent_a.a_data.tree.add(pair[0].get_identifier(), pair[0])
            agent_a.a_data.check_and_register_ownership(pair[0])
        agent_a.pending_transactions.clear()
        for key in agent_b.pending_transactions:
            pair = agent_b.pending_transactions.get(key)
            agent_b.a_data.tree.add(pair[0].get_identifier(), pair[0])
            agent_b.a_data.check_and_register_ownership(pair[0])
        agent_b.pending_transactions.clear()

        # Apply Checkpoint
        agent_a.switch_to_ckpt(ckpt)
        agent_b.switch_to_ckpt(ckpt)

        # Check for consistency; for part 1
        assert args[0] == agent_a.pending_transactions
        assert args[1] == agent_b.pending_transactions

        # Check for consistency; for part 2
        for ack in ack_set_a:
            assert agent_a.a_data.tree.search(ack) is not None
        for ack in ack_set_b:
            assert agent_b.a_data.tree.search(ack) is not None


def pre_test_calucaltion(agent_a, agent_b, args):
    # add Key from Genesis to Agent Keys
    key_bytes = bytes.fromhex(
        "b45467f907401eb614e56a2920847e3900eb89559f66f39f822c0e42a938d261"
    )
    agent_a.add_pregenerated_keypair(
        Ed25519PrivateKey.from_private_bytes(key_bytes), True
    )
    key_bytes = bytes.fromhex(
        "a3bf22d30bad4bf1fbfa42025ff15d46c8815f9e98c5d6fd5d3cbc72fd804d82"
    )
    agent_b.add_pregenerated_keypair(
        Ed25519PrivateKey.from_private_bytes(key_bytes), True
    )
    # Make TXNs
    txn_ping_pong(agent_a, agent_b, True)

    # Create TXNs, these stay in the pending_transactions, while their ACKs are put in the dag
    args.extend(txn_ping_pong(agent_a, agent_b, False, 1))


def txn_ping_pong(agent_a, agent_b, add, length=20):
    # Extract PK from Agent
    keys_a = agent_a.get_pub_key_bytes()
    keys_b = agent_b.get_pub_key_bytes()

    # Save pending_trans for test
    pending_trans_a = dict()
    pending_trans_b = dict()

    # Make Transactions, place all in dag
    for i in range(length):
        # calculate current amount of money the Agent has
        value_a = Decimal(0)
        for wallet in agent_a.a_data.balance:
            value_a += wallet.get_value()
        value_b = Decimal(0)
        for wallet in agent_b.a_data.balance:
            value_b += wallet.get_value()

        # take random amount of owned money
        txn_value_a = round(value_a / 25, 4)
        txn_value_a = Decimal(txn_value_a)
        print("TXN A value: ", txn_value_a)
        txn_value_b = round(value_b / 25, 4)
        txn_value_b = Decimal(txn_value_b)
        print("TXN B value: ", txn_value_b)

        # Create TXN and ACK
        agent_a._Agent__send_money(keys_b[1], txn_value_a, keys_b[1])
        agent_b._Agent__send_money(keys_a[1], txn_value_b, keys_a[1])

        if add:
            # Take TXN and put it in dag
            for item_a in agent_a.check_out:
                if item_a.item_type() == ItemType.TXN:
                    item_a: NetTransaction
                    txn_code_a = item_a.txn.get_identifier()

                    pending_trans_a[txn_code_a] = copy(agent_a.pending_transactions.get(txn_code_a))
                    agent_a.pending_transactions.pop(txn_code_a)

                    for input_wallet in item_a.txn.get_inputs():
                        input_wallet: Wallet
                        input_wallet.set_state(State.SPENT)
                    agent_a.a_data.tree.add(txn_code_a, item_a.txn)
                    agent_a.a_data.check_and_register_ownership(item_a.txn)

                    agent_b.a_data.tree.add(txn_code_a, item_a.txn)
                    agent_b.a_data.check_and_register_ownership(item_a.txn)
                else:
                    item_a: NetAcknowledgement
                    txn_code_a = item_a.ack.get_identifier()
                    agent_a.a_data.tree.add(txn_code_a, item_a.ack)

                    agent_b.a_data.tree.add(txn_code_a, item_a.ack)

            for item in agent_b.check_out:
                if item.item_type() == ItemType.TXN:
                    item: NetTransaction
                    txn_code_b = item.txn.get_identifier()

                    pending_trans_b[txn_code_b] = copy(agent_b.pending_transactions.get(txn_code_b))
                    agent_b.pending_transactions.pop(txn_code_b)

                    for input_wallet in item.txn.get_inputs():
                        input_wallet: Wallet
                        input_wallet.set_state(State.SPENT)

                    agent_b.a_data.tree.add(txn_code_b, item.txn)
                    agent_b.a_data.check_and_register_ownership(item.txn)

                    agent_a.a_data.tree.add(txn_code_b, item.txn)
                    agent_a.a_data.check_and_register_ownership(item.txn)
                else:
                    item: NetAcknowledgement
                    txn_code_b = item.ack.get_identifier()
                    agent_b.a_data.tree.add(txn_code_b, item.ack)

                    agent_a.a_data.tree.add(txn_code_b, item.ack)

        agent_a.check_out.clear()
        agent_b.check_out.clear()

    if len(pending_trans_a) > 0:
        return [pending_trans_a, pending_trans_b]
    else:
        return [copy(agent_a.pending_transactions), copy(agent_b.pending_transactions)]




