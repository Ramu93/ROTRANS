import base64
import logging
from decimal import Decimal
from enum import IntEnum
from io import BytesIO
from typing import Optional, Tuple, List
from abccore.DAG import Transaction
from abccore.DAG import Wallet, Checkpoint
from abccore.agent_crypto import auth_sign, auth_validate
from abccore.network_datastructures import NetTransaction, encode_wallet
from abcnet import transcriber
from abcnet.structures import ItemQualifier, ItemEncodeable
from abcnet.transcriber import Transcriber, Parser
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from abcckpt import fast_vrf
from abcckpt.ckpt_creation_state import CkptCreationState
from abcckpt.ckpt_creation_state import PreCkptStatus
from abcckpt.sortition import ValidatorProperties, SortitionProperties

logger = logging.getLogger("CkptItems")


class CkptItemType(IntEnum):
    PRIORITY = 0xabcce01
    CKPT_HASH = 0xabcce04
    VALVOTE = 0xabcce05
    CKPT_DATA = 0xabcce06

    MAJVOTES = 0xabcce07
    MOCK_CKPT_DATA = 0xabcce08
    CKPT = 0xabcce09
    CKPT_REQ = 0xabcce10


def encode_priority(t: Transcriber, pub_k: bytes, stake: Decimal, proof: bytes,
                    votes: int):
    t.nested_bytes(pub_k)
    t.write_text(str(stake))
    t.nested_bytes(proof)
    t.integer(votes)


def decode_priority(p: Parser):
    pub_k = p.consume_nested_bytes()
    stake = Decimal(p.consume_nested_text())
    proof = p.consume_nested_bytes()
    votes = p.consume_int()
    return pub_k, stake, proof, votes


def encode_state(transcriber: Transcriber, state: CkptCreationState):
    transcriber.nested_bytes(state.last_common_string)
    transcriber.integer(state.round)
    transcriber.integer(state.step_status)
    if state.chosen_validator is None:
        transcriber.nested_bytes(b'NO_VALIDATOR')
    else:
        transcriber.nested_bytes(state.chosen_validator)
    if state.content_hash is None:
        transcriber.nested_bytes(b'NO_HASH')
    else:
        transcriber.nested_bytes(state.content_hash)


def decode_state(parser: Parser) -> CkptCreationState:
    try:
        last_common_string = parser.consume_nested_bytes()
        round = parser.consume_int()
        step_status = parser.consume_int()
        chosen_validator = parser.consume_nested_bytes()
        content_hash = parser.consume_nested_bytes()
        if chosen_validator == b'NO_VALIDATOR':
            chosen_validator = None
        if content_hash == b'NO_HASH':
            content_hash = None

        return CkptCreationState(last_common_string, round, PreCkptStatus(step_status),
                                 chosen_validator, content_hash)
    except Exception as e:
        logger.error(f"Exception in parsing state, {e}")
        raise


