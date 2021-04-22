import os
import unittest

import prefix_tree
from agent import *
from abccore.prefix_tree import *
from abccore.agent import *

from tests.tree_test import Generator, TestTreePrefix

wallets = []


class Tree:
    """This is a wrapper class for the python dictionary to be used as if it had the functions of a prefix tree.
    The docs are copied from prefix_tree.py.
    """
    def __init__(self):
        self.storage = {}

    def search(self, code: bytes) -> "TreeLeaf":  # changed to dict, output changed to DAG.Node
        """The search() function :return a node from the tree if there is one corresponding to the code, otherwise None.
        :param code: identifier of DAG.Node to be searched in the tree.
        """
        if self.storage.get(code) is None:
            return None
        else:
            return self.storage.get(code)

    def add(self, code: bytes, node: "DAG.Node") -> bool:  # changed to dict
        """The add() function :return True if it was able to add a DAG.Node to the tree, otherwise False.
        This function is extended in TreeNode.
        :param code: identifier of DAG.Node to be added in the tree.
        :param node: DAG.Node to be added in the tree.
        """
        if self.storage.get(code) is None:
            self.storage[code] = node
            return True
        else:
            return False

    def search_predecessors(self, code: bytes):  # changed to dict
        """This function returns a list of TreeLeaf.
        :param code: Identifier of a DAG.Node. Its representation in the Tree will be searched and from there all
        predecessors of the DAG.Node will be searched and their representations in Tree will be returned.
        """
        input_node = self.storage.get(code)
        output = []

        parents_dict = input_node.get_parents()
        while len(parents_dict) > 0:
            output.append(self.search(parents_dict.popitem()[0]))

        return output


class TestTreeDict(unittest.TestCase):
    def test_runtime_search_unspent_wallets(self):
        """This will test the runtime of the prefix tree method search_unspent_wallets() to be linear in the number of
        Nodes in the Tree. This test will take a long time (2h+ for range 100)! It measures the average time needed for
        this check per one Node in the DAG.
        """
        time = []
        for i in range(1, 11):
            size = i*10000
            timer = StopTimer()
            TestTreePrefix().test_positive_search_unspent_wallets(size)
            time.append(timer.time()/size)

        time_sum = sum(time)
        average_time_per_node = time_sum/len(time)
        max_time_per_node = max(time)
        min_time_per_node = min(time)

        print("Average: " + str(average_time_per_node))
        print("Max: " + str(max_time_per_node))
        print("Min: " + str(min_time_per_node))

    def test_positive_add_search_dict(self):
        """Benchmark to compare run time and tree footprint of python dictionary against prefix tree"""
        tree = Tree()
        transactions = []
        generator = Generator()

        generator.gen_genesis()

        for i in range(50000):
            trans = generator.gen_transaction()
            transactions.append(trans)
            assert tree.add(trans.get_identifier(), trans)

        for dag_node in transactions:
            tree_node = tree.search(dag_node.get_identifier())
            assert tree_node.get_identifier() == dag_node.get_identifier()

    def test_positive_size(self):
        """With i == 1000000 this test takes ~ 1 minute"""
        tree = Tree()
        generator = Generator()
        transactions = []

        generator.gen_genesis()

        i = 0
        trans = generator.gen_transaction()
        while tree.add(trans.get_identifier(), trans):
            transactions.append(trans)
            trans = generator.gen_transaction()
            i += 1
            if i == 1000000:
                break

        assert i == 1000000

    def test_positive_search_predecessor(self):
        tree = Tree()
        generator = Generator()
        inputs = []
        transactions = []
        in_sum = Decimal(0)

        generator.gen_genesis()

        for i in range(10):
            trans = generator.gen_transaction()
            transactions.append(trans)
            for entry in trans.get_outputs():
                inputs.append(entry)

            in_sum += trans.get_value()
            tree.add(trans.get_identifier(), trans)

        out_sum = in_sum - (2 * calculate_fee(in_sum))

        receiver_wallet = Wallet(int.to_bytes(1, 32, "big"), out_sum)

        trans_test = Transaction(inputs, outputs_helper(inputs, [receiver_wallet]), None)
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
        generator = Generator()
        inputs = []
        transactions = []
        in_sum = 0

        generator.gen_genesis()

        for i in range(10):
            trans = generator.gen_transaction()
            transactions.append(trans)
            for entry in trans.get_outputs():
                inputs.append(entry)

            in_sum += trans.get_value()
            tree.add(trans.get_identifier(), trans)

        # negative case
        transactions.pop()

        out_sum = in_sum - (2 * calculate_fee(in_sum))

        receiver_wallet = Wallet(int.to_bytes(1, 32, "big"), out_sum)

        trans_test = Transaction(inputs, outputs_helper(inputs, [receiver_wallet]), None)
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
        generator = Generator()

        generator.gen_genesis()
        trans = generator.gen_transaction()

        tree.add(trans.get_identifier(), trans)
        assert not tree.add(trans.get_identifier(), trans)

    def test_negative_search(self):
        """With range == 100000 this test takes ~ 10 seconds"""
        tree = Tree()
        generator = Generator()

        generator.gen_genesis()

        for i in range(100000):
            trans = generator.gen_transaction()
            assert tree.add(trans.get_identifier(), trans)

        for i in range(100000):
            trans = generator.gen_transaction()

            trans = tree.search(trans.get_identifier())
            assert trans is None

    # def test_multiple(self):
    #    """This test will take much time and ram!"""
    #    for i in range(10):
    #        self.test_positive_add_search_dict()
    #        self.test_positive_size()
    #        self.test_positive_search_predecessor()
    #        self.test_negative_add()
    #        self.test_negative_search()
    #        self.test_negative_search_predecessor()


if __name__ == "__main__":
    unittest.main()


