from copy import copy
from random import random
from typing import Union, Any

from abccore.agent_crypto import *
from abccore.checkpoint_service import CheckpointService
from abccore.prefix_tree import *
from abccore.outputs_helper import outputs_helper
import abccore.save_handler as save_handler
from abcnet.structures import ItemType

import logging


logger = logging.getLogger(__name__)


class AgentData:
    """
    AgentData holds most of the data necessary for the abc protocol. To directly have access to (primarely genesis) wallets by start-up routine one can enter a key in the constructor to get access to the to this key related wallets.
    """

    def __init__(
        self,
        private_key: Union[None, Ed25519PrivateKey, List[Ed25519PrivateKey]] = None,
    ):
        """
        Construct a new 'AgentData' object.
        :param private_key: private key to get access the related wallets. Primarely used for the initial genesis wallets.
        """
        if private_key is None:
            private_key = [gen_key()]
        elif isinstance(private_key, Ed25519PrivateKey):
            private_key = [private_key]
        elif isinstance(private_key, List):
            if len(private_key) == 0:
                private_key = [gen_key()]
        else:
            raise ValueError(
                "Expected a list of private keys. Got: " + str(private_key)
            )
        private_key: List[
            Ed25519PrivateKey
        ]  # At this point the argument is always a list of at least one key.

        self.keyset: List[Ed25519PrivateKey] = list(private_key)

        self.balance = []  # a set of outputs owned by this entity

        # TODO stake to be removed; checkpoint service will do this
        # a set of transaction IDs in which this agent gained stake TODO Is this used?
        self.stake = []
        self.current_stake = Decimal(0)  # TODO Is this used?
        self.stake_threshold = Decimal("Infinity")

        self.known_validators = []  # list of public keys of known validators
        self.key_to_use = 0
        self.validator_to_use = None

        # identifier of the last acknowledged transaction; b"0" for None
        self.last_acks = dict()

        self.ack_length = dict()
        self.transaction_history = (
            []
        )  # list of ID's of transactions made by this entity

        self.acked_wallets: Dict[Tuple[bytes, int], List[Acknowledge]] = dict()
        self.last_checkpoint = None

        self.tree = Tree()

    def save_data(
        self,
        pending_trans,
        orphaned_nodes,
        user_password=bytes("ThisNeedsToBeAdded!", "UTF-8"),
        filename="abc_save.db",
        checkpointservice: Optional[CheckpointService] = None,
    ):
        """Calls the save handler to save the agent tree."""
        # TODO: password for keyset
        args = [
            self.keyset,
            self.balance,
            self.last_acks,
            self.stake,
            self.transaction_history,
            self.ack_length,
            pending_trans,
            orphaned_nodes,
        ]

        save_handler.write_data(args, user_password, self.tree, filename)
        # save Checkpoint
        ckpt = self.tree.get_latest_checkpoint()
        if isinstance(ckpt, Checkpoint) and checkpointservice is not None:
            checkpointservice.ckpt_save(ckpt)
        logger.info("Saved data to local storage.")

    def load_data(
        self,
        user_password=None,
        filename="abc_save.db",
        checkpointservice: Optional[CheckpointService] = None,
    ) -> list:
        """Calls the save handler to load the agent tree.
        :returns False if unsuccessful.
        """
        try:
            args = save_handler.load_data(user_password, filename)
        except ImportError:
            logger.error("DB contained no data!")
            return None
        except LookupError:
            logger.error("DB had no data for agent, fallback to genesis.db")

            return self.load_data(user_password, "genesis.db", checkpointservice)
        else:
            self.tree = args[6]

            if not filename == "genesis.db":
                # check if there has been a key load before the db was load
                for pre_load_key in self.keyset:
                    # if there is such a key and it's not in the keys load from the db, add it
                    add = True
                    for load_key in args[0]:
                        key1_bytes = parse_to_bytes(pre_load_key)
                        key2_bytes = parse_to_bytes(load_key)

                        if key1_bytes == key2_bytes:
                            add = False

                    if add:
                        args[0].append(pre_load_key)

                if args[0] is None:
                    args[0] = list()

                self.keyset = args[0]
                self.balance.extend(args[1])

                # for the case where a user has no balance load from the db, we check twice -> fallback
                if not self.balance:
                    for node in self.tree:
                        self.check_and_register_ownership(node)

                self.stake.extend(args[3])
                # calculate current_stake
                stake_value = Decimal(0)
                for txn in self.stake:
                    if txn != b"":
                        stake_trans = self.tree.search(txn).get_node()
                        stake_value += stake_trans.get_value()

                # last_acks
                if args[2] is None or len(args[2]) == 0:
                    for key in self.keyset:
                        pk = key.public_key().public_bytes(
                            encoding=Encoding.Raw, format=PublicFormat.Raw
                        )
                        self.last_acks[
                            pk
                        ] = self.tree.get_latest_checkpoint().get_identifier()
                else:
                    self.last_acks = args[2]

                self.transaction_history.extend(args[4])

                # ack_length
                if args[5] is None or len(args[5]) == 0:
                    for key in self.keyset:
                        pk = key.public_key().public_bytes(
                            encoding=Encoding.Raw, format=PublicFormat.Raw
                        )
                        self.ack_length[
                            pk
                        ] = 0
                else:
                    self.ack_length = args[5]

                if args[9] is None:
                    pending_trans = dict()
                else:
                    pending_trans = args[9]

                if args[10] is None:
                    orphaned_nodes = dict()
                else:
                    orphaned_nodes = args[10]

            else:
                for key in self.keyset:
                    pk = key.public_key().public_bytes(
                        encoding=Encoding.Raw, format=PublicFormat.Raw
                    )
                    self.last_acks[
                        pk
                    ] = self.tree.get_latest_checkpoint().get_identifier()
                    self.ack_length[
                        pk
                    ] = 0

                pending_trans = dict()
                orphaned_nodes = dict()
                for node in self.tree:
                    self.check_and_register_ownership(node)

            unspent_wallets = args[7]
            # This is the set of unspent wallets for which we want to ask if they are spent
            # unspent_wallets = { (wallet1.origin, wallet1.id), (wallet2.origin, wallet2.id), ... }

            logger.info("Loaded tree from local storage.")

            # Load Checkpoint
            if checkpointservice is not None:
                ckpt = checkpointservice.ckpt_extract()
                if ckpt is not None:
                    self.tree.add(ckpt.get_identifier(), ckpt)
                    self.__load_prev_ckpts(checkpointservice, ckpt)

            return [unspent_wallets, pending_trans, orphaned_nodes, args[8]]

    def __load_prev_ckpts(self, ckpt_service: CheckpointService, ckpt: Checkpoint):
        # TODO check with Amit if this works
        older_ckpt = ckpt_service.extract(ckpt.get_origin())
        if older_ckpt is not None:
            self.tree.add(ckpt.get_identifier(), ckpt)
            self.__load_prev_ckpts(ckpt_service, older_ckpt)

    def add_to_save(self, node, filename="abc_save.db"):
        if isinstance(node, Transaction):
            save_handler.add_txn(None, node, filename)
        elif isinstance(node, Acknowledge):
            save_handler.add_ack(None, node, filename)

        logger.info("Added data to local storage: " + node.get_identifier().hex())

    def update_wallet(self, wallet, filename="abc_save.db"):
        save_handler.update_wallet(wallet, filename)

        logger.info("Updated wallet state on local storage.")

    def add_keypair(self):
        """
        Adds a new randomly generated keypair to the keyset and flags it as new key_to_use
        """
        key = gen_key()
        self.keyset.append(key)
        self.key_to_use = len(self.keyset) - 1
        pk = key.public_key().public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )
        self.last_acks[pk] = self.tree.get_latest_checkpoint().get_identifier()
        self.ack_length[pk] = 0
        logger.info("New keypair created, public key: " + pk.hex())

    def add_pregenerated_keypair(
        self, key: Ed25519PrivateKey, search_tree_for_now_owned=False
    ):
        """
        Adds a new pregenerated keypair to the keyset and flags it as new key_to_use.
        :param key: Ed25519PrivateKey, which shall be included into the key list
        :param search_tree_for_now_owned: flags, if the DAG shall be searched for now owned wallets
        """
        self.keyset.append(key)
        pk = key.public_key().public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )
        logger.info("Added pregenerated keypair, public key: " + pk.hex())
        self.last_acks[pk] = self.tree.get_latest_checkpoint().get_identifier()
        self.ack_length[pk] = 0
        if search_tree_for_now_owned:
            for node in self.tree:
                self.check_and_register_ownership(node)

    def is_my_key(self, pb_key: bytes) -> bool:
        """
        Checks, if the mentioned public key is owned by this entity or not. This may be used to update balance or stake.
        :param pb_key: bytes encoded public key
        :return: boolean
        """
        for key in self.get_pub_key_bytes():
            if key == pb_key:
                return True
        return False

    def get_key_to_use(self) -> bytes:
        """
        Gets the byte encoded public key of the private key we prioritize to use.
        :return: bytes
        """
        return (
            self.keyset[self.key_to_use]
            .public_key()
            .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
        )

    def get_keys(self) -> List[Ed25519PrivateKey]:
        """Returns the list of keys owned by this agent"""
        return list(self.keyset)

    def get_pub_keys(self) -> list:
        """
        Returns a list of public keys related to this agent
        :return: list of public keys of type 'Ed25519PublicKey'
        """

        output_list = []
        for key in self.keyset:
            output_list.append(key.public_key())

        return output_list

    def get_pub_key_bytes(self):
        """
        Returns a list of public keys related to this agent encoded as bytes
        :return: list of bytes encoded public keys
        """
        return [
            key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            for key in self.get_pub_keys()
        ]

    def get_transaction_set(self, value):
        """Returns a set of wallets to get the specified amount of money. The method uses the oldest wallets first
        and takes additional wallets until the entered value with the additional fee-value is reached.
        :param value: Value which shall be represented with wallets. The value doesn't include the fee.
        :return: Set of wallets which is able to actually pay the specified value including the additional fees.
        """
        # self.balance.sort()   TODO , sorting balance to actually use wallets with lowest/highest amount of money first
        spending_set = []
        spending_val = 0

        while spending_val < value + calculate_fee(value):
            if len(self.balance) > 0:
                wallet = self.balance.pop(0)
                spending_val += wallet.value
                spending_set.append(wallet)
            else:
                logger.error("Transaction can't be handled, not enough balance.")
                self.balance.extend(spending_set)
                return None

        return spending_set

    def get_validator(self) -> bytes:
        """
        Returns a validator for handling a transaction
        :return: public key of a validator in bytes format
        """
        if self.validator_to_use is None and len(self.known_validators) == 0:
            return (
                self.keyset[self.key_to_use]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
            )
        elif self.validator_to_use is None:
            index = random.randint(
                0, len(self.known_validators) - 1
            )  # if no validator is specified, return a random one
            return self.known_validators[index]
        else:
            return self.validator_to_use

    def acknowledge(self, transaction) -> [Acknowledge]:
        """Function to acknowledge a new transaction. For each key of the agent, a new Ack will be generated.
        :param transaction: The transaction that will be acknowledged.
        :return: False if unsuccessfull.
        """
        acks = []

        double_pending_detected = False
        double_spending_acks = []
        previous_acks_found = False
        for wallet in transaction.get_inputs():
            if (wallet.get_origin(), wallet.get_id()) in self.acked_wallets:
                # If at least one of the inputs are already acknowledged
                # we are going to send back all the acks that we have for it:
                previous_acks_found = True
                previous_acks = self.acked_wallets[(wallet.get_origin(), wallet.get_id())]
                acks.extend(previous_acks)
                for prev_ack in previous_acks:
                    prev_ack: Acknowledge
                    if prev_ack.get_trans_id() != transaction.get_identifier():
                        double_pending_detected = True
                        double_spending_acks.append(prev_ack)

        if double_pending_detected:
            def join_wallets(wallets: List[Any]) -> str:
                return "\n\t- " + ("\n\t- ".join(map(lambda w: str(w), wallets)))
            logger.warning("Found a double spending attack by transaction: %s with,"
                           "\ninput wallets:  %s \nand output wallets: "
                           "%s\n Found previous acks that were sent for other transactions: %s",
                           transaction, join_wallets(transaction.get_inputs()), join_wallets(transaction.get_outputs()),
                           join_wallets(double_spending_acks), exc_info=True)
            return acks

        if previous_acks_found:
            logger.info("Found an txn whose inputs we have already acked: %s", transaction)
            return acks

        # create Ack for each key owned, instead of only once
        for i in range(len(self.get_pub_key_bytes())):
            sk: Ed25519PrivateKey = self.keyset[i]
            pk = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

            prev_ack = self.last_acks.get(pk)
            if prev_ack is None:
                prev_ack = self.tree.get_latest_checkpoint().get_identifier()
                self.last_acks[pk] = prev_ack

            ack = Acknowledge(
                transaction.get_identifier(),
                prev_ack,
                pk,
            )
            self.__create_signature(ack, sk)

            logger.info(
                "CREATED ACKNOWLEDGEMENT for transaction: "
                + transaction.identifier.hex()
                + "; Ack-ID: "
                + ack.get_identifier().hex()
            )

            ack_length = self.ack_length.get(pk)
            if ack_length is None:
                ack_length = 1
            else:
                ack_length += 1
            self.ack_length[pk] = ack_length

            self.last_acks[pk] = ack.get_identifier()
            acks.append(ack)

        for wallet in transaction.get_inputs():
            self.acked_wallets[(wallet.get_origin(), wallet.get_id())] = list(acks)

        return acks

    def __create_signature(self, node, key: Ed25519PrivateKey = None) -> bool:
        """Using the helper function __compute_data_for_auth(), this function creates a signature for :param node.
        The signature field is accessed with node.signature for Acknowledge or node.add_signature() for
        Transactions.
        """
        data = self.__compute_data_for_auth(node)
        if key is None:
            key = self.keyset[self.key_to_use]

        if isinstance(node, Acknowledge):
            signature = auth_sign(data, key)
            node.signatures.append(signature)

        elif isinstance(node, Transaction):
            for key in self.keyset:
                signature = auth_sign(data, key)
                node.add_signature(signature)

        logger.info("Created a signature for " + str(node))
        return True

    def validate_signature(self, node) -> bool:
        """Using the helper function __compute_data_for_auth(), this function validates a signature for :param node.
        The signature field is accessed with node.get_signature() for Acknowledge or node.get_signatures() for
        Transactions.
        """
        data = self.__compute_data_for_auth(node)
        if isinstance(node, Acknowledge):
            result = auth_validate(data, node.signature)

            logger.info("Checked a signature for " + str(node) + ": " + str(result))
            return result
        elif isinstance(node, Transaction):
            keys_to_check = dict()
            for wallet in node.get_inputs():
                keys_to_check[wallet.get_pk()] = True

            for (pk, sig) in node.get_signatures():
                if keys_to_check.get(pk):
                    keys_to_check.pop(pk)
                    if not auth_validate(data, (pk, sig)):
                        logger.error("Checked a signature for " + str(node) + ": False")
                        return False

            if len(keys_to_check) == 0:
                logger.info("Checked a signature for " + str(node) + ": True")
                return True

        logger.error("Checked a signature for " + str(node) + ": Something bad happend")
        return False

    def validate_trans(self, txn: Transaction) -> bool:
        """This method is a helper for the method __add_transaction(). For the :param txn, the local tree will be
        searched for all parents and if the wallets of the transaction inputs are unspent.
        If there are parent transactions missing, a TXN Request will be issued.
        If there is one wallet SPENT, the method will :return False to indicate that no acknowledge will be send.
        If txn is valid, it :returns True to indicate that an acknowledge should be send.
        """

        valid = True

        for wallet in txn.get_inputs():  # Check in dag if this TXN is valid.
            try:
                check_wallet = (
                    self.tree.search(wallet.get_origin())
                    .get_node()
                    .get_outputs()[wallet.get_id()]
                )

                if not check_wallet == wallet:
                    valid = False

                if not check_wallet.get_state() == State.UNSPENT:
                    valid = False  # Wallet of this TXN has already been spent, therefore TXN is not valid

            except AttributeError:
                valid = False
                logger.debug("There is no transaction with this wallet in the tree")
                logger.error("Transaction not found")

        if valid:
            valid = is_valid_trans(txn.get_inputs(), txn.get_outputs())

        logger.info("Tried validation of a TXN with result " + str(valid))
        return valid

    @staticmethod
    def validate_ack_chain(ack: Acknowledge, prev_ack: Union[Acknowledge, Genesis]):
        if ack is None or prev_ack is None:
            raise ValueError("None")
        if (
            ack.get_pb_key() is None
            or not isinstance(ack.get_pb_key(), bytes)
            or len(ack.get_pb_key()) == 0
        ):
            raise ValueError("Ack with no public key.")
        if ack.signature[0] != ack.get_pb_key():
            raise ValueError(
                "Signature mismatch. The signature is not signed using the keypair of the ack."
            )
        if isinstance(prev_ack, Genesis):
            # The first ack in the chain. Nothing to check:
            return

        if ack.signature is None or prev_ack.signature is None:
            raise ValueError("Signature is missing")
        # Check if the public key is the same:
        pb_key = ack.signature[0]
        prev_pb_key = prev_ack.signature[0]
        if pb_key != prev_pb_key:
            raise ValueError("Public keys are not matching")

    def __compute_data_for_auth(self, node) -> bytes:
        """This is a helper function to reduce code duplicates for functions __create & __validate_signature().
        It computes the data over which a signature is create, which is needed for both creation and validation.
        """
        data = bytes()
        data += node.get_identifier()

        return data

    def assign_validator(self, validator):
        """
        Assigns a possibly new validator this entity shall use. If the validator is unknown so far it is also added to the known validators.
        :param validator: bytes representation of the public key of the validator we want to use
        """
        self.validator_to_use = validator
        if not self.known_validators.__contains__(validator):
            self.known_validators.append(validator)
        logger.info("Now using validator " + validator.identifier)

    def add_validator(
        self, validator
    ):  # TODO do we even need a list of known validators? Nico: Partially, we need a list of (val-pk, stake) {init!}
        """
        Adds a validator to the list of known validators.
        :param validator: bytes representation of the public key of the validator we want to add to the known validators
        """
        if not (self.known_validators.__contains__(validator)):
            self.known_validators.append(validator)
            logger.info(
                "New validator added to known validators: " + validator.identifier
            )
        else:
            logger.info("Validator already exists in known validators set")

    def send_money(self, recipient, value, validator):
        """send some money to one specific recipient
        :param recipient: public key of the recipient
        :param value: amount of money one wants to send
        :param validator: public key of the validator
        """

        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            value = Decimal(value)
        elif not isinstance(value, Decimal):
            raise ValueError("Unrecognized value type: " + str(value))

        inputs = self.get_transaction_set(value)
        if inputs is None:
            return None
        inputs_val = get_wallet_value(inputs)

        if inputs_val == value:
            outputs = [Wallet(recipient, value)]
        else:
            outputs = [
                Wallet(recipient, value),
                # Wallet(self.get_key_to_use(), inputs_val - value)
                # TODO keyset private?
            ]
        outputs = outputs_helper(inputs, outputs)

        transaction = Transaction(inputs, outputs, validator)
        self.__create_signature(transaction)

        # self.known_validators.append(
        #     validator
        # )  # add validator to list of known validators

        self.transaction_history.append(transaction.get_identifier())

        return transaction

    def transform_dag(self, ckpt: Checkpoint, pending_transactions: dict):
        """This method will handle most of the transition from the current dag to a new checkpoint.
        At first, it creates a new prefix tree and populates it with all TXNs which have unspent outputs in the
        Checkpoint :param ckpt. Then, the ckpt will be added to the new tree.
        For all TXNs in the new tree, the dependend TXNs will be added to the dict pending_trans, and all ACKs will be
        added to a set pending_acks. Both are needed for reevaluation.
        The last step is to add all TXNs from the old pending_transactions to the new pending_trans, with stake reset to
        Decimal(0). Also, all ACKs for the TXNs in the old pending_transactions are added to pending_acks.
        Then, the old tree will be completely replaced by the new tree and the method :returns both pending_trans and
        pending_acks, such that the calling Agent is able to reconfirm TXNs.
        """
        # delete old data in local storage
        save_handler.delete_old_data("abc_save.db")

        # create a new tree and add all previous checkpoints
        new_tree = Tree()
        for node_id in self.tree.list_of_checkpoints:
            prev_ckpt = self.tree.search(node_id)
            if prev_ckpt is not None:
                new_tree.add(node_id, prev_ckpt.get_node())

        retained_spent_wallets: Dict[Tuple[bytes, int], List[Acknowledge]] = dict()

        def retain_acks_for_wallet(wallets: List[Wallet]):
            for w in wallets:
                if (w.get_origin(), w.get_id()) in self.acked_wallets:
                    retained_spent_wallets[(w.get_origin(), w.get_id())] \
                        = self.acked_wallets[(w.get_origin(), w.get_id())]

        # add unspent TXNs to the tree
        txn_set = set()
        utxo_set = set()
        missing_txn_requests = set()
        for wallet in ckpt.get_utxos():
            # For all unspent transaction outputs in the checkpoint, we add the corresponding TXN to the new tree and
            # set the corresponding output state to UNSPENT. Also, we add the pair (wallet.origin, wallet.id) to the
            # utxo_set.

            # add wallet representation to search for its dependend nodes
            utxo_set.add((wallet.get_origin(), wallet.get_id()))

            # check if TXN of this Wallet is in tree or send a request for it
            origin_leaf = self.tree.search(wallet.get_origin())
            if origin_leaf is None:
                missing_txn_requests.add(wallet.get_origin())
            else:
                # check if this TXN was added to the new tree before, if so, replace it
                test_tree_node = new_tree.search(wallet.get_origin())
                already_in_tree = False
                if test_tree_node is not None:
                    origin_leaf = test_tree_node
                    already_in_tree = True

                origin_node = origin_leaf.get_node()
                origin_node: Transaction

                # Set this Wallet to UNSPENT
                origin_node.outputs[wallet.get_id()].set_state(State.UNSPENT)

                # Set the TXNs parents to this ckpt
                if not isinstance(origin_node, Genesis) and not isinstance(origin_node, Checkpoint):
                    origin_node.parents = {ckpt.get_identifier(): ckpt.get_identifier()}


                # Add TXN.identifier to set of kept TXNs and add the TXN to the new tree
                if not already_in_tree:
                    txn_set.add(origin_node.get_identifier())
                    new_tree.add(origin_node.get_identifier(), origin_node)
                    # Retain the output acks that we have created before
                    retain_acks_for_wallet(origin_node.get_outputs())

        # Add Checkpoint to new tree
        new_tree.add(ckpt.get_identifier(), ckpt)

        # Add all UTXO that are mine to my balance
        self.balance.clear()
        my_keys = set(self.get_pub_key_bytes())
        for utxo in ckpt.utxos:
            if utxo.own_key in my_keys:
                self.balance.append(utxo)
        # Add all new outputs (rewards) that belong to me to my balance
        for out in ckpt.outputs:
            if out.own_key in my_keys:
                self.balance.append(out)

        # search for TXNs which were confirmed while the ckpt was created
        deconfirmed_nodes = self.tree.search_dependend_nodes(utxo_set)
        # deconfirmed_nodes: set of pairs (Node.ID, ItemType)
        # this set holds also the ACKs for the utxo-TXNs

        # part of method output; to be reevaluated ACKs
        pending_trans = set()
        pending_acks = set()
        for pair in deconfirmed_nodes:
            # For all Nodes in the old tree, that depend on Wallets which are UNSPENT in the checkpoint; we add TXNs
            # to pending_trans, and ACKs to pending_acks
            node_identifier = pair[0]
            item_type = pair[1]
            node = self.tree.search(node_identifier).get_node()

            if item_type == ItemType.TXN:
                node: Transaction
                # reset state of now pending TXNs
                self.transform_helper_reset_state(node)

                # add TXN to pending
                pending_trans.add(node)

            elif item_type == ItemType.ACK:
                # probably not needed anymore
                node: Acknowledge

                # set prev_ack to be ckpt
                node.prev_ack = ckpt.get_identifier()

                if node.get_trans_id() not in txn_set:
                    # don't add ACKs for utxo TXNs
                    pending_acks.add(node)

        pending_transactions_keys = pending_transactions.keys()
        for trans_id in pending_transactions_keys:
            # For all TXNs in the old pending_transactions, we search already received ACKs and add them to
            # pending_acks. Also, we add those TXNs, with stake reset to 0, to pending_trans for later reevaluation.
            depending_ack_set = self.tree.pending_acks.get(trans_id)

            if depending_ack_set is not None:
                for ack_code in depending_ack_set:
                    node = self.tree.search(ack_code).get_node()
                    node.prev_ack = ckpt.get_identifier()
                    pending_acks.add(node)

            # add the pending TXN for reevaluation
            depending_trans = pending_transactions.get(trans_id)[0]

            # reset state of now pending TXNs
            self.transform_helper_reset_state(depending_trans)

            pending_trans.add(depending_trans)

        for txn in pending_trans:
            # Retain all acks we have for this txn's output and input
            retain_acks_for_wallet(txn.get_outputs())
            retain_acks_for_wallet(txn.get_inputs())
        self.acked_wallets = retained_spent_wallets

        # deletes the now deprecated data
        self.tree = new_tree

        # since by transition all ACKs are deleted, the last_ack is set to the new Checkpoint
        ckpt = ckpt.get_identifier()
        for key in self.last_acks:
            self.last_acks[key] = ckpt

        return [pending_trans, pending_acks, missing_txn_requests]

    @staticmethod
    def transform_helper_reset_state(txn: Transaction):
        for in_wallet in txn.get_inputs():
            in_wallet: Wallet
            in_wallet.set_state(State.UNSPENT)

        for out_wallet in txn.get_outputs():
            out_wallet: Wallet
            out_wallet.set_state(State.UNSPENT)

    def check_and_register_ownership(self, node: Node):
        """This function checks for a :param node, if its inputs spent balance of the Agent and if its outputs add
        balance to the Agent.
        """
        # the Wallets to check are different based on the Nodes type
        output_wallets_to_check = []
        input_wallets_to_check = []

        if isinstance(node, Checkpoint):
            # CKPT utxos are the unspent outputs prior to the CKPT, while outputs represent the rewards for
            # participating in the system, thus both may add balance

            output_wallets_to_check += node.get_utxos()
            output_wallets_to_check += node.get_outputs()

        elif isinstance(node, Genesis):
            # In Genesis, only the outputs may add balance

            output_wallets_to_check += node.get_outputs()

        if isinstance(node, Transaction):
            if self.is_my_key(node.get_validator()):  # TODO deprecated
                # this was used to delegate stake, but our current ckpt implementation doesn't use it anymore
                logger.info("Gained delegated stake: %s", node.value)

            # In a Transaction, its outputs may add balance, but its inputs may spent balance
            output_wallets_to_check += node.get_outputs()
            input_wallets_to_check += node.get_inputs()

        for input_wallet in input_wallets_to_check:
            if self.is_my_key(input_wallet.get_pk()):
                if input_wallet in self.balance:
                    self.balance.remove(input_wallet)
                    logger.info("Removed money from wallet: %s", input_wallet)

        for wallet in output_wallets_to_check:
            if self.is_my_key(wallet.get_pk()):
                if wallet not in self.balance:
                    self.balance.append(wallet)
                    logger.info("Gained money from wallet: %s", wallet)
