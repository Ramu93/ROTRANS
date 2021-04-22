import unittest
from random import *
from abccore.DAG import *


class TestTransaction(unittest.TestCase):
    def test_output(self):
        output1 = Wallet("qwe123", 4)
        self.assertEqual(output1.value, 4)
        self.assertEqual(output1.own_key, "qwe123")

    def test_is_valid_trans_new_case1(self):
        """tests for one wallet in inputs"""
        val = randrange(2, 1000)

        inputs = [Wallet("a", val)]
        outputs = [Wallet("b", val - calculate_fee(val))]
        assert is_valid_trans(inputs, outputs)

        inputs = [Wallet("a", val)]
        outputs = [Wallet("a", val - (calculate_fee(1) + 1)), Wallet("b", 1)]
        assert is_valid_trans(inputs, outputs)

    def test_is_valid_trans_new_case2(self):
        """tests for two wallets in inputs"""
        val = randrange(2, 1000)

        inputs = [Wallet("a", val), Wallet("c", 1)]
        outputs = [Wallet("a", val - (calculate_fee(1))), Wallet("b", 1)]
        assert is_valid_trans(inputs, outputs)

        inputs = [Wallet("a", val), Wallet("c", 2)]
        outputs = [Wallet("a", val - (calculate_fee(3) + 1)), Wallet("c", 3)]
        assert is_valid_trans(inputs, outputs)

        inputs = [Wallet("a", val), Wallet("c", 2)]
        outputs = [Wallet("a", val - (calculate_fee(3) + 1)), Wallet("b", 0.5), Wallet("c", 2.5)]
        assert is_valid_trans(inputs, outputs)

        inputs = [Wallet("a", val), Wallet("c", 2)]
        outputs = [Wallet("a", val - (calculate_fee(1) + 1)), Wallet("b", 0.5), Wallet("c", 2.5)]
        assert not is_valid_trans(inputs, outputs)

    def test_is_valid_trans_new_case3(self):
        """tests for one wallet in inputs with two identical wallets in outputs"""
        val = randrange(2, 1000)

        inputs = [Wallet("a", val)]
        outputs = [Wallet("b", Decimal(val/2) - calculate_fee(Decimal(val/2))),
                   Wallet("b", Decimal(val/2) - calculate_fee(Decimal(val/2)))]
        assert is_valid_trans(inputs, outputs)

    def test_is_valid_trans_new_case4(self):
        """tests for one wallet in inputs with two identical wallets and one other in outputs. The identical wallets
        have the same pk as the input wallet.
        """
        val = randrange(2, 1000)
        own = Decimal(val - 1)

        inputs = [Wallet("a", val)]
        outputs = [Wallet("a", Decimal(own/2) - calculate_fee(Decimal(1/2))),
                   Wallet("a", Decimal(own/2) - calculate_fee(Decimal(1/2))),
                   Wallet("b", Decimal(1))]
        assert is_valid_trans(inputs, outputs)

    def test_get_wallet_value(self):
        value = Decimal(0)
        wallets = []
        for i in range(0, 100):
            rnd = randint(1, 200)
            value += rnd
            wallets.append(Wallet(i, rnd))

        assert get_wallet_value(wallets) == value


if __name__ == "__main__":
    unittest.main()