class CkptMsg(ItemQualifier, ItemEncodeable):
    """Base class for item types in checkpoint module.
    """

    def __init__(self, state: CkptCreationState):
        self.signature: Optional[Tuple[bytes, bytes]] = None
        self._id: bytes = None
        self.state: CkptCreationState = state

    def check_id(self, other_id: bytes):
        self.get_id()  # Generate ID
        if other_id is None:
            return
        if self.get_id() != other_id:
            raise ValueError(f"Calculated ID, {self.get_id().hex()} doesn't match the given ID: {other_id.hex()}")

    def __set_id(self):
        """
        Sets id by hashing the content of the message converted into a buffer of bytes
        """
        digest = hashes.Hash(hashes.SHA512_256())
        bytebuffer = BytesIO()
        bytebuffer.write(transcriber.encode_int(self.item_type()))
        self._encode_id(bytebuffer)
        encoded_ = bytebuffer.getvalue()
        digest.update(encoded_)
        self._id = digest.finalize()

    def _encode_id(self, bytebuffer: BytesIO):
        """
        Writes the content of the object that makes up its identity into the given byte buffer.
        :param bytebuffer: io.ByteIO object that holds the content of this msg
        """
        t = Transcriber()
        self.encode(t, encode_identity_only=True)
        bytebuffer.write(t.msg.parts[0])

    def encode(self, transcriber: "Transcriber", encode_identity_only=False):
        if not encode_identity_only:
            transcriber.nested_bytes(self.get_id())
        encode_state(transcriber, self.state)
        if not encode_identity_only:
            if self.signature:
                transcriber.nested_bytes(self.signature[0])
                transcriber.nested_bytes(self.signature[1])
            else:
                transcriber.nested_bytes(b'NO_SIGN')
                transcriber.nested_bytes(b'NO_SIGN')

    def get_id(self) -> bytes:
        """
        The identifier of this message is returned. If id is not set, it is set with current contents.
        Do not call this function until all properties of this object has been set.
        :returns the identifier of this node.
        """
        if self._id is None:
            self.__set_id()
        return self._id

    def _compute_data_for_sign(self) -> bytes:
        data = bytes()
        data += self.get_id()
        return data

    def add_signature(self, key):
        """
        Set signature attribute by signing the message content using secret key.
        """
        data = self._compute_data_for_sign()
        sign: Tuple[bytes, bytes] = auth_sign(data, key)
        self.set_sign(sign)

    def set_sign(self, sign: Optional[Tuple[bytes, bytes]]) -> bool:
        if sign is not None:
            self.signature = sign
            return self.verify_signature()
        return True

    def verify_signature(self) -> bool:
        """
        Verify signature of the item.
        """
        if self.signature is None:
            return False
        data = self.get_id()
        return auth_validate(data, self.signature)

    def item_qualifier(self):
        return base64.urlsafe_b64encode(self.get_id()).rstrip(b"=").decode("utf-8")

    def __str__(self):
        return f'ItemQualifier(type={self.item_type()}, ' \
               f'qualifier={self._id})'

    def __eq__(self, other: "CkptMsg"):
        if other is None:
            return False
        if self.get_id() != other.get_id():
            return False
        if self.signature != other.signature:
            return False
        return True

    def __hash__(self):
        return hash(self.get_id())


class Priority(CkptMsg, ItemQualifier, ItemEncodeable):
    """
    Class for sending priority item of checkpoint creation for choosing a validator.
    """
    def __init__(self, state: CkptCreationState, pub_k: bytes, stake: Decimal, proof: bytes, votes: int,
                 id: bytes = None):
        CkptMsg.__init__(self, state)
        self.pub_k: bytes = pub_k
        self.stake: Decimal = stake
        self.proof: bytes = proof
        self.votes: int = votes
        self.check_id(id)

    @classmethod
    def from_validator_props(cls, state: CkptCreationState, validator_props: ValidatorProperties) -> "Priority":
        if validator_props is None or not isinstance(validator_props, ValidatorProperties):
            raise ValueError("Illegal validator properties: " + str(validator_props))
        return Priority(state=state, pub_k=validator_props.public_key,
                        stake=validator_props.stake, proof=validator_props.sortition.proof,
                        votes=validator_props.sortition.votes)

    def item_type(self):
        return CkptItemType.PRIORITY

    # def _encode_id(self, bytebuffer: BytesIO):
    #     t = Transcriber()
    #     self.encode(t, encode_identity_only=True)
    #     bytebuffer.write(t.msg.parts[0])

    def encode(self, transcriber, encode_identity_only=False):
        CkptMsg.encode(self, transcriber, encode_identity_only)
        encode_priority(transcriber, self.pub_k, self.stake, self.proof, self.votes)

    def get_validator_prop(self) -> ValidatorProperties:
        return ValidatorProperties(self.pub_k, b'', self.state.current_common_str, self.stake,
                                   self.get_sortition_prop())

    def get_sortition_prop(self) -> SortitionProperties:
        status, sample = fast_vrf.hash_vrf_proof_to_hash(self.proof)
        return SortitionProperties(self.proof, sample, self.state.current_common_str, self.votes)

    def get_sample(self) -> Decimal:
        return self.get_sortition_prop().sample

    def is_greater_than(self, other: "Priority") -> bool:
        if other is None or not isinstance(other, Priority):
            raise ValueError("Unexpected other object.")
        if self == other:
            return False
        if self.votes != other.votes:
            return self.votes > other.votes
        # Vote tiebreak, refer to the smaller sample:
        self_sample = self.get_sample()
        other_sample = other.get_sample()
        if self_sample != other_sample:
            return self_sample < other_sample
        # If samples and votes match, refer to the larger public key:
        if self.pub_k == other.pub_k:
            raise ValueError(f"Public keys match too.."
                             f" Something is wrong: {self}, other: {other}")
        return self.pub_k > other.pub_k

    def __str__(self):
        return f"Priority(id={self.item_qualifier()[:5]}," \
               f" state={self.state}," \
               f" pub_k={self.pub_k.hex()[:5]}," \
               f" stake={self.stake}," \
               f" proof={self.proof[:10]}," \
               f" votes={self.votes})"


