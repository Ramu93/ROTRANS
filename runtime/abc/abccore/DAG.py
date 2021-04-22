from enum import Enum
from typing import Optional, Tuple, List, Dict

import abccore.constants as constants
from abccore.agent_crypto import hash_bytes
from decimal import *
from io import BytesIO
import hashlib
from struct import pack


def get_wallet_value(wallets: []) -> Decimal:
    """Function to get the value of the inputs list and outputs list of transactions
    :param wallets: List of wallets to be summed up using internal Decimal() implementation of class Wallet
    """
    out = Decimal(0)
    for entry in wallets:
        out += entry.get_value()
    return out


def is_valid_trans(inputs, outputs) -> bool:
    """Method to check if the sum of the values in some inputs equals the sum of values in some outputs, according to
    correct transaction fee calculation.
    :param inputs: set of wallet
    :param outputs: set of wallets
    :return boolean
    """
    in_sum = Decimal(0)
    out_sum = Decimal(0)
    inputs_dict = (
        {}
    )  # key: PK of the owner; value: sum of value of wallets belonging to the same PK
    taxed = Decimal(0)
    for wallet in inputs:
        # sums up the values of all input wallets and adds them to the inputs_dict
        in_sum += wallet.get_value()
        if inputs_dict.get(wallet.get_pk()) is None:
            # current wallet belongs to PK not in the dict
            inputs_dict[wallet.get_pk()] = wallet.get_value()
        else:
            # increase value of known PK
            inputs_dict[wallet.get_pk()] += wallet.get_value()

    laundering = (
        True  # if the output wallets only redistribute money between the input wallets
    )
    for wallet in outputs:
        # sums up the values of all output wallets
        out_sum += wallet.get_value()

        # case distinction with two outcomes per wallet
        if (
            inputs_dict.get(wallet.get_pk()) is None
            or inputs_dict.get(wallet.get_pk()) < wallet.get_value()
        ):
            # if the output wallet belongs to none of the known PKs from the input wallets -> fee
            # also, if the output wallet has a larger value than the sum of input wallets of the same PK -> fee
            taxed += wallet.get_value()
            laundering = False

    if laundering:
        # if laundering is True, then there was no wallet detected that would be subject to the fee
        # therefore, the sum of values of all input wallets is subject to the fee, to prevent spamming attacks
        taxed = in_sum

    if taxed == out_sum:
        # if all output wallets are subject to the fee, then the fee was calculated over the input wallets
        fee = calculate_fee(in_sum)
    else:
        fee = calculate_fee(taxed)

    # we round the input and output values to much smaller degree than the fee
    return in_sum.quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN) == (
        out_sum + fee
    ).quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN)


def calculate_fee(taxed: Decimal) -> Decimal:
    fee = Decimal(taxed * constants.TRANSACTION_FEE)
    return fee.quantize(Decimal(".0000000001"), rounding=ROUND_DOWN)


class State(Enum):
    UNSPENT = 0
    PENDING = 1
    SPENT = 2


