import unittest
from decimal import Decimal

from abccore.DAG import Transaction, Wallet, Acknowledge, Genesis
import abccore.DAG as DAG


def always_valid_trans(*args):
    return True

DAG.is_valid_trans = always_valid_trans


def assert_wallet_id_matches_txn(txn: Transaction):
    for w in txn.outputs:
        w: Wallet
        assert w.origin == txn.get_identifier()


class TestNodeId(unittest.TestCase):

    def test_transaction_id_empty_wallets(self):
        in_wallets = [
        ]
        out_wallets = [
        ]
        txn = Transaction(in_wallets, out_wallets, None)
        assert_wallet_id_matches_txn(txn)

        out_wallets2 = [
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn2.get_identifier() == txn.get_identifier()

    def test_transaction_id_empty_out_wallets(self):
        in_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0)
        ]
        out_wallets = [

        ]
        txn = Transaction(in_wallets, out_wallets, None)
        assert_wallet_id_matches_txn(txn)

        out_wallets2 = [
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn2.get_identifier() == txn.get_identifier()

    def test_transaction_id_empty_in_wallets(self):
        in_wallets = [
        ]
        out_wallets = [
            Wallet(b'2', Decimal(10)),
            Wallet(b'2', Decimal(2))
        ]
        txn = Transaction(in_wallets, out_wallets, None)
        assert_wallet_id_matches_txn(txn)

        out_wallets2 = [
            Wallet(b'2', Decimal(10)),
            Wallet(b'2', Decimal(2))
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn2.get_identifier() == txn.get_identifier()

    def test_transaction_id(self):
        in_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0)
        ]
        out_wallets = [
            Wallet(b'2', Decimal(10)),
            Wallet(b'2', Decimal(2))
        ]
        txn = Transaction(in_wallets, out_wallets, None)
        assert_wallet_id_matches_txn(txn)

        out_wallets2 = [
            Wallet(b'2', Decimal(10)),
            Wallet(b'2', Decimal(2))
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn2.get_identifier() == txn.get_identifier()

    def test_transaction_id_different_validator(self):
        in_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0)
        ]
        out_wallets = [
            Wallet(b'2', Decimal(10)),
            Wallet(b'2', Decimal(2))
        ]
        txn = Transaction(in_wallets, out_wallets, 'validator1')
        assert_wallet_id_matches_txn(txn)

        out_wallets2 = [
            Wallet(b'2', Decimal(10)),
            Wallet(b'2', Decimal(2))
        ]
        txn2 = Transaction(in_wallets, out_wallets2, 'validator2')
        assert txn2.get_identifier() == txn.get_identifier()

    def test_transaction_different_content(self):
        in_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0)
        ]
        out_wallets = [
            Wallet(b'2', Decimal(10)),
        ]
        txn = Transaction(in_wallets, out_wallets, None)
        out_wallets2 = [
            Wallet(b'1', Decimal(10)),
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn.get_identifier() != txn2.get_identifier()
        out_wallets2 = [
            Wallet(b'1', Decimal(11)),
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn.get_identifier() != txn2.get_identifier()
        out_wallets2 = [
            Wallet(b'1', Decimal(10)),
            Wallet(b'1', Decimal(11)),
        ]
        txn2 = Transaction(in_wallets, out_wallets2, None)
        assert txn.get_identifier() != txn2.get_identifier()
        in_wallets2 = [
            Wallet(b'1', Decimal(11), b"o1", 0),
        ]
        txn2 = Transaction(in_wallets2, out_wallets, None)
        assert txn.get_identifier() != txn2.get_identifier()
        in_wallets2 = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'2', Decimal(1), b"o2", 0)
        ]
        txn2 = Transaction(in_wallets2, out_wallets, None)
        assert txn.get_identifier() != txn2.get_identifier()
        in_wallets2 = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o3", 0)
        ]
        txn2 = Transaction(in_wallets2, out_wallets, None)
        assert txn.get_identifier() != txn2.get_identifier()
        in_wallets2 = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(2), b"o2", 0)
        ]
        txn2 = Transaction(in_wallets2, out_wallets, None)
        assert txn.get_identifier() != txn2.get_identifier()
        in_wallets2 = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 1)
        ]
        txn2 = Transaction(in_wallets2, out_wallets, None)
        assert txn.get_identifier() != txn2.get_identifier()


class TestAckId(unittest.TestCase):

    def test_ack_id_equality(self):
        ack1 = Acknowledge(b'txn', b'ack1', b'pbk1')
        ack2 = Acknowledge(b'txn', b'ack1', b'pbk1')
        assert ack1.get_identifier() == ack2.get_identifier()

    def test_ack_id_inequality(self):
        ack1 = Acknowledge(b'txn', b'ack1', b'pbk1')
        ack2 = Acknowledge(b'txn', b'ack2', b'pbk1')
        assert ack1.get_identifier() != ack2.get_identifier()

        ack2 = Acknowledge(b'txn1', b'ack1', b'pbk1')
        assert ack1.get_identifier() != ack2.get_identifier()

        ack2 = Acknowledge(b'txn1', b'ack2', b'pbk1')
        assert ack1.get_identifier() != ack2.get_identifier()

        ack2 = Acknowledge(b'txn', b'ack', b'pbk2')
        assert ack1.get_identifier() != ack2.get_identifier()

        ack2 = Acknowledge(b'txn1', b'ack', b'pbk2')
        assert ack1.get_identifier() != ack2.get_identifier()

        ack2 = Acknowledge(b'txn1', b'ack2', b'pbk2')
        assert ack1.get_identifier() != ack2.get_identifier()

class TestGensisId(unittest.TestCase):

    def test_empty_genesis_id(self):
        out_wallets = [
        ]
        gen1 = Genesis(out_wallets)
        out_wallets = [
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() == gen2.get_identifier()
        assert len(gen1.get_identifier()) != 0

    def test_genesis_id_equality(self):
        out_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 1),
        ]
        gen1 = Genesis(out_wallets)
        out_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 1),
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() == gen2.get_identifier()

    def test_genesis_id_inequality(self):
        out_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 1),
        ]
        gen1 = Genesis(out_wallets)
        assert gen1.get_identifier() is not None
        out_wallets = [
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() != gen2.get_identifier()
        out_wallets = [
            Wallet(b'1', Decimal(1), b"o1", 1),
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() != gen2.get_identifier()
        out_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'12', Decimal(1), b"o2", 1),
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() != gen2.get_identifier()
        out_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 1),
            Wallet(b'3', Decimal(1), b"o2", 1),
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() != gen2.get_identifier()
        out_wallets = [
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0),
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0),
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0),
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0),
            Wallet(b'1', Decimal(11), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 0),
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() != gen2.get_identifier()
        out_wallets = [
            Wallet(b'1', Decimal(110), b"o1", 0),
            Wallet(b'1', Decimal(1), b"o2", 1),
        ]
        gen2 = Genesis(out_wallets)
        assert gen1.get_identifier() != gen2.get_identifier()


if __name__ == "__main__":
    unittest.main()