class CkptHash(CkptMsg, ItemQualifier, ItemEncodeable):
    """
    Class for sending hash of checkpoint proposal.
    """

    def __init__(self, ckpt_state: CkptCreationState, ckpt_hash: bytes, id: bytes = None):
        """
        :param ckpt_hash: hash of the checkpoint proposal data to be sent
        :param id:
        """
        CkptMsg.__init__(self, ckpt_state)
        assert ckpt_state.chosen_validator is not None
        self.ckpt_hash = ckpt_hash
        self.check_id(id)

    def encode(self, transcriber, encode_identity_only=False):
        CkptMsg.encode(self, transcriber, encode_identity_only)
        transcriber.nested_bytes(self.ckpt_hash)

    def item_type(self):
        return CkptItemType.CKPT_HASH

    def get_ckpt_hash(self):
        """
        returns the hash of checkpoint referred in the message.
        """
        return self.ckpt_hash


class ValidatorVote(CkptMsg, ItemQualifier, ItemEncodeable):
    """
    Class for sending vote in each step of checkpoint creation.
    """
    def __init__(self, state: CkptCreationState, voted_item_id: Optional[str], voted_item_type: int, pub_key: bytes,
                 id: bytes = None):
        CkptMsg.__init__(self, state)
        if voted_item_type not in [CkptItemType.PRIORITY, CkptItemType.CKPT_HASH, CkptItemType.CKPT_DATA]:
            raise ValueError("Voted item id unrecognized: " + str(voted_item_type))
        self.voted_item_type: int = voted_item_type
        self.voted_item_id: Optional[str] = voted_item_id
        self.pub_key: bytes = pub_key
        self.check_id(id)

    @classmethod
    def create_and_sign(cls, state: CkptCreationState, voted_item_id: Optional[str], voted_item_type: int,
                        skey: Ed25519PrivateKey) \
            -> "ValidatorVote":
        pkb = fast_vrf.encode_pub_key(skey.public_key())
        vote = cls(state, voted_item_id, voted_item_type, pkb)
        vote.add_signature(skey)
        return vote

    def item_type(self):
        return CkptItemType.VALVOTE

    def encode(self, transcriber, encode_identity_only=False):
        CkptMsg.encode(self, transcriber, encode_identity_only)
        transcriber.integer(self.voted_item_type)
        vote_string = self.voted_item_id if not self.is_pass_vote() else "PASS"
        transcriber.write_text(vote_string)
        transcriber.nested_bytes(self.pub_key)

    def is_pass_vote(self):
        if self.voted_item_id is None:
            return True
        else:
            return False

    def verify_signature(self) -> bool:
        """
        Verify signature of the item.
        """
        if not CkptMsg.verify_signature(self):
            return False
        return self.pub_key == self.signature[0]


class MajorityVotes(CkptMsg, ItemQualifier, ItemEncodeable):
    """
    Class for sending majority vote found by each validator in each step of checkpoint creation.
    """
    def __init__(self, state: CkptCreationState, votes: List[str], voted_item_qualifier: str, id_: bytes = None):
        CkptMsg.__init__(self, state)
        if votes is None or len(votes) == 0:
            raise ValueError("Empty votes..")
        self.votes: List[str] = list(votes)
        self.votes.sort()
        self.voted_item_qualifier: str = voted_item_qualifier
        self.check_id(id_)

    # def _encode_id(self, bytebuffer: BytesIO):
    #     t = Transcriber()
    #     self.encode(t, encode_identity_only=True)
    #     bytebuffer.write(t.msg.parts[0])

    def encode(self, transcriber, encode_identity_only=False):
        CkptMsg.encode(self, transcriber, encode_identity_only)
        if self.voted_item_qualifier is None:
            transcriber.write_text("PASS")
        else:
            transcriber.write_text(self.voted_item_qualifier)
        transcriber.integer(len(self.votes))
        for v in self.votes:
            transcriber.write_text(v)

    def item_type(self):
        return CkptItemType.MAJVOTES

    def add_signature(self, key):
        raise Exception("Cannot set the signature of a majority vote item.")