class Wallet:
    """Basic unit to save who has which amount of money, used for transactions"""

    def __init__(self, own_key: bytes, value: Decimal, origin=None, id=None):
        """The first two parameters will be set by creation of a wallet:
        :param own_key: the public key of the owner of the money
        :param value: a certain amount of money
        The other two parameters are set afterwards, in the constructor of a Transaction
        :param origin: the Transaction.identifier in which this wallet is an output
        :param id: the list index of this wallet in its origins Transaction.outputs
        """
        self.value = value
        self.own_key = own_key  # own_key needs to be fixed length bytes
        self.origin = origin  # origin needs to be fixed length bytes
        self.id = id  # id is maxed to 65536 as it needs to be representable in one byte of size
        self.state = State.UNSPENT

    def __eq__(self, other) -> bool:
        """Since a wallet has no unique identifier computed over its contents, we check the contents itself for equality
        The state is not checked here, because it is not needed to see if two wallets are the same
        """
        if not self.value == other.get_value():
            return False
        if not self.own_key == other.get_pk():
            return False
        if not self.origin == other.get_origin():
            return False
        if not self.id == other.get_id():
            return False
        return True

    def __hash__(self):
        return hash((self.origin, self.id))

    def __bytes__(self):
        output = b"" + self.own_key + self.origin + self.id.to_bytes(2, "big")
        return output

    def __str__(self):
        return f"Wallet(owner={self.own_key.hex()[:5]}, origin={self.origin.hex()[:5]}, id={self.id}, value={str(self.value)})"

    # ---- Override the comparing operator(<,>,>=,<=) that help us sort list of wallets.
    def __ge__(self, other: "Wallet"):
        """
        Returns self >= other.
        A wallet is greater than another if the origin is larger (alphabetically) .
        In case of a tie, the id of wallets serve as a tie breaker.
        """
        if self.origin == other.origin:
            return self.id >= other.id
        return self.origin.hex() > other.origin.hex()

    def __lt__(self, other):
        """
        Returns self < other
        """
        return not (self >= other)

    def __le__(self, other):
        """
        Returns self <= other
        """
        return not (self > other)

    def __gt__(self, other):
        """
        Returns self > other
        """
        return self >= other and self != other

    def equals(self, other: "Wallet"):
        return self == other

    def get_pk(self):
        return self.own_key

    def get_value(self):
        return Decimal(self.value)

    def get_origin(self):
        return self.origin

    def get_id(self):
        return self.id

    def set_origin_id(self, origin, id):
        """To be called in Transaction.init() to set the Wallet origin to be the transaction ID where this Wallet is
        produced as output and the Wallet ID as the index of the Wallet in the Transactions output list.
        """
        self.origin = origin
        self.id = id

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.state = state

    def encode_input_wallet_identity(self, bytebuffer):
        """
        Encodes this wallet as an input wallet and writes it into the given writable buffer.
        This only properties that are considered are the origin id, value and the key information.
        :param bytebuffer: Buffer in which the content of this wallet will be writen into.
        """
        bytebuffer.write(self.get_origin())
        bytebuffer.write(self.id.to_bytes(4, byteorder="big"))
        self.encode_output_wallet_identity(bytebuffer)

    def encode_output_wallet_identity(self, bytebuffer):
        """
        Encodes this wallet as an output wallet and writes it into the given writable buffer.
        This only properties that are considered are value and the key information.
        The origin  id is not considered as the identity of an output wallet.
        :param bytebuffer: Buffer in which the content of this wallet will be writen into.
        """
        bytebuffer.write(self.own_key)
        quantized_value = self.value.quantize(
            Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN
        )
        # We use the standard rounding so different value properties will only effect the id,
        # if the value would also affect the system monetary value
        bytebuffer.write(str(quantized_value).encode("UTF-8"))


class Node:
    """Base class for all Node types in the DAG"""

    def __init__(self):
        self.signatures = (
            []
        )  # list of tuples (pk, sig over content), both contents in bytes, length 32 + 64
        self.identifier = None  # will be calculated over contents
        self.parents = (
            {}
        )  # could have been a set for easier use TODO change if time allows
        self.value = Decimal(0)
        self.outputs = None  # all Nodes have outputs, but not all Nodes have inputs

    def __hash__(self):
        return hash(self.get_identifier())

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.get_identifier() == other.get_identifier()
        else:
            return False

    def __set_identifier(self):
        """
        Sets the identifier by writing the content of this node into a buffer
        and calls
        """
        bytebuffer = BytesIO()
        self._encode_identity(bytebuffer)
        self.identifier = hash_bytes(bytebuffer.getbuffer())

    def _encode_identity(self, bytebuffer: BytesIO):
        """
        Writes the content of the object that makes up its identity into the given byte buffer.
        :param bytebuffer: io.ByteIO object that holds the content of this node object
        """
        pass  # This is a different implementation for each type of Node

    def get_identifier(self) -> bytes:
        """
        The identifier of this node is lazily calculated.
        Do not call this function until all properties of this object have been set.
        :returns the identifier of this node.
        """
        if self.identifier is None:
            self.__set_identifier()
        return self.identifier

    def get_parents(self):
        """:returns the dict of identifiers of all parent nodes in the DAG."""
        return self.parents

    def get_outputs(self) -> List[Wallet]:
        """:returns a list ouf outputs if the node is of type transaction, checkpoint or genesis, otherwise None"""
        return self.outputs

    def get_value(self):
        return self.value

    def __str__(self):
        if self.identifier is None:
            return "Node not initialized yet"
        return "Node " + self.get_identifier().hex()


