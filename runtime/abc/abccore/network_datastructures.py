import time
import hashlib

from abcnet.structures import ItemQualifier, ItemEncodeable, ItemType
from abcnet.transcriber import Transcriber

from abccore.DAG import Acknowledge
from abccore.constants import TTL, INTERVAL_TIME
from abccore.agent_crypto import hash_bytes


def encode_signature(transcriber: Transcriber, signature):
    """
    Encodes a single signature and adds it to the given transcriber to prepare the sending over the network.
    :param transcriber: The transcriber we use to send the corresponding message
    :param signature: Signature which shall be encoded and included in the transcriber
    """
    if signature is None:
        signature = (bytes(), bytes())
    (pk, sig) = signature
    if pk is None:
        transcriber.nested_bytes(bytes())
    else:
        transcriber.nested_bytes(pk)
    transcriber.nested_bytes(sig)


def encode_wallet(transcriber: Transcriber, wallets):
    """
    Encodes a set of wallets and adds it to the given transcriber to prepare the sending over the network.
    :param transcriber: The transcriber we use to send the corresponding message
    :param wallets: The set of outputs/wallets which shall be encoded and included in the transcriber
    """
    transcriber.integer(len(wallets))

    for i in range(0, len(wallets)):
        transcriber.write_text(str(wallets[i].value), "value")
        transcriber.nested_bytes(wallets[i].own_key)
        transcriber.nested_bytes(
            wallets[i].origin, "transaction ID this wallet belongs to"
        )
        transcriber.integer(wallets[i].id, "Wallet ID")


def reduce_ttl(item_set: set, debug=False) -> set:
    """
    Reduces the TTL of all items included in the item_set.
    :param item_set: Set of items which TTL shall be reduced
    :param debug: debug=True allows testing of the TTL reduction block even if a certain amount of time has not passed.
    :return: Set of items with the reduced TTL
    """
    return_set = set()
    to_remove = list()
    for item in item_set:
        if not isinstance(item, HasTimeToLive):
            raise TypeError('Item has no "ttl"-variable')

        if item.time_stamp != None:
            if debug or time.time() - item.time_stamp > float(INTERVAL_TIME):
                item.ttl -= 1
                item.time_stamp = time.time()
                return_set.add(item)

        else:
            item.ttl -= 1
            item.time_stamp = time.time()
            return_set.add(item)

        if item.ttl <= 0:
            to_remove.append(item)

    for item in to_remove:
        item_set.remove(item)

    return return_set


class HasTimeToLive:
    """
    This class can be used for inheritage to introduce TTL (=time to live) and repeat messages sent to the network.
    The amount of repetitions can be set with the TTL variable in the 'abccore.constants' module.
    """

    def __init__(self):
        self.ttl = TTL
        self.time_stamp = None
        self.id = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


class NetTransaction(HasTimeToLive, ItemQualifier, ItemEncodeable):
    """
    NetTransaction is used to prepare and to receive items of type 'Transaction' from the network.
    """

    def __init__(self, transaction, id=None):
        """
        Initializes all parameters including the TTL necessary for the repeatedly sending.
        :param transaction: The transaction we want to prepare for the network
        :param id: If an ID is given (e.g. received over the network) it will be checked if it fits to the transaction
        """
        self.txn = transaction
        super(NetTransaction, self).__init__()

        if id is None:
            self.id = self.txn.get_identifier()
        else:
            self.id = id
            self.check_id()

    def check_id(self):
        """
        Checks the ID and raises an error if the given ID and the computed ID doesn't match.
        """
        if self.id != self.txn.get_identifier():
            raise ValueError(
                f"ID check doesn't match the transaction content: "
                f"Given id: {self.id},"
                f"Calculated id: {self.identifier}"
            )

    def item_qualifier(self):
        """
        :return: Returns the ID of this entity as hex.
        """
        return self.id.hex()

    def item_type(self):
        """
        :return: Returns the ItemType of this entity (ItemType.TXN)
        """
        return ItemType.TXN

    def encode(self, transcriber):
        """
        Encodes this entity to prepare it for sending over the network.
        :param transcriber: The transcriber which is used for the sending process.
        """
        transcriber.nested_bytes(self.id)
        encode_wallet(transcriber, self.txn.inputs)
        encode_wallet(transcriber, self.txn.outputs)

        if self.txn.validator_key is None:
            # Write an empty string if validator key is none
            transcriber.nested_bytes(bytes(), "validator key")
        else:
            transcriber.nested_bytes(self.txn.validator_key, "validator key")

        transcriber.integer(len(self.txn.signatures))
        for s in self.txn.signatures:
            encode_signature(transcriber, s)