class MockCkptData(CkptMsg, ItemQualifier, ItemEncodeable):
    """
    Mock proposal data class for test simulation.
    """
    def __init__(self, state: CkptCreationState, txn_list: List[Transaction], id_: Optional[bytes] = None):
        CkptMsg.__init__(self, state)
        self.txn_list: List[Transaction] = txn_list
        self.ckpt_hash = self.get_txn_hash(self.txn_list)
        self.check_id(id_)

    @staticmethod
    def get_txn_hash(txn_list: List[Transaction]) -> bytes:
        ckpt_hash = txn_list[0].get_identifier()
        for i in range(1, len(txn_list)):
            ckpt_hash = bytes([a ^ b for (a, b) in zip(ckpt_hash, txn_list[i].get_identifier())])
            # ckpt_hash = xor(ckpt_hash, txn_list[i].get_identifier())
        return ckpt_hash

    @classmethod
    def create_and_sign(cls, state: CkptCreationState, txn_list: List[Transaction],
                        skey: Ed25519PrivateKey) \
            -> "MockCkptData":
        ckpt_data = cls(state, txn_list)
        ckpt_data.add_signature(skey)
        return ckpt_data

    def item_type(self):
        return CkptItemType.MOCK_CKPT_DATA

    def encode(self, transcriber, encode_identity_only=False):
        CkptMsg.encode(self, transcriber, encode_identity_only)
        transcriber.integer(len(self.txn_list))
        for txn in self.txn_list:
            net_txn = NetTransaction(txn)
            net_txn.encode(transcriber)

    def get_ckpt_hash(self):
        return self.ckpt_hash


class CkptData(CkptMsg, ItemQualifier, ItemEncodeable):
    def __init__(self, ckpt_state: CkptCreationState, checkpoint_data: Checkpoint, item_id: bytes = None):
        """Class representing data structure for sending the checkpoint over the network.

        Parameters:
            ckpt_state: Consensus data object (Common string, round, status, step..)
            checkpoint_data (Checkpoint): proposed checkpoint to be sent.
            item_id (bytes): Unique content identity of the checkpoint.

        """
        super().__init__(ckpt_state)
        self.checkpoint_data = checkpoint_data
        self.ckpt_hash = checkpoint_data.id
        self.check_id(item_id)

    def get_ckpt_hash(self) -> bytes:
        """
        Returns the unique identifier of the message object.
        """
        return self.ckpt_hash

    def item_type(self) -> IntEnum:
        """
        Returns the item type of the message object.
        """
        return CkptItemType.CKPT_DATA

    def _encode_id(self, bytebuffer: BytesIO):
        t = Transcriber()
        encode_state(t, self.state)
        bytebuffer.write(t.content)
        bytebuffer.write(self.ckpt_hash)

    def encode(self, transcriber, encode_identity_only=False):
        """
        Encodes the checkpoint object into bytes.
        """
        CkptMsg.encode(self, transcriber, encode_identity_only)
        ckpt_stake_list = ''
        for key in self.checkpoint_data.stake_dict:
            ckpt_stake_list += key.hex() + ':' + str(self.checkpoint_data.stake_dict[key]) + ';'

        transcriber.nested_bytes(self.checkpoint_data.id, "CID")
        transcriber.nested_bytes(self.checkpoint_data.origin, "PARENT")
        transcriber.integer(self.checkpoint_data.height)
        transcriber.write_double(self.checkpoint_data.lock_time, "TIME")
        transcriber.integer(self.checkpoint_data.ack_length, "LENGTH")
        encode_wallet(transcriber, self.checkpoint_data.utxos)
        encode_wallet(transcriber, self.checkpoint_data.outputs)
        transcriber.integer(self.checkpoint_data.nutxo, "NUTXO")
        transcriber.write_text(ckpt_stake_list, "STAKEL")
        transcriber.write_text(str(self.checkpoint_data.total_stake), "TSTAKE")
        transcriber.write_text(str(self.checkpoint_data.total_coins), "TCOIN")
        transcriber.nested_bytes(self.checkpoint_data.miner, "MINER")

    def verify_signature(self) -> bool:
        """
        Verifies signature of the item.

        Returns: True if signature verifies.
        """
        if not CkptMsg.verify_signature(self):
            return False
        return self.state.chosen_validator == self.signature[0]