class Transaction(Node):
    """class for use in incentive option B"""

    def __init__(self, inputs, outputs, validator_key):
        """:param inputs: a list of wallets [w1, ...], where every wallet needs to have set its origin
        :param outputs: a list of wallets: [w1, w2, ...]
        :param validator_key: pk to address the validator
        """
        super().__init__()
        self.inputs = inputs

        # Set parents of Transaction as list of all origins of input wallets
        for entry in inputs:
            if not entry.get_origin() is None:
                self.parents[entry.get_origin()] = entry.get_origin()

        # Compute the value of this transaction
        for wallet in outputs:
            self.value += wallet.get_value()

        self.outputs = outputs
        assert is_valid_trans(inputs, outputs)  # sanity check
        self.validator_key = validator_key

        # Set the wallet origin id.
        # We perform this loop at the end of the init method,
        # because the identifier of this object can only be calculated AFTER all the properties has been set.
        for i, wallet in enumerate(outputs):
            wallet.set_origin_id(self.get_identifier(), i)

    def _encode_identity(self, bytebuffer: BytesIO):
        # Transaction identity is defined as the in/out wallets.
        # The key of the validator is ignored as it isn't of function need for the transaction

        # The wallets are encoded in the order that they appear in the lists.
        # That is why the wallet nr is not encoded.
        for input_wallet in self.inputs:
            input_wallet: Wallet
            input_wallet.encode_input_wallet_identity(bytebuffer)
        for output_wallet in self.outputs:
            output_wallet: Wallet
            output_wallet.encode_output_wallet_identity(bytebuffer)

    def get_parents(self):
        if len(self.parents) == 0:
            for entry in self.inputs:
                if not entry.get_origin() is None:
                    self.parents[entry.get_origin()] = entry.get_origin()

        return self.parents

    def get_value(self) -> Decimal:
        return Decimal(self.value)

    def get_inputs(self):
        return self.inputs

    def get_validator(self) -> bytes:
        return self.validator_key

    def add_signature(self, signature):
        """Takes :param signature as pair of (pk, sig) and only if pk matches one of the wallets PKs, it adds it to the
        field signatures.
        """
        for wallet in self.inputs:
            if wallet.get_pk() == signature[0]:
                self.signatures.append(signature)

    def get_signatures(self):
        return self.signatures

    def __str__(self):
        return "Transaction " + self.get_identifier().hex()


class TransactionIncentivesA(Transaction):
    """child class for use in Incentive Option A"""

    def acknowledge(self, signature, stake, total_stake):
        """:param signature: signature of the validator for the transaction
        :param stake: delegated to the validator
        :param total_stake: total amount of delegated stake in DAG
        """
        incentive = (
            self.value * constants.MONEY_GENERATION_MODIFIER * stake / total_stake
        )  # This is not a wallet.
        self.outputs.append(incentive)
        self.signatures.append(signature)

    def _encode_identity(self, bytebuffer: BytesIO):
        raise ValueError("This class is unfinished..")


class Acknowledge(Node):
    """Node for Acknowledgements to be used in Incentives Option B"""

    def __init__(self, transaction, prev_ack, pb_key):
        """:param transaction: id of to be acknowledged transaction
        :param prev_ack: identifier of last acknowledge-node
        :param signature: signature of the validator for the transaction
        """
        super().__init__()
        self.transaction = transaction
        self.prev_ack = prev_ack
        self.pb_key = pb_key

    def __hash__(self):
        return hash(self.get_identifier())

    def get_trans_id(self) -> bytes:
        return self.transaction

    @property
    def signature(self) -> Optional[Tuple[bytes, bytes]]:
        if len(self.signatures) == 0:
            return None
        if len(self.signatures) == 1:
            return self.signatures[0]
        raise ValueError("The ack has multiple signatures.")

    def get_signature(self):
        return self.signature

    def get_pb_key(self) -> Optional[bytes]:
        return self.pb_key

    def get_prev_ack(self) -> bytes:
        return self.prev_ack

    def _encode_identity(self, bytebuffer: BytesIO):
        """
        Encodes the identity of this acknowledgement to a byte string.
        Since including the dependency to prev_ack leads to issues in terms of uniqueness after checkpoint creation,
        prev_acks arent included for the encode method anymore.
        """
        bytebuffer.write(self.get_trans_id())

        if self.get_pb_key() is None:
            bytebuffer.write(b"MISSING_PB_KEY")
        else:
            bytebuffer.write(self.get_pb_key())

    def __str__(self):
        prev_ack = None

        if self.prev_ack is not None:
            prev_ack = self.prev_ack.hex()
        return f"Ack(id = {self.get_identifier().hex()}, txn={self.transaction.hex()}, prev_ack={prev_ack})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Acknowledge):
            return False
        other: Acknowledge
        if other.transaction != self.transaction:
            return False
        if other.prev_ack != self.prev_ack:
            return False
        if other.get_identifier() != self.get_identifier():
            return False
        return True


