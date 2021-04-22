from decimal import Decimal
from random import randint
from typing import List

from abccore.DAG import State
from abccore.DAG import Wallet, Genesis, Checkpoint, Transaction, Acknowledge, calculate_fee, is_valid_trans
from abccore.prefix_tree import Tree
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class TestUtility:
    wallets = []
    p1 = "b45467f907401eb614e56a2920847e3900eb89559f66f39f822c0e42a938d261"
    p2 = "a3bf22d30bad4bf1fbfa42025ff15d46c8815f9e98c5d6fd5d3cbc72fd804d82"
    p3 = "3b32a3c4a5f30982be33f7f76e73e96e2798de729ffd8595772006cd807f329d"
    p4 = "2b1c87e7fa5cd11e6dc807ea3b4c272293c00e092741cee9247c95ce932830d0"

    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p1))
    pub_key1 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p2))
    pub_key2 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p3))
    pub_key3 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p4))
    pub_key4 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def __init__(self):
        self.tree = Tree()

    def get_sample_checkpoint(self):
        self.time_stamp = float(1.1)
        self.utxo = [Wallet(self.pub_key1, Decimal(25), b'genesis'),
                     Wallet(self.pub_key2, Decimal(25), b'genesis'),
                     Wallet(self.pub_key3, Decimal(25), b'genesis'),
                     Wallet(self.pub_key4, Decimal(25), b'genesis')]

        for i, w in enumerate(self.utxo):
            w: Wallet
            w.set_origin_id(w.origin, i)

        self.stake_dict = {self.pub_key1: Decimal(25), self.pub_key2: Decimal(25), self.pub_key3: Decimal(25),
                           self.pub_key4: Decimal(25)}
        gen = Checkpoint(b'Genesis', 1, self.time_stamp, length=10000, utxos=self.utxo,
                         stake_list=self.stake_dict, outputs=[],
                         nutxo=4, tstake=Decimal(100), tcoins=Decimal(100),
                         miner=b'genesis')
        return gen

    def get_gen_checkpoint(self):
        w1: Wallet = Wallet(self.pub_key1, Decimal(50), b'Genesis', 0)  # gen(150)===>1(50)
        w2 = Wallet(self.pub_key2, Decimal(50), b'Genesis', 1)  # gen(100)===>2(50)
        w3 = Wallet(self.pub_key3, Decimal(50), b'Genesis', 2)  # gen(50)===>3(50)

        outputs: List[Wallet] = [w1, w2, w3]
        time = 0.01
        gen: Checkpoint = Checkpoint(b'Genesis', 0, time, 0, [], outputs, {}, 3,
                                     Decimal(0), Decimal(150), b'Genesis')
        return gen

    def get_manual_tree(self):

        w1: Wallet = Wallet(self.pub_key1, Decimal(50), b'Genesis', 0)  # gen(150)===>1(50)
        w2 = Wallet(self.pub_key2, Decimal(50), b'Genesis', 1)  # gen(100)===>2(50)
        w3 = Wallet(self.pub_key3, Decimal(500000), b'Genesis', 2)  # gen(50)===>3(50)

        outputs: List[Wallet] = [w1, w2, w3]
        time = 0.01
        gen: Checkpoint = Checkpoint(b'Genesis', 0, time, 0, [], outputs,
                                     {self.pub_key1: Decimal(50), self.pub_key2: Decimal(50),
                                      self.pub_key3: Decimal(500000.28742734872)}, 0,
                                     Decimal(150), Decimal(150), b'Genesis')

        self.tree.add(gen.id, gen)

        w4 = Wallet(self.pub_key1, Decimal(24))
        w5 = Wallet(self.pub_key2, Decimal(24))
        w1.set_state(State.SPENT)

        trans1 = Transaction([w1], self.outputs_helper([w1], [w4, w5]), validator_key=self.pub_key2)

        self.tree.add(trans1.get_identifier(), trans1)

        ack1: Acknowledge = Acknowledge(trans1.get_identifier(), None, self.pub_key1)
        ack2 = Acknowledge(trans1.get_identifier(), None, self.pub_key2)
        ack3 = Acknowledge(trans1.get_identifier(), None, self.pub_key3)
        # commented due to "Couldn't set dependency, there is a node missing in the DAG! AttributeError" because there
        # are no prev ack
        self.tree.add(ack1.get_identifier(), ack1)
        self.tree.add(ack2.get_identifier(), ack2)
        self.tree.add(ack3.get_identifier(), ack3)

        w6 = Wallet(self.pub_key3, Decimal(20))
        w7 = Wallet(self.pub_key1, Decimal(5))
        w5.set_state(State.SPENT)
        w2.set_state(State.SPENT)

        trans2 = Transaction([w5, w2], self.outputs_helper([w5, w2], [w6, w7]), self.pub_key3)

        self.tree.add(trans2.get_identifier(), trans2)
        ack1 = Acknowledge(trans2.get_identifier(), None, self.pub_key1)
        ack2 = Acknowledge(trans2.get_identifier(), None, self.pub_key2)
        ack3 = Acknowledge(trans2.get_identifier(), None, self.pub_key3)

        self.tree.add(ack1.get_identifier(), ack1)
        self.tree.add(ack2.get_identifier(), ack2)
        self.tree.add(ack3.get_identifier(), ack3)

        return self.tree

    def gen_genesis(self):
        """imported from abccore"""
        self.wallets.clear()
        size = randint(1, 20)
        for i in range(size):
            genesis = b'Genesis'
            val = Decimal(100)
            self.wallets.append(Wallet(int.to_bytes(i, 32, "big"), val, genesis, i))

        return Genesis(self.wallets)

    validator_list = [pub_key1, pub_key2, pub_key3,
                      pub_key4]  # list of validators to randomize the validator in transactions

    def gen_transaction(self):
        """Imported from abccore:
        Picks a random number from 1 to 5 of existing wallets at random and creates a new transaction with it,
        transfering a random percentage of the value to a new wallet
        """
        number_wallets = randint(1, min(5, len(self.wallets)))
        inputs = []
        in_sum = Decimal(0)
        for number in range(0, number_wallets):
            i = randint(0, len(self.wallets) - 1)
            inputs.append(self.wallets.pop(i))
            in_sum += inputs[len(inputs) - 1].get_value()
        for v in inputs:
            v.set_state(State.SPENT)
        out_sum = in_sum * randint(1, 99) / 100

        outputs = TestUtility.outputs_helper(
            inputs, [Wallet(int.to_bytes(randint(0, 100), 32, "big"), Decimal(out_sum))]
        )

        for wallet in outputs:
            self.wallets.append(wallet)

        return Transaction(inputs, outputs, TestUtility.validator_list[randint(0, 3)])

    @staticmethod
    def outputs_helper(inputs, outputs):
        """Imported from abccore:
        Adds remaining value of input wallets to outputs after calculating fee based on :param outputs.
        See Issue #16 for more information.
        The function first calculates the fee for the transaction based on :param inputs and :param outputs, just like
        agent.is_valid_function() does, but it calculates the remaining value of the wallets in :param inputs, too.
        Then, the public keys of wallets in :param inputs will be used to create new wallets for the remaining value
        starting at the last wallet in the list :param inputs. This is to ensure that the remaining value won't be subject
        to the transaction fee as proposed in Issue #14.
        :param inputs: list of wallets to be spend in a transaction.
        :param outputs: list of wallets to be paid without own wallets for remaining value, those will be created here.
        """
        in_sum = Decimal(0)
        out_sum = Decimal(0)
        inputs_dict = {}
        taxed = Decimal(0)
        for wallet in inputs:
            in_sum += wallet.get_value()
            if inputs_dict.get(wallet.get_pk()) is None:
                inputs_dict[wallet.get_pk()] = wallet.get_value()
            else:
                inputs_dict[wallet.get_pk()] += wallet.get_value()

        laundering = (
            True  # if the output wallets only redistirbute money between the input wallets
        )
        for wallet in outputs:
            out_sum += wallet.get_value()

            if (
                    inputs_dict.get(wallet.get_pk()) is None
                    or inputs_dict.get(wallet.get_pk()) < wallet.get_value()
            ):
                taxed += wallet.get_value()
                laundering = False

        if laundering:
            taxed = in_sum

        fee = calculate_fee(taxed)
        remaining_value = in_sum - (out_sum + fee)
        while not remaining_value <= 0:
            key_value = inputs_dict.popitem()
            if key_value[1] > remaining_value:
                outputs.append(Wallet(key_value[0], remaining_value))
                remaining_value = 0
            else:
                outputs.append(Wallet(key_value[0], key_value[1]))
                remaining_value -= key_value[1]

        if is_valid_trans(inputs, outputs):
            return outputs
        else:  # Error Handling
            msg = "Didn't create valid outputs for this inputs: ["
            is_valid_trans(inputs, outputs)
            for wallet in inputs:
                msg += str(wallet) + ", "

            msg += "]. Got instead this: ["
            for wallet in outputs:
                msg += str(wallet) + ", "

            msg += "]."
            raise Exception(msg)
