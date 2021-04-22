import unittest
import sys
from abccore.agent import *
from abccore.DAG import *
from random import *
import os


class TestTreePrefix(unittest.TestCase):
    def test_positive_search_dependend_nodes(self, length=1000):
        tree = Tree()
        self.generator = Generator()

        genesis = self.generator.gen_genesis()

        gen_wallets = set()

        for wallet in genesis.get_outputs():
            gen_wallets.add((wallet.get_origin(), wallet.get_id()))

        spent_wallets = set()

        tree.add(genesis.get_identifier(), genesis)

        for i in range(length):
            trans = self.generator.gen_transaction()
            ack = Acknowledge(trans.get_identifier(), None, None)

            tree.add(trans.get_identifier(), trans)
            tree.add(ack.get_identifier(), ack)

            for wallet in trans.get_inputs():
                pair = (wallet.get_origin(), wallet.get_id())
                if pair in gen_wallets or (wallet.get_origin(), ItemType.TXN) in spent_wallets:
                    spent_wallets.add((trans.get_identifier(), ItemType.TXN))
                    spent_wallets.add((ack.get_identifier(), ItemType.ACK))

        relatives = tree.search_dependend_nodes(gen_wallets)

        assert relatives == spent_wallets

    def test_positive_iterable(self):
        tree = Tree()
        self.generator = Generator()

        genesis = self.generator.gen_genesis()

        tree.add(genesis.get_identifier(), genesis)
        nodes = [genesis]
        length = 1000

        for i in range(length):
            trans = self.generator.gen_transaction()
            tree.add(trans.get_identifier(), trans)
            nodes.append(trans)

            ack = Acknowledge(trans.get_identifier(), None, None)
            tree.add(ack.get_identifier(), ack)
            nodes.append(ack)

        assert len(nodes) == 2*length + 1

        all_nodes = tree.get_all()
        assert len(all_nodes) == 2*length + 1

        nodes_per_iterator = []
        for elem in tree:
            nodes_per_iterator.append(elem)

        assert len(nodes_per_iterator) == 2*length + 1

    def test_positive_add_search(self):
        tree = Tree()
        self.generator = Generator()
        transactions = []

        self.generator.gen_genesis()

        for i in range(50000):
            trans = self.generator.gen_transaction()
            transactions.append(trans)
            assert tree.add(trans.get_identifier(), trans)

        for dag_node in transactions:
            tree_node = tree.search(dag_node.get_identifier()).get_node()
            assert tree_node.get_identifier() == dag_node.get_identifier()

    def test_positive_get_all(self):
        tree = Tree()
        self.generator = Generator()

        self.generator.gen_genesis()

        length = 10000
        trans = self.generator.gen_transaction()
        ack = Acknowledge(trans.get_identifier(), None, None)

        for i in range(length):
            trans = self.generator.gen_transaction()
            tree.add(trans.get_identifier(), trans)
            ack = Acknowledge(trans.get_identifier(), ack.get_identifier(), None)
            tree.add(ack.get_identifier(), ack)

        nodes = tree.get_all()
        assert len(nodes) == 2*length

    def test_positive_transaction_chain(self):
        """Creates a chain of transactions and checks if there is a complete chain from the last created transaction
        to the genesis.
        """
        tree = Tree()
        self.generator = Generator()

        genesis = self.generator.gen_genesis()
        tree.add(genesis.get_identifier(), genesis)
        print(sys.getrecursionlimit())

        for i in range(sys.getrecursionlimit() - 1):
            trans = self.generator.gen_transaction()
            assert tree.add(trans.get_identifier(), trans)

        assert self.generator.get_root(tree, trans)

    def test_positive_size(self):
        """With i == 1000000 this test takes ~ 1 minute"""
        tree = Tree()
        self.generator = Generator()
        transactions = []

        self.generator.gen_genesis()

        i = 0
        trans = self.generator.gen_transaction()
        while tree.add(trans.get_identifier(), trans):
            transactions.append(trans)
            trans = self.generator.gen_transaction()
            i += 1
            if i == 1000000:
                break

        assert i == 1000000

    def test_positive_search_predecessor(self):
        tree = Tree()
        self.generator = Generator()
        inputs = []
        transactions = []
        in_sum = 0

        self.generator.gen_genesis()

        for i in range(10):
            trans = self.generator.gen_transaction()
            transactions.append(trans)
            for entry in trans.get_outputs():
                inputs.append(entry)

            in_sum += trans.get_value()
            tree.add(trans.get_identifier(), trans)

        out_sum = in_sum - (2 * calculate_fee(in_sum))

        pk = os.urandom(32)
        receiver_wallet = Wallet(pk, out_sum)

        trans_test = Transaction(
            inputs, outputs_helper(inputs, [receiver_wallet]), None
        )
        tree.add(trans_test.get_identifier(), trans_test)

        outcome = tree.search_predecessors(trans_test.get_identifier())

        # list outcome has reversed order
        same = True
        length = max(len(outcome), len(transactions)) - 1
        for i in range(0, length):
            try:
                if not transactions[length - i] == outcome[i]:
                    same = False
            except:
                same = False
        assert same

    def test_negative_search_predecessor(self):
        tree = Tree()
        self.generator = Generator()
        inputs = []
        transactions = []
        in_sum = 0

        self.generator.gen_genesis()

        for i in range(5):
            trans = self.generator.gen_transaction()
            transactions.append(trans)
            for entry in trans.get_outputs():
                inputs.append(entry)

            in_sum += trans.get_value()
            tree.add(trans.get_identifier(), trans)

        # negative case
        transactions.pop()

        out_sum = in_sum - (2 * calculate_fee(in_sum))

        pk = os.urandom(32)
        receiver_wallet = Wallet(pk, out_sum)

        trans_test = Transaction(
            inputs, outputs_helper(inputs, [receiver_wallet]), None
        )
        tree.add(trans_test.get_identifier(), trans_test)

        outcome = tree.search_predecessors(trans_test.get_identifier())

        # list outcome has reversed order
        same = True
        length = max(len(outcome), len(transactions)) - 1
        for i in range(0, length):
            try:
                if not transactions[length - i] == outcome[i]:
                    same = False
            except:
                same = False
        assert not same

    def test_negative_add(self):
        tree = Tree()
        self.generator = Generator()

        self.generator.gen_genesis()
        trans = self.generator.gen_transaction()

        tree.add(trans.get_identifier(), trans)
        assert not tree.add(trans.get_identifier(), trans)

    def test_negative_search(self):
        """With range == 100000 this test takes ~ 15 seconds"""
        tree = Tree()
        self.generator = Generator()

        self.generator.gen_genesis()

        for i in range(100000):
            trans = self.generator.gen_transaction()
            assert tree.add(trans.get_identifier(), trans)

        for i in range(100000):
            trans = self.generator.gen_transaction()

            trans = tree.search(trans.get_identifier())
            assert trans is None

    # def test_multiple(self):
    # """This test will take much time and ram!"""
    # for i in range(10):
    #    self.test_positive_add_search()
    #    self.test_positive_size()
    #    self.test_positive_search_predecessor()
    #    self.test_negative_add()
    #    self.test_negative_search()
    #    self.test_negative_search_predecessor()