class NetAcknowledgement(HasTimeToLive, ItemQualifier, ItemEncodeable):
    """
    NetAcknowledgement is used to prepare and to receive items of type 'Acknowledgement' from the network.
    """

    def __init__(self, acknowledgement, id=None):
        """
        Initializes all parameters including the TTL necessary for the repeatedly sending.
        :param acknowledgement: The acknowledgement we want to prepare for the network
        :param id: If an ID is given (e.g. received over the network) it will be checked if it fits to the acknowledgement
        """
        self.ack: Acknowledge = acknowledgement
        super(NetAcknowledgement, self).__init__()

        self.id = self.ack.get_identifier()

        if id is None:
            self.id = self.ack.get_identifier()
        else:
            self.id = id
            self.check_id()

    def check_id(self):
        """
        Checks the ID and raises an error if the given ID and the computed ID doesn't match.
        """
        if self.id != self.ack.get_identifier():
            raise ValueError(
                f"ID check doesn't match the ack content: "
                f"Given id: {self.id},"
                f"Calculated id: {self.identifier}"
            )

    def item_qualifier(self):
        """
        :return: Returns the ID of this entity as hex.
        """
        return self.id.hex()

    def item_type(self):
        """
        :return: Returns the ItemType of this entity (ItemType.ACK)
        """
        return ItemType.ACK

    def encode(self, transcriber: Transcriber):
        """
        Encodes this entity to prepare it for sending over the network.
        :param transcriber: The transcriber which is used for the sending process.
        """
        transcriber.nested_bytes(self.id)
        transcriber.nested_bytes(self.ack.transaction)
        if self.ack.prev_ack is None:
            transcriber.nested_bytes(bytes())
        else:
            transcriber.nested_bytes(self.ack.prev_ack)
        if self.ack.get_pb_key() is None:
            transcriber.nested_bytes(bytes())
        else:
            transcriber.nested_bytes(self.ack.get_pb_key())

        encode_signature(transcriber, self.ack.signature)


def gen_uspwr_id(wallet_set, is_req) -> bytes:
    """
    Method to generate an ID for a whole set of wallets.
    :param wallet_set: Set of wallets we want to generate an ID for
    :return: hash in bytes
    """
    wallet_list = []
    for wallet in wallet_set:
        wallet_list.append(wallet)

    wallet_list.sort()
    id_string = b""
    for wallet in wallet_list:
        id_string = id_string + wallet[0] + bytes(wallet[1])

    id_string = id_string + bytes(is_req)

    return hash_bytes(id_string)


# Unspent Wallet Request = USPWR
class NetUSPWR(HasTimeToLive, ItemQualifier, ItemEncodeable):
    """
    NetUSPWR (=Net-Unspent-Wallet-Request) is used to prepare and to receive unspent wallet request which is needed for the Replay functionality.
    The Replay functionality allows agents to request updates from the network after start-up routine.
    If an agent was offline he might has missed new transactions or acknowledgement. Therefore, the agent can send an NetUSPWR to the network with
    the last state of utxos (unspent-transaction-outputs = unspent wallets). All other agents will check if there are new transactions which depend on these utxos.
    If there are new transactions, the newest ones will be send with help of a NetUSPWR as well. The 'is_req' flag defines if a NetUSPWR is a request or an answer.
    """

    def __init__(self, wallet_set, is_req=0, id=None):
        """
        Initializes all parameters including the TTL necessary for the repeatedly sending.
        :param wallet_set: The acknowledgement we want to prepare for the network
        :param is_req: defines if it is a request or not. To make sending over the network easier with usage of already implemented methods is_req is an integer value.
        0: it is not a request
        1: it is a request
        :param id: If an ID is given (e.g. received over the network) it will be checked if it fits to the acknowledgement
        """
        super(NetUSPWR, self).__init__()

        if not isinstance(is_req, int):
            raise ValueError(f"NetUSPWR expects 'is_req' of type 'int'")

        if not isinstance(id, bytes) and not id == None:
            raise ValueError(f"NetUSPWR expects 'id' of type 'bytes'")

        self.id = id
        self.unspent_wallet_set = wallet_set  # = {(origin1, wallet_id1),...}
        self.is_req = is_req

        if id is None:
            self.id = gen_uspwr_id(self.unspent_wallet_set, is_req)
        else:
            self.check_id()

    def check_id(self):
        """
        Checks the ID and raises an error if the given ID and the computed ID doesn't match.
        """
        other_id = gen_uspwr_id(self.unspent_wallet_set, self.is_req)
        if self.id != other_id:
            raise ValueError(
                f"ID check doesn't match the unspent wallet request content: "
                f"Given id: {self.id},"
                f"Calculated id: {other_id}"
            )

    def item_qualifier(self):
        """
        :return: Returns the ID of this entity as hex.
        """
        return self.id.hex()

    def item_type(self):
        """
        :return: Returns the ItemType of this entity (ItemType.UNSPENT_WALLET_COLLECTION)
        """
        return ItemType.UNSPENT_WALLET_COLLECTION

    def encode(self, transcriber: Transcriber):
        """
        Encodes this entity to prepare it for sending over the network.
        :param transcriber: The transcriber which is used for the sending process.
        """
        transcriber.nested_bytes(self.id)
        transcriber.integer(self.is_req)
        transcriber.integer(len(self.unspent_wallet_set), "Unspent wallets length")

        for wallet in self.unspent_wallet_set:
            transcriber.nested_bytes(wallet[0], "Wallet origin")
            transcriber.integer(wallet[1], "Wallet ID")