class Genesis(Node):
    """Genesis of the DAG"""

    def __init__(self, outputs):
        """ :param outputs: list of initial wealth distribution"""
        super().__init__()
        self.outputs = outputs
        self.value = get_wallet_value(outputs)
        self.inputs = []
        self.height = 0
        self.stake_dict = dict()
        self.total_stake = Decimal(self.value)
        self.utxos = list()

        for wallet in outputs:
            owner = wallet.get_pk()
            if owner not in self.stake_dict:
                self.stake_dict[owner] = Decimal(0)
            owned_money = self.stake_dict[owner]
            owned_money += wallet.value
            self.stake_dict[owner] = owned_money

        # Set the wallet origin id.
        # We perform this loop at the end of the init method,
        # because the identifier of this object can only be calculated AFTER all the properties has been set.
        for i, wallet in enumerate(outputs):
            wallet.set_origin_id(self.get_identifier(), i)

        self.id = self.get_identifier()

    def _encode_identity(self, bytebuffer: BytesIO):
        for wallet in self.outputs:
            wallet: Wallet
            wallet.encode_output_wallet_identity(bytebuffer)


class Checkpoint(Genesis):
    def __init__(
        self,
        origin: bytes,
        height: int,
        locktime: float,
        length: int,
        utxos: List[Wallet],
        outputs: List[Wallet],
        stake_list: Dict,
        nutxo: int,
        tstake: Decimal,
        tcoins: Decimal,
        miner: bytes,
    ):
        # checkpoint data
        Node.__init__(self)
        self.origin = origin  # Identifier of the last checkpoint
        self.height = height  # Height of the checkpoint
        self.utxos = utxos  # List of Unspent outputs finalized from the DAG
        self.outputs = outputs  # Newly generated outputs from fees
        self.stake_dict = stake_list  # Stake list
        self.miner = miner  # Public key of the checkpoint proposer
        self.inputs = []  # Required for genesis processing
        self.value = get_wallet_value(outputs)  # Total output value

        # statistical data
        self.nutxo = nutxo  # Total number of outputs in the Checkpoint
        self.lock_time = locktime  # Generation timestamp of the Checkpoint
        self.ack_length = length  # Trigger point of the Checkpoint
        self.total_stake = tstake  # Total stake at the Checkpoint
        self.total_coins = tcoins  # Total coins in the system at the Checkpoint

        for i, wallet in enumerate(outputs):
            wallet.set_origin_id(self.get_identifier(), i)
        self.id = self.get_identifier()

    def get_id(self) -> bytes:
        return self.get_identifier()

    def get_locktime(self) -> float:
        return self.lock_time

    def get_acklength(self) -> int:
        return self.ack_length

    def get_outputs(self) -> List[Wallet]:
        return self.outputs

    def get_fee_rewards(self) -> List[Wallet]:
        return self.outputs

    def get_outputs_len(self) -> int:
        return self.nutxo

    def get_stake_list(self) -> {}:
        return self.stake_dict

    def get_stake_sum(self) -> Decimal:
        if self.total_stake is None:
            return Decimal(0)
        else:
            return Decimal(self.total_stake)

    def get_total_coins(self) -> Decimal:
        return self.total_coins

    def get_origin(self) -> bytes:
        return self.origin

    def get_height(self) -> int:
        return self.height

    def get_miner(self) -> bytes:
        return self.miner

    def get_utxos(self) -> List[Wallet]:
        return self.utxos

    def get_stake(self, pk):
        """
        Returns the stake delegated to the given public key.
        """
        if pk in self.stake_dict:
            return Decimal(self.stake_dict[pk])
        else:
            return Decimal(0)

    def get_transaction_list(self) -> List[bytes]:
        txn = []
        for out in self.outputs:
            txn.append(out.origin)
        return list(set(txn))

    def generate_hash_id(self) -> bytes:
        content = hashlib.sha256()
        content.update(self.origin)
        # content.update(pack("d", self.lock_time))
        # content.update(pack("i", self.ack_length))
        # content.update(pack("i", self.nutxo))
        buffer = BytesIO()
        utxo_sorted = list(self.get_utxos())
        utxo_sorted.sort()
        for out in utxo_sorted:
            out: Wallet
            out.encode_input_wallet_identity(buffer)
        content.update(buffer.getvalue())
        del buffer

        stake_list = list(self.stake_dict.keys())
        stake_list.sort()
        content.update(pack("i", len(stake_list)))

        for key in stake_list:
            content.update(key)
            content.update(bytes(str(self.stake_dict[key]), "utf-8"))

        buffer = BytesIO()
        for reward in self.outputs:
            reward.encode_output_wallet_identity(buffer)
        content.update(buffer.getvalue())
        del buffer

        content.update(self.miner)
        return content.digest()

    def get_parents(self):
        parents = dict()
        parents[self.origin] = self.origin
        for input_wallet in self.utxos:
            input_wallet_origin = input_wallet.get_origin()
            parents[input_wallet_origin] = input_wallet_origin

    def _encode_identity(self, bytebuffer: BytesIO):
        bytebuffer.write(self.generate_hash_id())
