import logging
from copy import deepcopy
from abcnet.structures import ItemType
from abccore.DAG import *

logger = logging.getLogger(__name__)

class Tree:
    """This is the actual data structure to store the dag based on a prefix tree."""
    def __init__(self):
        # The tree and any node in it has per default 256 empty child seats to decrease search time.
        self.childs = [None]*256
        self.latest_checkpoint = None

        # save IDs of all previous checkpoints to have a line of trust
        self.list_of_checkpoints = list()

        # pending_acks and pending_txns will hold identifiers of those nodes, of which the parents are not in the Tree.
        # This will be used to set dependences with those parents as soon as they occur in a call of the add() function.
        self.pending_acks = dict()
        self.pending_txns = dict()

    def __contains__(self, item: Node) -> bool:
        """Uses the function search() to check if the identifier of the given Node :param item is in the Tree, and if
        so, it raises an Exception if the item differs from the Node in the Tree.
        """
        item_copy = self.search(item.get_identifier())
        if item_copy is not None:
            if item == item_copy.get_node():
                return True
            else:
                raise Exception("Identifier in use, but items are not equal.")

        return False

    def __iter__(self):
        """Makes the Tree iterable. First, all Nodes in the Tree will be added to a new field all_elements: set(), which
        is iterable in itself. Based on that, the function __next__() will then iterate over all Nodes. To reduce the
        memory fottprint, the field all_elements will be deleted after each iteration over all Nodes.
        """
        self.all_elements = self.get_all()
        self.max = len(self.all_elements)
        self.num = 0
        return self

    def __next__(self) -> 'TreeLeaf':
        """Iterates over all Nodes of the Tree, leveraging the field all_elements. After a complete iteration, the field
        all_elements will be deleted.
        """
        if self.num >= self.max:
            # delete the traces left from the loop operation
            self.all_elements = None  # makes sure that there is a field to delete in the enxt program step
            delattr(self, "all_elements")
            raise StopIteration

        self.num += 1
        return self.all_elements[self.num-1]

    def __delete(self, code) -> bool:
        """This function is not tested and in general shouldn't be used!
        Deletion of Nodes in the Tree is not anticipated. If called, this function searches for the TreeLeaf
        corresponding to :param code. For an index i, the TreeLeaf will saved in childs[i] of a TreeNode. The function
        sets the TreeNodes childs[i] to None, where the TreeLeaf would have been.
        """
        child = self.childs[code[0]]
        if child is None:
            return_value = False
        elif isinstance(child, TreeLeaf):
            self.childs[code[0]] = None
            return_value = True
        else:
            child: TreeNode
            return_value = child.__delete(code[1:len(code)])

        if not isinstance(self, TreeNode) and return_value:
            self.max -= 1

        return return_value

    def get_latest_checkpoint(self) -> Genesis:
        return self.latest_checkpoint

    def search_dependend_nodes(self, wallets: set(tuple())) -> set(tuple()):
        """For any representation of a Wallet contained in the set :param wallets, this function searches for all
        Transactions, which use that Wallet in its inputs. The function also adds all ACKs for these TXNs to the
        :return set of pairs (Node.identifier, Node.ItemType).
        """
        dependend_nodes = set()
        for pair in wallets:
            # For all representations of a Wallet, search for the TXN based on Wallet.origin.
            # pair: tuple(bytes, int)

            if isinstance(pair, Wallet):
                pair = [pair.get_origin(), pair.get_id()]

            tree_node = self.search(pair[0])
            if tree_node is not None:
                for t_node in tree_node.get_dependend_nodes():
                    # Add any Node d_node, which depends on the TXN tree_node and the Wallet representation

                    t_node: TreeLeaf
                    d_node = t_node.get_node()
                    if isinstance(d_node, Transaction):
                        # If d_node is Transaction, only add d_node to dependend_nodes if one of its inputs matches the
                        # current representation of a Wallet
                        for input_wallet in d_node.get_inputs():
                            if pair == (input_wallet.get_origin(), input_wallet.get_id()):
                                dependend_nodes.add(d_node)
                                break
                    elif isinstance(d_node, Checkpoint):
                        # If d_node is Checkpoint, we add it
                        dependend_nodes.add(t_node)
                    elif isinstance(d_node, Acknowledge):
                        # We need these ACKs to resend them after a ckpt was injected
                        dependend_nodes.add(d_node)

        # set outputs will be returned with all pairs (Node.Identifier, Node.ItemType) representing Nodes depending on
        # at least one Wallet in the parameter wallets. visited_nodes reduces runtime by skipping already visited nodes
        outputs = set()
        visited_nodes = dict()
        while len(dependend_nodes) > 0:
            # For any Node in dependend_nodes, search for its dependend Nodes and add them to dependend_nodes, if they
            # werent in the set any time before. Then, put the current Node in the outputs.

            dependend_node = dependend_nodes.pop()

            # Check if dependend_node is a TreeLeaf or a Node. In both cases, get the dependend Nodes.
            if isinstance(dependend_node, TreeLeaf):
                # set dependend_node to be the Node contained in the TreeLeaf
                my_dependend_nodes = dependend_node.get_dependend_nodes()
                dependend_node = dependend_node.get_node()

            else:
                my_dependend_nodes = self.search(dependend_node.get_identifier()).get_dependend_nodes()

            for dep_node in my_dependend_nodes:
                # Check for all TreeLeaf if they were in dependend_nodes before
                dep_node: TreeLeaf
                code = dep_node.get_node().get_identifier()
                if visited_nodes.get(code) is None:
                    # dep_node was not in the set before -> add it to the set
                    dependend_nodes.add(dep_node)
                    visited_nodes[code] = True

            # compute pair to add to outputs based on the ItemType of the current dependend_node
            if isinstance(dependend_node, Transaction):
                node_type = ItemType.TXN
            elif isinstance(dependend_node, Acknowledge):
                node_type = ItemType.ACK
            else:
                node_type = ItemType.CHP

            outputs.add((dependend_node.get_identifier(), node_type))

        return outputs  # { (Node.Identifier, Node.ItemType) }

    def search(self, code: bytes) -> "TreeLeaf":
        """The function :returns a TreeLeaf if there is one corresponding to the code, otherwise None.
        :param code: identifier of DAG.Node to be searched in the tree.
        """
        try:
            if self.childs[code[0]] is None:
                return None
            else:
                return self.childs[code[0]].search(code[1:len(code)])
        except IndexError:
            raise Exception(code)

    def add(self, code: bytes, node: Node) -> bool:
        """The function :returns True if it was able to add a DAG.Node to the tree, otherwise False.
        If successfull, the function also checks if there are Nodes in the Tree which depend on the new node. If so,
        the function set_dependencies() will be called.
        This function is overridden in TreeNode.
        :param code: identifier of DAG.Node to be added in the tree.
        :param node: DAG.Node to be added in the tree.
        """

        # search for the integer representation I of the first byte of code
        if code == b"":
            return False
        if self.childs[code[0]] is None:
            # insert new TreeLeaf for the node in childs[I]
            self.childs[code[0]] = TreeLeaf(self, code, node)
            return_value = True
        else:
            # go to the TreeNode located in childs[I] and try add() recursively for the code without its first byte
            return_value = self.childs[code[0]].add(code[1:len(code)], node)

        # After add() was completed successfully, try to set dependencies based on the new node.
        # If there are ACKs referencing this node, then call their function set_dependencies()
        pending_set = self.pending_acks.get(code)
        if return_value and pending_set is not None:
            logger.debug("Started adding dependencies of pending_acks")
            for entry in pending_set:
                pending_set: set
                self.search(entry).set_dependencies()

            self.pending_acks.pop(code)

        # Do the same with dependend TXNs as above
        pending_set = self.pending_txns.get(code)
        if return_value and pending_set is not None:
            logger.debug("Started adding dependencies of pending_txns")
            for entry in pending_set:
                pending_set: set
                self.search(entry).set_dependencies()

            self.pending_txns.pop(code)

        if return_value:
            if isinstance(node, Genesis) or isinstance(node, Checkpoint):
                self.latest_checkpoint = node
                self.list_of_checkpoints.append(node.get_identifier())

        return return_value

    def search_predecessors(self, code: bytes):  # not used anymore
        """This function returns a list of DAG.Node.
        :param code: Identifier of a DAG.Node. Its representation in the Tree will be searched and from there all direct
        predecessors of the DAG.Node will be searched returned.
        """
        input_node = self.search(code)
        output = []

        parents_dict = input_node.get_node().get_parents()
        for key in parents_dict.keys():
            output.append(self.search(key).get_node())

        return output

    def get_all(self) -> [Node]:
        """This method is used to save the entire tree. It will return a list containing every single DAG Node in the
        tree structure.
        """
        output = []
        for child in self.childs:
            if child is not None:
                output.extend(child.get_all())

        return output