class Generator:
    def __init__(self):
        self.wallets = []

    def gen_genesis(self):
        """Generates a genesis with up to 20 wallets of different owners"""
        self.wallets.clear()
        size = randint(1, 20)
        for i in range(size):
            genesis = os.urandom(32)
            val = Decimal(100)
            new_wallet = Wallet(int.to_bytes(i, 32, "big"), val, genesis, i)
            self.wallets.append(deepcopy(new_wallet))
    
        return Genesis(copy(self.wallets))
        
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
    
        outputs = outputs_helper(
            inputs, [Wallet(int.to_bytes(randint(0, 100), 32, "big"), Decimal(out_sum))]
        )
    
        for wallet in outputs:
            self.wallets.append(wallet)

        new_trans = Transaction(inputs, outputs, None)
        return new_trans
        
    def get_root(self, tree: Tree, trans: Transaction):
        """Recursion to check if the current :param trans has genesis as parent or if the parents of trans have genesis as
        parent.
        """
        for parent in trans.get_parents():
            node = tree.search(parent)
            if isinstance(node, TreeLeaf):
                dag_node = node.get_node()
                if isinstance(dag_node, Genesis):
                    return True
    
                return self.get_root(tree, dag_node)
            elif node is not None:
                raise Exception("Unexpected Behaviour")
    
        return False


if __name__ == "__main__":
    unittest.main()
