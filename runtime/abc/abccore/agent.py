import time
from datetime import datetime
from random import random

import time
from typing import Set

from abccore.constants import RESEND_PENDING_ITEMS_TIME
from abcnet.timer import StopTimer, SimpleTimer

from abccore.prefix_tree import TreeLeaf
from abccore.checkpoint_service import CheckpointServiceMock
from abccore.agent_data import *
from abccore.agent_msg_handler import AgentMessageHandler
from abccore.agent_items_parser import AgentItemsParser
from abccore.network_datastructures import (
    NetTransaction,
    NetAcknowledgement,
    reduce_ttl,
    NetUSPWR,
)

from abcnet.structures import ItemType
from abcnet.services import ChannelService

from abccore.zmq_server import LocalMessageHandler
from abccore.agent_interface import AgentInterface

logger = logging.getLogger(__name__)


class Agent(AgentMessageHandler, LocalMessageHandler, AgentInterface):
    """
    Core Class of the abccore module. This class is responsible for saving the whole data including DAG,
    handling the network queues and sending new items to the network. Most of the data is stored in an object
    of the class 'AgentData'.
    """

    interesting_item_types = [
        ItemType.ACK,
        ItemType.TXN,
        ItemType.UNSPENT_WALLET_COLLECTION,
    ]

    def __init__(
            self,
            private_keys: Union[None, Ed25519PrivateKey, List[Ed25519PrivateKey]] = None,
            checkpoint_service: CheckpointService = None,
            filename="genesis.db",
            bot_mode: bool = False
    ):
        """
        Initializes all objects of the agent.
        :param private_key: Directly adds the given key to the keyset to instantly get access to the related wallets. Primarely used for the genesis.
        :param checkpoint_service: Pointer to the checkpoint service.
        """
        item_parser = AgentItemsParser()

        super(Agent, self).__init__()  # calls init of AgentMessageHandler
        super(AgentMessageHandler, self).__init__(
            Agent.interesting_item_types, item_parser
        )  # calls init of LocalMessageHandler
        super(AgentInterface, self).__init__()  # should call the init
        #  of AbstractItemHandler of AgentMessageHandler
        self.checkpoint_service = None
        self.a_data = AgentData(private_keys)

        self.check_out = set()
        self.fetch_item_set = set()
        self.item_set = set()

        self.pending_uspwr: NetUSPWR = None
        self.pending_uspwr_timeout: SimpleTimer = None

        self.orphaned_nodes: Dict[bytes, Dict[bytes, Node]] = dict()
        self.gen_prev_orphan_parents = set()

        self.pending_transactions = dict()
        self.resend_pending_txns_time_stamp = time.time()
        self.set_resend_pending_items_time()

        self.load_data(filename=filename)
        if not self.a_data.keyset:
            self.add_keypair()

        if checkpoint_service is None:
            logger.info(
                "Created a checkpoint mock service that delivers us correct information regarding stake"
                " based on the current dag."
            )
            checkpoint_service = CheckpointServiceMock(self.a_data.tree)
        # for pb_key in self.get_pub_key_bytes():
        #     for wallet in checkpoint_service.owned_wallets(pb_key):
        #         self.a_data.balance.append(wallet)

        self.checkpoint_service: CheckpointService = checkpoint_service
        self.a_data.stake_threshold = checkpoint_service.stake_sum() * (
                Decimal(2) / Decimal(3)
        )
        self.missing_txn_resend_timer = SimpleTimer(constants.MISSING_TXN_RESEND_TIMEOUT)

        self.bot_mode = bot_mode
        if bot_mode:
            self.auto_send_timer = SimpleTimer(10)
            self.auto_send_count = 0

    def save_data(
            self,
            user_password=bytes("ThisNeedsToBeAdded!", "UTF-8"),
            filename="abc_save.db"
    ):
        """Calls the save handler to save the agent tree."""
        # TODO user password

        # Flatten the orphaned dictionary to a dictionary of bytes to list of nodes:
        flattened_orphans = dict()
        for missing_parent, orphaned in self.orphaned_nodes.items():
            flattened_orphans[missing_parent] = list()
            for o in orphaned.values():
                flattened_orphans[missing_parent].append(o)

        return self.a_data.save_data(
            self.pending_transactions,
            flattened_orphans,
            user_password,
            filename,
            self.checkpoint_service
        )

    def __auto_send_money(self):
        logger.debug("Start automated Transaction generation from me to me, like as a present, but for the validators...")
        balance = Decimal(0)
        for wallet in self.a_data.balance:
            balance += wallet.get_value()

        while balance >= Decimal("0.4"):
            for wallet in self.a_data.balance:
                if wallet.get_value() >= Decimal("9.1"):
                    self.__send_money(wallet.get_pk(), Decimal("4.9"), wallet.get_pk())
                    break

                elif wallet.get_value() >= Decimal("4.5"):
                    self.__send_money(wallet.get_pk(), Decimal("2.2"), wallet.get_pk())
                    break

                elif wallet.get_value() >= Decimal("2.2"):
                    self.__send_money(wallet.get_pk(), Decimal("1"), wallet.get_pk())
                    break

                elif wallet.get_value() > Decimal("1"):
                    self.__send_money(wallet.get_pk(), Decimal("0.4"), wallet.get_pk())
                    break

                elif wallet.get_value() > Decimal("0.4"):
                    self.__send_money(wallet.get_pk(), Decimal("0.1"), wallet.get_pk())
                    break

                else:
                    self.__send_money(wallet.get_pk(), balance - Decimal("0.2"), wallet.get_pk())

            balance = Decimal(0)
            for wallet in self.a_data.balance:
                balance += wallet.get_value()

    def load_data(self, user_password=None, filename="abc_save.db") -> bool:
        """Calls the save handler to load the agent tree.
        :returns False if unsuccessful.
        """
        args = self.a_data.load_data(user_password, filename, self.checkpoint_service)
        unspent_wallet_set = args[0]
        if not filename == "genesis.db":
            self.pending_transactions = args[1]

            # check for Wallets in balance that have been spent in pending TXNs
            pending_keys = args[1].keys()
            balance = deepcopy(self.a_data.balance)
            for txn_key in pending_keys:
                pending_trans = self.pending_transactions.get(txn_key)[0]
                pending_trans: Transaction

                for balance_wallet in balance:
                    if balance_wallet in pending_trans.get_inputs():
                        self.a_data.balance.remove(balance_wallet)

            # Set the orphaned nodes to an empty dict no matter if the loading succeeds:
            self.orphaned_nodes: Dict[bytes, Dict[bytes, Node]] = dict()

            # De-flatten the orphans list to dictionary instead of node list:
            orphans_flatten: Dict[bytes, List[Node]] = args[2]
            if orphans_flatten is None:
                logger.error("Agent save_handler loaded with orphan pool=None.", exc_info=True)
            else:
                for missing_id, node_list in orphans_flatten.items():
                    orphans: Dict[bytes, Node] = dict()
                    for n in node_list:
                        orphans[n.get_identifier()] = n
                    self.orphaned_nodes[missing_id] = orphans

        for node in args[-1]:
            self.fetch_item_set.add(node)

        if unspent_wallet_set is not None:
            request = NetUSPWR(unspent_wallet_set, is_req=1)
            self.set_uspwr(request)
            return True
        else:
            return False

    def set_uspwr(self, uspwr_request: NetUSPWR):
        self.pending_uspwr = uspwr_request
        self.pending_uspwr_timeout = SimpleTimer(constants.USPWR_LATE_SEND_TIMEOUT, start=True)

    def __send_money(self, recipient, value, validator):
        """Send some money to one specific recipient
        :param recipient: public key of the recipient
        :param value: amount of money one wants to send
        :param validator: public key of the validator
        """

        logger.info(
            "INITIALIZED TRANSACTION:  value - "
            + str(value)
            + "; recipient - "
            + recipient.hex()
            + "; validator - "
            + validator.hex()
        )

        transaction = self.a_data.send_money(recipient, value, validator)
        if transaction is not None:
            self.__add_transaction(transaction)
            net_txn = NetTransaction(transaction)
            self.check_out.add(net_txn)
            # save_handler.update_unconfirmed(
            #     {transaction.get_identifier(): [transaction, Decimal(0)]}
            # )

            # self.pending_transactions[transaction.get_identifier()] = [
            #     transaction,
            #     Decimal(0),
            # ]

            # if self.a_data.validate_trans(transaction):
            #     self.__acknowledge(transaction)

            logger.info(
                "CREATED TRANSACTION, ID: %s", transaction.get_identifier().hex()
            )

    def __acknowledge(self, transaction) -> bool:
        """Function to acknowledge a new transaction. It calls AgentData.acknowledge() to get an ACK for every own key,
        processes each ACK in __add_acknowledgement() and adds each ACK as NetAcknowledgement to the check_out list.
        :param transaction: The transaction that will be acknowledged.
        :returns False if unsuccessfull.
        """
        acks = self.a_data.acknowledge(transaction)
        return_value = True

        for ack in acks:
            if not self.__add_acknowledgement(ack):
                return_value = False
            self.check_out.add(NetAcknowledgement(ack))

        self.save_data()

        if len(acks) > 0 and return_value:
            return return_value

        return False

    def inject_checkpoint(self, checkpoint: Checkpoint):
        self.switch_to_ckpt(checkpoint)
        self.a_data.stake_threshold = checkpoint.total_stake * (Decimal(2) / Decimal(3))
        # self.a_data.balance.clear()
        # self.recalc_ownership(checkpoint)
        # self.__check_and_register_ownership(checkpoint)

    def assign_validator(self, validator):
        """
        Forwards the assign_validator request to the AgentData class. Assigns the specified validator for following transactions.
        :param validator: public key of the validator which shall be assigned
        """
        self.a_data.assign_validator(validator)

    def add_txn_to_fetch_list(self, item_id):
        """
        Adds a transaction to the fetch_list. This enables the checkpoint service the opportunity to request transactions from the network.
        :param item_id: id of the requested item in bytes.
        """
        if isinstance(item_id, bytes):
            self.fetch_item_set.add((ItemType.TXN, item_id.hex()))

    # above function changed to take list of bytes(transaction ids).
    # def add_txn_to_fetch_list(self, item_ids: list[bytes]):
    #     for item_id in item_ids:
    #         if isinstance(item_id, bytes):
    #             self.fetch_item_set.append(ItemType.TXN, item_id)

    def add_keypair(self):
        """Adds a new random generated keypair to the keyset"""
        self.a_data.add_keypair()

    def add_pregenerated_keypair(
            self, key: Ed25519PrivateKey, search_tree_for_now_owned=False
    ):
        """
        Adds a new pregenerated keypair to the keyset and flags it as new key_to_use.
        :param key: Ed25519PrivateKey, which shall be included into the key list
        :param search_tree_for_now_owned: flags, if the DAG shall be searched for now owned wallets
        """
        self.a_data.add_pregenerated_keypair(key, search_tree_for_now_owned)

    def is_my_key(self, pb_key) -> bool:
        """
        Checks, if the mentioned public key is owned by this entity or not. This may be used to update balance or stake.
        :param pb_key: bytes encoded public key
        :return: boolean
        """
        return self.a_data.is_my_key(pb_key)

    def get_keys(self) -> List[Ed25519PrivateKey]:
        """Returns the list of keys owned by this agent"""
        return self.a_data.get_keys()

    def get_pub_keys(self) -> list:
        """:return: List of public keys related to this agent"""
        return self.a_data.get_pub_keys()

    def get_pub_key_bytes(self):
        """:return: List of public keys related to this agent encoded as bytes"""
        return self.a_data.get_pub_key_bytes()

    def get_stake(self):
        """
        :return: Returns the stake related to the keys owned by this entity.
        """
        stake = Decimal(0)
        for key in self.get_pub_key_bytes():
            stake += self.checkpoint_service.delegated_stake(key)
        return stake

    def get_agent(self):
        """
        :return: Returns this entity, required by the interface
        """
        return self

    def get_prefix_tree(self):
        """
        :return: Returns the prefix_tree including all transactions and acknowledgements
        """
        return self.a_data.tree

    def get_validator(self):
        """
        :return: Returns a validators public key  to handle a transaction
        """
        return self.a_data.get_validator()

    def add_validator(self, validator):
        """
        Adds a validator to the known validators.
        :param validator: public key of the validator which is added to the known validators
        """
        self.a_data.add_validator(validator)

    def validate_signature(self, node) -> bool:
        """
        Validates a signature of a transaction or an acknowledgement.
        :param node: The node, which signatures should be checked
        :return: True iff the transaction is valid
        """
        return self.a_data.validate_signature(node)

    def switch_to_ckpt(self, ckpt: Checkpoint):
        """This method will handle the transition from the current dag to a new checkpoint. Most of that is done in the
        function transform_dag() of AgentData, called here. For the Agent, the transition includes reevaluating all ACKs
        which were received for the contents of the new pending_transactions received from transform_dag().
        """
        # new_save_name = "abc_save" + datetime.today().strftime('%Y-%m-%d-%H_%M_%S') + ".db"
        # self.save_data(filename=new_save_name)
        logger.debug("PRE  CHECKPOINT")
        logger.debug("PRE  CHECKPOINT")
        logger.debug("PRE  CHECKPOINT")
        logger.debug("PRE  CHECKPOINT")
        logger.debug("PRE  CHECKPOINT")
        for wallet in self.a_data.balance:
            logger.debug(wallet)
        pendings = self.a_data.transform_dag(ckpt, self.pending_transactions)
        # pendings = [ pending_transactions: dict, pending_acks: set ]
        for wallet in self.a_data.balance:
            logger.debug(wallet)
        logger.debug("POST  CHECKPOINT")
        logger.debug("POST  CHECKPOINT")
        logger.debug("POST  CHECKPOINT")
        logger.debug("POST  CHECKPOINT")
        logger.debug("POST  CHECKPOINT")

        self.__remove_dead_orphans()

        self.pending_transactions.clear()
        self.checkpoint_service.set_checkpoint(self.a_data.tree)

        for txn in pendings[0]:
            self.__add_transaction(txn)

        for ack in pendings[1]:
            self.__add_acknowledgement(ack)  # probably not needed
            pass

        for txn_id in pendings[2]:
            self.fetch_item_set.add((ItemType.TXN, txn_id.hex()))

        self.save_data()

    def __handle_txn_request(self, txn_id):
        """Search in DAG for transaction with ID :param txn:id and prepare to broadcast it over the network"""
        req_trans = self.search_item(ItemType.TXN, txn_id)
        if req_trans is not None:
            net_txn = NetTransaction(req_trans)
            self.item_set.add(net_txn)

    def __handle_ack_request(self, ack_id):
        """Search in DAG for acknowledge with ID :param ack_id and prepare to broadcast it over the network"""
        ack = self.search_item(ItemType.ACK, ack_id)
        if ack is not None:
            net_ack = NetAcknowledgement(ack)
            self.item_set.add(net_ack)  # TODO is ack of type "Acknowledgement"?

    def __handle_uspwr_request(self, uspwr_id):
        """
        Handles an incoming request for uspwr with it uspwr_id. If uspwr_id is known the corresponding item is added to item_set.
        :param uspwr_id: ID of the USPWR which is requested.
        """
        # uspwr = self.uspwr_dict.get(uspwr_id)
        # if uspwr is not None:
        #     self.item_set.add(uspwr)
        logger.warning("Received item request for USPWR.")

    def __handle_unspnt_wllt_objs(self, item_content: NetUSPWR):
        """
        Handles unspent wallet requests dependent on the flag 'is_req'. Requests (is_req=1) are handled different than answers (is_req=0).
        If the content is a request a new answer USPWR is created and added to the checklist for the network.
        If the content is an answer all given unspent_wallets are searched in the local datastructure and asked from the network if the items are unkown.
        :param item_content: unspent wallet request
        """
        # item_content = { (wallet.origin, wallet.id: bytes) }
        # TODO check if the items are already included in last checkpoint or not
        # if yes -> proceed as already implemented
        # if no -> send last checkpoint and use unspend_walltes (utxos) of the checkpoint instead
        answer_from_tree = self.a_data.tree.search_dependend_nodes(
            item_content.unspent_wallet_set
        )
        # answer_from_tree = {ID: bytes, ItemType: hex), ... }

        for item_id, item_type in answer_from_tree:
            if item_type == ItemType.ACK:
                n = self.a_data.tree.search(item_id).node
                self.check_out.add(NetAcknowledgement(n))
            elif item_type == ItemType.TXN:
                n = self.a_data.tree.search(item_id).node
                self.check_out.add(NetTransaction(n))
            else:
                logger.warning("Found nodes in DAG that are requested in a NetUSPWR"
                               " but cannot it cannot be sent. Itemtype: %s, item id: %s", item_type, item_id)

    def __retry_missing_txn_request(self):
        """This method will be called every one in a while to ask again for missing Transactions. For this, all keys
        of the dict orphaned_nodes will be added as TXN request to the fetch_item_set.
        """
        if len(self.orphaned_nodes) != 0:
            for txn_bytes in self.orphaned_nodes.keys():
                self.fetch_item_set.add((ItemType.TXN, txn_bytes.hex()))
            logger.info("Added missing TXNs to fetch_item_set, again.")

    def set_resend_pending_items_time(self):
        """ Sets the randomized time for repeating pending items """
        self.resend_pending_items_time = RESEND_PENDING_ITEMS_TIME + RESEND_PENDING_ITEMS_TIME * random()

    def resend_pending_items(self):
        """
        Adds all pending transactions to the checklist again. This prevents transactions to be unconfirmed for ever.
        """
        if len(self.pending_transactions) > 0:
            for txn, stake in self.pending_transactions.values():
                self.check_out.add(NetTransaction(txn))
            logger.info("Pending items have been added to the outgoing checklist.")
        else:
            logger.info("Pending items list is empty.")

        self.set_resend_pending_items_time()
        self.resend_pending_txns_time_stamp = time.time()

        logger.info(
            "Next pending items will be send in "
            + str(self.resend_pending_items_time)
            + "s."
        )

    def perform_maintenance(self, cs: ChannelService):
        """
        This method is repeatedly called by the network and service management of the abcnet module.
        perform_maintenance empties the opperating queues, handles the included items and sends new checklists, requests and items to the network.
        :param cs: The ChannelService which is responsible for the communication to the network
        """

        logger.debug("PERFORM MAINTENANCE - START")

        super().perform_maintenance(cs)
        ch_out = cs.broadcast_channel()
        if (
                time.time() - self.resend_pending_txns_time_stamp
                > self.resend_pending_items_time
        ):
            self.resend_pending_items()

        if self.pending_uspwr_timeout is not None and self.pending_uspwr_timeout.check():
            self.pending_uspwr_timeout = None
            if self.pending_uspwr is not None:
                cs.broadcast_channel().items([self.pending_uspwr])
                self.pending_uspwr = None

        for item_bytes in self.input_queue:
            item = self.input_queue[item_bytes]
            item_type = item[0]
            item_content = item[1]

            if item_type == ItemType.UNSPENT_WALLET_COLLECTION:
                item_content: NetUSPWR
                self.__handle_unspnt_wllt_objs(item_content)

            elif item_type == ItemType.TXN:
                item_content: NetTransaction
                if self.__add_transaction(item_content.txn):
                    logger.info(
                        "Handled Transaction, ID:"
                        + item_content.id.hex()
                    )
                else:
                    logger.info(
                        "New transaction has been declined, ID: "
                        + item_content.id.hex()
                    )
            elif item_type == ItemType.ACK:  # item_type == ItemType.ACK
                item_content: NetAcknowledgement
                if self.__add_acknowledgement(item_content.ack):
                    self.a_data.add_to_save(item_content.ack)
                    logger.info(
                        "New acknowledgement added to local DAG, ID:"
                        + str(item_content.id.hex())
                    )
                else:
                    logger.info(
                        "New acknowledgement has been declined, ID: "
                        + str(item_content.id.hex())
                    )

        for (item_type, item_bytes) in self.request_queue:
            item_qualifier_bytes = bytes.fromhex(item_bytes)
            if item_type == ItemType.TXN:
                self.__handle_txn_request(item_qualifier_bytes)
            elif item_type == ItemType.ACK:
                self.__handle_ack_request(item_qualifier_bytes)
            elif item_type == ItemType.UNSPENT_WALLET_COLLECTION:
                self.__handle_uspwr_request(item_qualifier_bytes)
            else:
                logger.warning("Received request for unrecognized item type: " + str(item_type))

        for (item_type, item_bytes_hex) in self.checklist_queue:
            item_bytes = bytes.fromhex(item_bytes_hex)
            if item_type == ItemType.UNSPENT_WALLET_COLLECTION:
                # if item_bytes not in self.uspwr_dict:
                #     self.fetch_item_set.add((item_type, item_bytes_hex))
                logger.warning("Someone is sending checklist of unspent wallet collection requests.")
            elif item_type == ItemType.ACK:
                if self.search_item(item_type, item_bytes) is None:
                    # TODO look into the orphan pool: if it is there we dont want it again.
                    self.fetch_item_set.add((item_type, item_bytes_hex))
            elif item_type == ItemType.TXN:
                # If the item in the checklist is already confirmed, directly send ACKs from the DAG in a checklist as answer
                content: TreeLeaf = self.a_data.tree.search(item_bytes)
                if content is not None:
                    for tl in content.dependend_nodes:
                        if (
                                isinstance(tl.node, Acknowledge)
                                and tl.node.transaction == item_bytes
                        ):
                            self.check_out.add(NetAcknowledgement(tl.node))
                else:
                    self.fetch_item_set.add((item_type, item_bytes_hex))

        if not self.check_out == set():
            send_set = reduce_ttl(self.check_out)
            if not send_set == set():
                ch_out.checklist(send_set)
                logger.info(
                    "Checklist broadcasted to network with following new items: "
                    + "\n\t- ".join(item.id.hex() for item in send_set)
                )

        if self.bot_mode:
            if self.auto_send_count < 50 and self.auto_send_timer():
                self.__auto_send_money()
                self.auto_send_count += 1
            elif self.auto_send_count >= 50 and self.auto_send_timer():
                logger.debug("Done with sending automatically!")

        if self.missing_txn_resend_timer():
            # use this timer to regularly save
            self.save_data()

            # regularly ask for missing TXNs
            self.__retry_missing_txn_request()

        if not self.fetch_item_set == set():
            logger.debug("fetching items")
            ch_out.fetch_items(self.fetch_item_set)
            logger.info(
                "Fetchlist broadcasted to network with following requested items: "
                + "\n\t- ".join(item[1] for item in self.fetch_item_set)
            )
            self.fetch_item_set = set()

        if not self.item_set == set():
            ch_out.items(self.item_set)
            logger.info(
                "Itemlist broadcasted to network with following item content: "
                + "\n\t- ".join(item.id.hex() for item in self.item_set)
            )
            self.item_set = set()

        self.input_queue.clear()
        self.request_queue.clear()
        self.checklist_queue.clear()
        self.output_queue.clear()

        logger.debug("PERFORM MAINTENANCE - END")

    def __add_transaction(self, txn: Transaction) -> bool:
        """This function is called by the perform_maintanance() method to handle an incoming Transaction :param txn.
        At first it is checked if the txn is already in the dag or if the identifier is a key to a value in the dict
        pending_transactions. In both cases, the function :returns True, indicating that everything was as expected.
        If not, then the txn is completely new to the agent and it will be added to the dict pending_transactions as
        value '[txn, Decimal(0)]' for the key 'txn.identifier'. If the validation of the txn succeeds, it will be
        acknowledged (there, the stake will be updated).
        Then, it will be checked if there are depending Acknowledges in the set orphaned_nodes, which then would be
        processed.
        :param txn: Transaction received from the network.
        :returns False if not successful.
        """
        if not self.validate_signature(txn):
            logger.error("Signature of received Transaction not valid")
            return False

        # The `valid` and `signed` txn that may be using wallets in my balance.
        # Remove those wallets:
        self.register_balance_lost(txn)

        # Check if txn is in dag
        data_check = self.a_data.tree.search(txn.get_identifier())
        if data_check is not None:
            logger.info("Identifier already in tree!")
            return data_check.get_node() == txn

        # Check if the inputs are all unspent
        for in_wallet in txn.get_inputs():
            in_wallet: Wallet
            parent = in_wallet.get_origin()
            input_txn = self.a_data.tree.search(parent)
            if input_txn is None:
                # Cannot find the txn for the input
                continue
            node: Union[Genesis, Transaction] = input_txn.get_node()
            out_wallet = node.outputs[in_wallet.id]
            out_wallet: Wallet
            if out_wallet.state == State.SPENT:
                logger.info("Found a txn %s that is using spend outputs. Discarding it...", txn.get_identifier().hex())
                return False

        # Check if the parents of TXN are represented in local tree
        is_orphan = False
        for in_wallet in txn.get_inputs():
            parent = in_wallet.get_origin()
            if self.a_data.tree.search(parent) is None:
                orphans = self.orphaned_nodes.get(parent)
                if orphans is None:
                    orphans = dict()
                    self.orphaned_nodes[parent] = orphans
                orphans[txn.get_identifier()] = txn
                self.fetch_item_set.add((ItemType.TXN, parent.hex()))
                is_orphan = True

        # check if this TXN was requested in the latest ckpt injection
        if self.__is_wanted_txn(txn):
            return True

        if not is_orphan:
            pending_trans = self.pending_transactions.get(txn.get_identifier())
            # pending_transactions only holds TXNs that are known but not confirmed
            return_value = True

            if pending_trans is None:
                save_handler.update_unconfirmed(
                    {txn.get_identifier(): [txn, Decimal(0)]}
                )
                self.pending_transactions[txn.get_identifier()] = [txn, Decimal(0)]

                if self.a_data.validate_trans(txn):
                    self.__acknowledge(txn)

                logger.info("Added new Transaction to pending_transactions, ID: %s", txn.get_identifier().hex())

                self.__try_freeing_orphans(txn)
            else:
                logger.info("Transaction is already in pending_transactions, ID: %s", txn.get_identifier().hex())
                return_value = False

            return return_value
        else:  # is_orphan
            logger.info("Added a TXN to the orphanage")
            return False

    def __add_acknowledgement(self, ack: Acknowledge) -> bool:
        """This function is called by the perform_maintenance() method to handle an incoming Acknowledge :param ack.
        If the transaction related to this ack is not known, a txn request is send and the value [None, stake] will be
        added to the dict pending_transactions for the key 'ack.get_transaction()' which is the txn.identifier.
        If the txn is known, the stake in the dict will be updated and checked if the txn is now confirmed.
        :returns False if not successful.
        """
        if not self.validate_signature(ack):
            logger.error("Signature of received Acknowledge not valid")
            return False

        # if ack.prev_ack is not None:
        #     prev_ack = self.search_item(ItemType.ACK, ack.prev_ack)
        #     # if prev_ack is None:
        #     #     logger.info("Declined ack because its parent was not found in the dag: %s", ack)
        #     # return False

        #     try:
        #         self.a_data.validate_ack_chain(ack, prev_ack)
        #     except ValueError as e:
        #         if (
        #             self.a_data.last_acks[ack.pb_key]
        #             == self.a_data.tree.get_latest_checkpoint()
        #         ):
        #             ack.prev_ack = self.a_data.tree.get_latest_checkpoint()
        #             logger.info("Changed last_ack of this to be the latest checkpoint")
        #         else:
        #             logger.info("Declined ack because %s. \nAck: %s", e, ack)
        #             return False

        # Check if ack is in dag
        # Sanity check because if the identifier are equal the ack content should be equal
        data_check = self.a_data.tree.search(ack.get_identifier())
        if data_check is not None:
            if data_check.get_node() != ack:
                logger.error(
                    "Found a different ack in the dag with the same id.\nAck in dag: %s\nAck from network: %s",
                    data_check.get_node(),
                    ack,
                )
                return False
            else:
                logger.info("Ack already in tree!")
            return False

        # Check if trans is in dag
        data_check = self.a_data.tree.search(ack.get_trans_id())
        if data_check is not None:
            self.a_data.tree.add(ack.get_identifier(), ack)
            self.a_data.add_to_save(ack)
            return True

        pending_trans = self.pending_transactions.get(ack.get_trans_id())

        if pending_trans is None:
            orphans = self.orphaned_nodes.get(ack.get_trans_id())
            if orphans is None:
                orphans = dict()
                self.orphaned_nodes[ack.get_trans_id()] = orphans
            orphans[ack.get_identifier()] = ack
            self.fetch_item_set.add((ItemType.TXN, ack.get_trans_id().hex()))
            logger.warning("Ack %s was put into the orphan pool.", ack)
            return True
        else:
            stake = pending_trans[1]
            self.a_data.tree.add(ack.get_identifier(), ack)
            self.a_data.add_to_save(ack)

            (pk, _) = ack.get_signature()
            ack_stake = self.checkpoint_service.delegated_stake(pk)
            stake += ack_stake
            logger.info(
                "Received an ack for transaction with %s stake. The transaction is now validated by %s stake.",
                ack_stake,
                stake,
            )

            self.pending_transactions.update(
                {ack.get_trans_id(): [pending_trans[0], stake]}
            )

            if stake >= self.a_data.stake_threshold:
                # TXN is known and has enough stake to be confirmed
                self.__add_confirmed_trans(pending_trans[0])
            return True

    def __check_and_register_ownership(self, node: Node):
        self.a_data.check_and_register_ownership(node)

    def __add_confirmed_trans(self, transaction: Transaction):
        """Function will be called if either an acknowledge or a transaction is received and confirmed. This function
        will delete the record of the transaction in the list pending_transactions and add the transaction to the local
        dag. After this, the function checks if the new transaction gives money or stake to the agent.
        Then the dict orphaned_nodes will be checked if there are depending Nodes in it, which then will be processed.
        :param transaction: This is the newly confirmed transaction.
        """
        self.pending_transactions.pop(transaction.get_identifier())
        self.a_data.tree.add(transaction.get_identifier(), transaction)

        logger.info(
            "Removed "
            + str(transaction)
            + " from list pending_trans and added to tree."
        )

        self.__check_and_register_ownership(transaction)

        for wallet in transaction.get_inputs():  # Mark wallets as SPENT.
            try:
                check_wallet = (
                    self.a_data.tree.search(wallet.get_origin())
                        .get_node()
                        .get_outputs()[wallet.get_id()]
                )
                check_wallet.set_state(State.SPENT)
                wallet.set_state(State.SPENT)
                self.a_data.update_wallet(check_wallet)
            except AttributeError:
                logger.debug("Something went terribly wrong!")
        try:
            orphans: Dict[bytes, Node] = self.orphaned_nodes.pop(transaction.get_identifier())
            if orphans is not None:
                for node in orphans.values():
                    if isinstance(node, Acknowledge):
                        self.__add_acknowledgement(node)
                    elif isinstance(node, Transaction):
                        self.__add_transaction(node)
                logger.info(
                    "By confirming txn %s,  freed %d many Nodes from the orphanage.",
                    transaction,
                    len(orphans),
                )
            self.save_data()
        except KeyError:
            logger.info(
                "By confirming txn %s, no nodes were freed from orphanage.", transaction
            )

        self.a_data.add_to_save(transaction)

    @staticmethod
    def check_item_type_matches(item_type: ItemType, node: Node):
        if item_type == ItemType.TXN:
            return isinstance(node, Transaction)
        elif item_type == ItemType.ACK:
            return isinstance(node, Acknowledge)
        elif item_type == ItemType.CHP:
            return isinstance(node, Checkpoint)
        elif item_type == ItemType.UNSPENT_WALLET_COLLECTION:
            return False

    def search_item(self, item_type, item_id):
        """
        Searches in the prefix tree data structure for the given object. If no result is found it returns None.
        :param item_type: Item type of the item which is searched. Itemtypes are defined in abcnet.structures
        :param item_id: Item ID of the item which is searched
        :return: The searched item including its content. If the item can't be found it returns None
        """
        lf = self.a_data.tree.search(item_id)
        if lf is not None:
            node = lf.get_node()
            if not Agent.check_item_type_matches(item_type, node):
                logger.error(f"Received search for the wrong item type={item_type}. "
                             f"Found node in the DAG: {node.__class__}")
                return None
            return lf.get_node()
        if item_type == ItemType.TXN:
            # transactions can also be in the pending list:
            txn = self.pending_transactions.get(item_id)
            if txn is not None and txn[0] is not None:
                return txn[0]

        elif item_type == ItemType.ACK:
            # We assume that all acks are in the dag
            pass

        # TODO handle search of uwp in the cache

        return None

    def register_balance_lost(self, txn: Transaction):
        new_balance = list()
        for wallet in self.a_data.balance:
            spent = False
            for spent_input in txn.inputs:
                spent_input: Wallet
                if wallet.origin == spent_input.origin \
                        and wallet.id == spent_input.id:
                    spent = True
                    break
            if spent:
                logger.info("Found a txn thats spends my balance wallet: %s. Wallet spent: %s", txn, wallet)
            else:
                # Retain the wallet because no input spent it:
                new_balance.append(wallet)
        # Now set the filtered wallets as our new balance
        self.a_data.balance = new_balance

    def __is_wanted_txn(self, txn: Transaction):
        was_requested_at_ckpt_injection = False
        req_wallets = set()
        output_wallet: Wallet

        for output_wallet in txn.get_outputs():
            # check if one of the wallets of this TXN occurs in the latest ckpts utxos

            if output_wallet in self.a_data.tree.get_latest_checkpoint().utxos:
                was_requested_at_ckpt_injection = True
                req_wallets.add(output_wallet)

        if was_requested_at_ckpt_injection:
            # mark all wallets except the ones requested as SPENT

            for output_wallet in txn.get_outputs():
                if output_wallet not in req_wallets:
                    output_wallet.set_state(State.SPENT)

            # add TXN to tree and possibly detect gained money
            self.a_data.tree.add(txn.get_identifier(), txn)

            self.__try_freeing_orphans(txn)

            if self.pending_transactions.get(txn.get_identifier()) is not None:
                self.pending_transactions.pop(txn.get_identifier())
            logger.info("Found a wanted txn: %s", txn)
            return True

        return False

    def __try_freeing_orphans(self, txn: Transaction):
        try:
            orphans = self.orphaned_nodes.pop(txn.get_identifier())

            if orphans is not None:
                for node in orphans.values():
                    if isinstance(node, Acknowledge):
                        self.__add_acknowledgement(node)

                self.save_data()
                logger.info("Freed some Acks from the orphanage")
        except KeyError:
            logger.info("No orphans freed by registering transaction %s", txn)

    def __remove_dead_orphans(self):
        """This function will remove those orphans which ere in the orphanage for longer than the duration of one ckpt.
        """
        print("Started purging of dead parents")
        # parents of orphans from before the previous checkpoint grow older and may die in here
        gen_dead_orphan_parents = copy(self.gen_prev_orphan_parents)

        # parents of orphans from the time between the new, current ckpt and the previous one will grow older
        keys = set(self.orphaned_nodes.keys())
        self.gen_prev_orphan_parents = copy(keys)

        # those parents of orphans, that died in gen_dead will be removed from the orphaned_nodes keys
        for key in gen_dead_orphan_parents:
            if self.orphaned_nodes.get(key) is not None:
                self.orphaned_nodes.pop(key)

        logger.info("Missing parents of orphans grew older, dead ones were removed.")