class TreeNode(Tree):
    def __init__(self, parent: "TreeNode"):
        super().__init__()
        self.parent = parent

    def get_parent(self):
        return self.parent

    def add(self, code: bytes, node: Transaction) -> bool:
        """The add() function :return True if it was able to add a DAG.Node to the tree, otherwise False.
        This function overrides the original function in class Tree and is overridden in TreeLeaf.
        :param code: part of the identifier of DAG.Node to be searched in the tree.
        :param node: DAG.Node to be added in the tree.
        """
        if self.childs[code[0]] is None:
            self.childs[code[0]] = TreeLeaf(self, code, node)
            return True
        else:
            return self.childs[code[0]].add(code[1:len(code)], node)


class TreeLeaf(TreeNode):
    def __init__(self, parent: TreeNode, my_code: bytes, node: Node):
        """:param my_code: will be saved as self.remaining_code. It starts with the byte b used in parent s.t.
        self.parent.child[b] == self. This will be used if parent.add(b, node) maps another node to the same field
        child[b]. Further details are available in TreeLeaf.add(b, node) documentation.
        :param node: A DAG.Node to be saved. :param my_code is a suffix to node.identifier.
        """
        super().__init__(parent)
        self.remaining_code = my_code
        self.node = node
        self.dependend_nodes = set()
        self.set_dependencies()

    def set_dependencies(self):
        """This function adds the identifier of this Node to the dependend_nodes of its predecessors."""

        # traverse the tree from this TreeLeaf up to the root Tree, to be able to search for predecessors
        parent = self.get_parent()
        while isinstance(parent, TreeNode):
            parent = parent.get_parent()

        # only go on if the root can be reached
        if isinstance(parent, Tree):

            # get the list of nodes to search for based on the own ItemType
            inputs = []
            if isinstance(self.node, Checkpoint):
                logger.debug("Setting dependencies of a Checkpoint is not tested!")
                inputs = self.node.get_utxos()
                prev_ckpt = parent.search(self.node.get_origin())
                prev_ckpt.dependend_nodes.add(self)

            elif isinstance(self.node, Genesis):
                logger.debug("The Genesis doesn't depend on any other Nodes!")

            elif isinstance(self.node, Transaction):
                inputs = self.node.get_inputs()

            elif isinstance(self.node, Acknowledge):
                # in the case of an ACK, there are only two predecessors: prev_ack and txn_id
                try:
                    # if prev_ack is in the tree, add the identifier of this node to the prev_ack's dependend_nodes set
                    if self.node.get_prev_ack() is not None:
                        tree_node = parent.search(self.node.get_prev_ack())
                        if not isinstance(tree_node.get_node(), Genesis):
                            tree_node.dependend_nodes.add(self)

                except AttributeError:
                    logger.debug("Acknowledge caused AttributeError: Couldn't set dependency, there is a node missing in the "
                          "DAG! ")

                try:
                    # if txn_id is in the tree, add the identifier of this node to its dependend_nodes set
                    tree_node = parent.search(self.node.get_trans_id())
                    tree_node.dependend_nodes.add(self)

                except AttributeError:
                    # in this case, the TXN of txn_id may be still in the pending_transactions list of the agent,
                    # therefor the identifier of this node will be added to the pending_acks

                    pending_set = parent.pending_acks.get(self.node.get_trans_id())
                    if pending_set is None:
                        parent.pending_acks[self.node.get_trans_id()] = {self.node.get_identifier()}
                    else:
                        pending_set: set
                        parent.pending_acks.pop(self.node.get_trans_id())
                        pending_set.add(self.get_node().get_identifier())
                        parent.pending_acks[self.node.get_trans_id()] = pending_set
                    logger.debug("Added an Ack to the pending_acks, the corresponding TXN is missing.")

            # If this node is not an ACK and not a Genesis, then it has a (non empty) inputs list
            for input_wallet in inputs:
                # for all Wallets in inputs, add this identifier to the depending_nodes of the corresponding TXNs

                input_wallet: Wallet
                try:
                    tree_node = parent.search(input_wallet.get_origin())
                    tree_node.dependend_nodes.add(self)
                except AttributeError:
                    # In this case, the TXN can't be in the pending_transaction, since then this node wouldn't have been
                    # added to the tree, but the missing "TXN" may be a Checkpoint which is only added after this node
                    # was added to the tree. This happens on each call of function load_data() in the agent.
                    logger.debug("Transaction caused: Couldn't set dependency, there is a node missing in the DAG! ",
                          "Is this TXN dependend on a checkpoint?")

                    # In this case, this identifier is added to pending_txns to set the correct dependencies later.
                    pending_set = parent.pending_txns.get(self.node.get_identifier())
                    if pending_set is None:
                        parent.pending_txns[self.node.get_identifier()] = {self.node.get_identifier()}
                    else:
                        pending_set: set
                        parent.pending_txns.pop(self.node.get_identifier())
                        pending_set.add(self.get_node().get_identifier())
                        parent.pending_txns[self.node.get_identifier()] = pending_set
                    logger.debug("Added a TXN to the pending_txns, the corresponding TXN is missing.")

    def get_dependend_nodes(self) -> set('TreeLeaf'):
        return self.dependend_nodes

    def get_node(self) -> "Node":
        return self.node

    def add(self, code: bytes, node: Node) -> bool:
        """This function overrides the parent function in class TreeNode.
        If there is already a node in the tree with the same identifier, the function will :return False,
        otherwise it creates a TreeNode in its place of its parent node, append itself to the newly created TreeNode,
        also appends a new LeafNode for the new DAG.Node and then :returns True.
        :param code: part of the identifier of DAG.Node to be searched in the tree.
        :param node: DAG.Node to be added in the tree.
        """
        if self.node.identifier == node.identifier:
            return False
        else:
            # the current parent will become this TreeLeafs 'grandparent'
            grandparent = self.get_parent()

            # create a new TreeNode with this TreeLeafs 'grandparent' as parameter, such that the parent of the new
            # TreeNode is this TreeLeafs 'grandparent'.
            self.parent = TreeNode(grandparent)

            # the new TreeNode will then be set as child of this TreeLeafs 'grandparent' in place of this TreeLeaf.
            grandparent.childs[self.remaining_code[0]] = self.parent

            # This TreeLeaf will be added as child to the new TreeNode, such that self.parent.parent = 'grandparent'
            self.parent.childs[self.remaining_code[1]] = self

            # This TreeLeafs remaining_code will be shortened accoring to the change of relative position in the tree
            self.remaining_code = self.remaining_code[1:len(self.remaining_code)]

            # The node to be added will be added as a child of the new TreeNode, this TreeLeafs new parent
            self.parent.add(code, node)

            return True

    def search(self, code: bytes) -> "TreeLeaf":
        """The function :returns a node from the tree if there is one corresponding to the code, otherwise None.
        :param code: identifier of DAG.Node to be searched in the tree.
        """
        # only return this TreeLeaf if code matches remaining_code, meaning that the initial code matches the identifier
        # of the Node contained in this TreeLeaf.
        mycode = self.remaining_code[1:len(self.remaining_code)]
        if mycode == code:
            return self
        else:
            return None

    def get_all(self) -> [Node]:
        """This method is used to save the entire tree. It will return a list containing the DAG Node of this TreeLeaf.
        """
        return [self.node]
