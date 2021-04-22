import random
import unittest
from abccore.agent import *
from abccore.agent_items_parser import AgentItemsParser
from abccore.network_datastructures import (
    NetTransaction,
    NetAcknowledgement,
    Transcriber,
    NetUSPWR,
    reduce_ttl,
)
from abccore.agent_crypto import pub_key_to_bytes
from tests.tree_test import Generator
from abcnet.structures import ItemType
from abcnet.transcriber import Parser
from abccore.genesis_key_generator import load_genesis_keys
from abccore.constants import TTL

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import PublicFormat


class TestAgentNetwork(unittest.TestCase):
    def test_transaction_encoding_decoding(self):
        generator = Generator()
        generator.gen_genesis()
        t = generator.gen_transaction()
        txn = NetTransaction(t)

        transcriber = Transcriber()
        txn.encode(transcriber)

        parser = Parser(transcriber.msg.parts[0])
        txn2 = AgentItemsParser().decode_item(ItemType.TXN, parser)

        for i in range(0, len(txn.txn.inputs)):
            assert txn.txn.inputs[i].value == txn2.txn.inputs[i].value
            assert txn.txn.inputs[i].origin == txn2.txn.inputs[i].origin
            assert txn.txn.inputs[i].own_key == txn2.txn.inputs[i].own_key

        for i in range(0, len(txn.txn.outputs)):
            assert txn.txn.outputs[i].value == txn2.txn.outputs[i].value
            assert txn.txn.outputs[i].origin == txn2.txn.outputs[i].origin
            assert txn.txn.outputs[i].own_key == txn2.txn.outputs[i].own_key

        assert txn.txn.inputs == txn2.txn.inputs
        assert txn.txn.outputs == txn2.txn.outputs
        assert txn.txn.value == txn2.txn.value
        assert txn.txn.validator_key == txn2.txn.validator_key
        assert txn.txn.signatures == txn2.txn.signatures

    def test_acknowledgement_encoding_decoding(self):
        agent = Agent()
        generator = Generator()
        generator.gen_genesis()
        t = generator.gen_transaction()
        pub_key = agent.get_pub_keys()[0].public_bytes(Encoding.Raw, PublicFormat.Raw)
        preack = Acknowledge(t.get_identifier(), None, pub_key)
        suback = NetAcknowledgement(preack)
        ack = NetAcknowledgement(Acknowledge(t.get_identifier(), suback.id, pub_key))

        transcriber = Transcriber()
        ack.encode(transcriber)

        parser = Parser(transcriber.msg.parts[0])
        ack2: NetAcknowledgement = AgentItemsParser().decode_item(ItemType.ACK, parser)

        assert ack.ack.identifier == ack2.ack.identifier
        assert ack.ack.prev_ack == ack2.ack.prev_ack
        assert ack.ack.transaction == ack2.ack.transaction
        assert ack.ack.get_pb_key() == ack2.ack.get_pb_key()
        assert ack.ack.signature == ack2.ack.signature

    def test_unspent_wallets_encoding_decoding(self):
        generator = Generator()
        gen = generator.gen_genesis()

        t = generator.gen_transaction()
        t2 = generator.gen_transaction()
        test_set = set()
        for wallet in gen.outputs:
            test_set.add((wallet.origin, wallet.id))
        for wallet in t.outputs:
            test_set.add((wallet.origin, wallet.id))
        for wallet in t2.outputs:
            test_set.add((wallet.origin, wallet.id))

        uspwr = NetUSPWR(test_set)

        transcriber = Transcriber()
        uspwr.encode(transcriber)

        parser = Parser(transcriber.msg.parts[0])
        uspwr2: NetUSPWR = AgentItemsParser().decode_item(
            ItemType.UNSPENT_WALLET_COLLECTION, parser
        )

        assert uspwr.unspent_wallet_set == uspwr2.unspent_wallet_set
        assert uspwr.is_req == uspwr2.is_req
        assert uspwr.id == uspwr2.id

    def test_uspwr_datastructure(self):
        agent = Agent()
        generator = Generator()
        generator.gen_genesis()
        t = generator.gen_transaction()
        test_set = set()
        for wallet in t.inputs:
            test_set.add((wallet.origin, wallet.id))

        assert NetUSPWR(test_set, is_req=2)
        try:
            NetUSPWR(test_set, bytes.fromhex("02"))
        except ValueError:
            assert True
        else:
            assert False

        try:
            NetUSPWR(test_set, id=bytes.fromhex("A6"))
        except ValueError:
            assert True
        else:
            assert False

    def test_ttl(self):
        item_list = list()
        generator = Generator()
        generator.gen_genesis()
        for i in range(0, TTL):
            item_list.append(NetTransaction(generator.gen_transaction()))
            reduce_ttl(item_list, debug=True)

        for i in range(0, TTL - 1):
            assert item_list[i].ttl == i + 1

    def test_create_transaction(self):
        pass
        # key = load_genesis_keys()[0]
        # agent = Agent(key)
        # value = Decimal(5)

        # validator = pub_key_to_bytes(key.public_key())

        # key2 = load_genesis_keys()[1]
        # agent2 = Agent(key2)

        # recipient = agent2.get_pub_key_bytes()[0]

        # agent._Agent__send_money(recipient, value, validator)
        # # Transaction()

        # net_txn = agent.check_out[0]

    # TODO

    def sum_wallets(wallets):
        w_sum = 0
        for wallet in wallets:
            w_sum += wallet.value
        return w_sum


if __name__ == "__main__":
    unittest.main()