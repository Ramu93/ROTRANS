import inspect
import secrets
import random
from re import Pattern
import re
from enum import IntEnum
from typing import AnyStr, Callable, Dict, List, Optional, Tuple, Union, Set
from uuid import uuid4


from abcnet.timer import StopTimer

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)

# Forward import
@property
def transcriber(tsn=[]) -> "transcriber":
    if tsn:
        return tsn[0]
    else:
        import transcriber as ts
        tsn.append(ts)
        return transcriber




def _shorten(qualifier: AnyStr) -> AnyStr:
    return qualifier[:min(7, len(qualifier))]


def __pattern_checker(regex_pattern: Pattern, variable_name) -> Callable[[AnyStr], None]:
    def checker(variable):
        if not regex_pattern.match(variable):
            raise ValueError(
                "{}:{} does not match required pattern: {}.".format(variable_name, variable,  regex_pattern.pattern))
    return checker


# ---- Regexes:
_qualifier_pc = __pattern_checker(re.compile("^[A-Za-z0-9-]+$"), "Qualifier")


def check_qualifier(qualifier: AnyStr) -> AnyStr:
    """
    | Checks the qualifier string of an entity.
    | Does nothing if the qualifier is legal.
    | Throws ValueError if the qualifier is not legal.
    | A qualifier is allowed must use only A-Z, a-z, 0-9 and hyphen (-) and be at least one character long
    :param qualifier: Qualifier to be checked.
    :type qualifier: str
    :return: None
    :rtype: None
    """
    if not isinstance(qualifier, str):
        raise ValueError("Qualifier is not of str type.")
    _qualifier_pc(qualifier)
    return qualifier


class MsgType(IntEnum):
    """
    Some standard message types.
    Every Message has a distinct message type which signals its content and format.
    There can be more messages that these.
    """
    items_content = 0xabc001
    items_checklist = 0xabc002
    items_request = 0xabc003
    items_notfound = 0xabc004

    contacts_content = 0xabc005
    contacts_checklist = 0xabc006
    contacts_request = 0xabc007

    ping = 0xabc008
    pong = 0xabc009

    @staticmethod
    def is_items(msg_type: int, item_msg_type_set={items_content, items_notfound,
                                                   items_request, items_checklist}) -> bool:
        """
        Returns True, iff the msg type is one of the four item message types.

        :param msg_type: to be checked item type.
        :type msg_type: int or MsgType
        :return: true if the given msg type is one of the four item types.
        :rtype:bool
        """
        return msg_type in item_msg_type_set


class Message:
    """
    A abc message.
    Holds msg parts and msg type.
    Can also hold any additional meta information that can be attached.
    Only the msg_parts are the content that is serialized.
    """
    def __init__(self, msg_parts: List[bytes], msg_type: MsgType = None):
        self._msg_parts: List[bytes] = list()
        self._signature: Optional[bytes] = None
        self._finalized: bool = False
        self._auth: bool = False
        self._sender: Optional[Contact] = None
        self._is_direct_msg: bool = False
        self._msg_type: MsgType = msg_type
        self._items: List = None
        self._item_type_set: Set[int] = set()
        self._discarded: bool = False
        if msg_parts:
            if not isinstance(msg_parts, list):
                raise ValueError("Message parts are not a list.")
            else:
                self._msg_parts: List[bytes] = msg_parts
                self._finalized: bool = False

    @property
    def final(self) -> bool:
        return self._finalized

    def finalize(self):
        self._finalized = True

    @property
    def parts(self) -> List[bytes]:
        return self._msg_parts

    @property
    def signature(self) -> Optional[bytes]:
        return self._signature

    @signature.setter
    def signature(self, sig: bytes):
        if sig is None:
            raise ValueError()
        # if len(self.parts) == 3:
        #     self.parts.append(sig)
        # else:
        #     raise ValueError("Require exactly 3 message parts to add signature. "
        #                      "Currently have: " + str(len((self.parts))))
        self._signature = sig

    @property
    def is_direct(self):
        return self._is_direct_msg

    @is_direct.setter
    def is_direct(self, is_dir):
        self._is_direct_msg = is_dir

    def __iadd__(self, part: bytes):
        self.add_part(part)
        return self

    def add_part(self, part: bytes):
        if self.final:
            raise RuntimeError("Message is final. Cannot add a message part.")
        self._msg_parts.append(part)

    @property
    def is_authenticated(self) -> bool:
        return self._auth

    def __set_authenticated(self):
        self._auth = True

    @property
    def sender(self) -> Optional["Contact"]:
        return self._sender

    @sender.setter
    def sender(self, sender: "Contact"):
        self._sender = sender

    @property
    def msg_type(self) -> int:
        if not self._msg_type:
            raise ValueError("Message type is not defined.")
        return self._msg_type

    @msg_type.setter
    def msg_type(self, msg_type: MsgType):
        self._msg_type = msg_type

    @property
    def items(self) -> List[Tuple[int, Union[str, bytes]]]:
        return self._items

    @items.setter
    def items(self, value: List[Tuple[int, Union[str, bytes]]]) -> None:
        self._items = value
        self._item_type_set.clear()
        for item_type, _ in self._items:
            self._item_type_set.add(item_type)

    def has_item_of_type(self, item_type: int):
        return item_type in self._item_type_set

    @property
    def is_discarded(self):
        return self._discarded

    def discard(self):
        self._discarded = True

    def __str__(self):
        return f'Message(parts={len(self.parts)},' \
               f' lengths={[len(p) for p in self.parts]})'


class PeerContactQualifier:
    """
    Holds the id of a network peer.
    """

    def __init__(self, qualifer: AnyStr):
        check_qualifier(qualifer)
        self._qualifier = qualifer

    @property
    def identifier(self) -> AnyStr:
        """
        c.identifier() -> AnyStr

        Returns the unique identifier of this contact.
        This is usually a uuid such as: ``ad30cd39-7a76-4523-bf52-bfe9f0ae9a3c``

        The returned object is not mutable,
        thus it can be safely used as keys in caches and such.

        :return: The unique identifier of the contact.
        """
        return self._qualifier

    def __str__(self):
        return f'{_shorten(self.identifier)}'

    def __repr__(self):
        return f'{_shorten(self.identifier)}'

    def __eq__(self, other):
        return isinstance(other, PeerContactQualifier) and other.identifier == self.identifier


class PeerContactInfo(PeerContactQualifier):
    """
    Holds information about a single network peer, such as a validator.
    This information can be used to contact the peer, given a ChannelService.
    In context of this class this peer is referred to as ``contact``.
    """

    def __init__(self, qualifer: AnyStr, pub_key: Optional[bytes], publish_addr: AnyStr, rec_addr: AnyStr):
        super().__init__(qualifer)
        if pub_key is not None:
            if not isinstance(pub_key, bytes):
                raise ValueError("Public key malformed")
        self._pub_key = pub_key
        self._publish_addr = publish_addr
        self._rec_addr = rec_addr

    @staticmethod
    def from_dict(dict_def: Dict) -> "PeerContactInfo":
        pubkey = None
        if 'pubKey' in dict_def:
            pubkey = bytes.fromhex(dict_def['pubKey'])
        contact_info = PeerContactInfo(qualifer=dict_def['id'],
                               pub_key=pubkey,
                               rec_addr=dict_def.get('receiveAddr', None),
                               publish_addr=dict_def.get('publishAddr', None))
        return contact_info

    @property
    def public_key(self) -> bytes:
        """
        c.public_key() -> bytes

        Returns the public key of this contact in form of a byte array.
        If the returned bytes object is empty,
        then no public key of the peer is known.

        If the public key is present (the returned bytes is not empty),
        the bytes object is encoded in PEM format, containing a single elliptic curve public key.

        :return: Public key of the contact, or empty bytes if unknown.
        """
        return self._pub_key

    @public_key.setter
    def public_key(self, public_key_bytes):
        """
        Sets the public key bytes of this peer.
        """
        self._pub_key = public_key_bytes

    @property
    def publish_addr(self) -> AnyStr:
        """
        c.publish_addr() -> AnyStr

        Returns the publish address of this contact.

        If the returned string is None or empty, the publish address is not available.
        A publish address can eventually become available.
        So calling this method multiple times can result different values.

        The return string is url formatted, such as: "tcp://example.com:2912"
        :return: The publish address of this contact.
        """
        return self._publish_addr

    @property
    def receive_addr(self) -> AnyStr:
        """
        c.receive_addr() -> AnyStr

        Returns the receive address of this contact.

         If the returned string is None or empty, the receive address is not available.
        A receive address can eventually become available.
        So calling this method multiple times can result different values.

        The returned string is url formatted, such as: "tcp://example.com:2912"
        :return: The receive address of this contact.
        """
        return self._rec_addr

    @property
    def is_publisher(self) -> bool:
        """
        :return: True, iff the contact has non empty ``publish_addr``.
        """
        if self.publish_addr:
            return True
        else:
            return False

    @property
    def is_reachable(self) -> bool:
        """
        :return: True, iff the contact has non empty ``receive_addr``.
        """
        if self.receive_addr:
            return True
        else:
            return False

    @property
    def is_fullnode(self) -> bool:
        """
        :return: True, iff the contact is ``is_reachable`` and ``is_publisher``.
        """
        return self.is_reachable and self.is_publisher

    def __repr__(self):
        return  f'PeerContactInfo(qualifer={self.identifier}, ' \
                f'pub_key={self.public_key}, ' \
                f'publish_addr={self.publish_addr}, ' \
                f'rec_addr={self.receive_addr})'

    def __eq__(self, other: "PeerContactInfo"):
        return super(PeerContactInfo, self).__eq__(other) and \
            isinstance(other, PeerContactInfo) and \
            ((not self.public_key and not other.public_key) or (self.public_key == other.public_key)) and \
            self.publish_addr == other.publish_addr and self.receive_addr == other.receive_addr


Qualifier = Union[str, PeerContactInfo, PeerContactQualifier]
"""
Type name of the union of PeerContactInfo and PeerContactQualifier or string.
A object of type Qualifier can be transformed to str by the use of get_qualifier helper method.
"""

Contact = Union[PeerContactInfo, PeerContactQualifier]
"""
Type name of any contact object
"""

class SocketBinding:
    """
    Represents information about how to bind the correct sockets.
    """
    def __init__(self, publish_addr: str, direct_receive_addr: str):
        self._publish_addr = publish_addr
        self._direct_addr = direct_receive_addr

    @staticmethod
    def from_dict(dict_def: Dict) -> "SocketBinding":
        direct_addr = None
        publish_addr = None
        if 'receiveAddr' in dict_def:
            direct_addr = dict_def['receiveAddr']
        if 'publishAddr' in dict_def:
            publish_addr = dict_def['publishAddr']
        if 'bindReceiveAddr' in dict_def:
            direct_addr = dict_def['bindReceiveAddr']
        if 'bindPublishAddr' in dict_def:
            publish_addr = dict_def['bindPublishAddr']
        return SocketBinding(publish_addr=publish_addr, direct_receive_addr=direct_addr)

    @property
    def bind_publish_addr(self) -> Optional[str]:
        return self._publish_addr

    @property
    def bind_direct_addr(self) -> Optional[str]:
        return self._direct_addr


def get_qualifier_helper(q: Qualifier) -> str:
    """
    Helper method that is used to convert any qualifier Object to ``str`` type.
    """
    if isinstance(q, PeerContactQualifier):
        return q.identifier
    if isinstance(q, str):
        return q
    raise ValueError("Unrecognized qualifier: " + str(q))


class NetPrivKey:
    """
    Key used for signing messages.
    """

    def __init__(self, private_key: Union[Ed25519PrivateKey, bytes] = None):
        if private_key is None:
            raise ValueError("Private key is None.")
        if isinstance(private_key, bytes):
            self._private_key_bytes: bytes = private_key
            self._private_key: Ed25519PrivateKey = Ed25519PrivateKey.from_private_bytes(private_key)
        elif isinstance(private_key, Ed25519PrivateKey):
            self._private_key_bytes: bytes = private_key.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
            self._private_key: Ed25519PrivateKey = private_key
        else:
            raise ValueError("Unrecognized private key type: " + str(private_key))
        pass

    @staticmethod
    def gen_key(seed: Optional[Union[str, bytes, int]] = None) -> Ed25519PrivateKey:
        """
        Generates private key from the given seed.
        If the seed is None the returned private key is selected from a secure random source.
        """
        if seed is None:
            key_bytes = secrets.token_bytes(32)
        else:
            prng = random.Random(seed)
            key_bytes = bytearray(prng.getrandbits(8) for _ in range(32))
        return Ed25519PrivateKey.from_private_bytes(key_bytes)

    @classmethod
    def from_seed(self, seed: Optional[Union[bytes, int, str]] = None) -> "NetPrivKey":
        """
        Creates the private key from the given seed.
        This method deterministically creates a private key if seed is not None.
        If seed is None this method securely calcucaltes a random private key.
        """
        key = self.gen_key(seed)
        return NetPrivKey(key)

    @classmethod
    def from_dict(self, dictionary: Dict) -> Optional["NetPrivKey"]:
        if "net_private_key_bytes" in dictionary:
            return NetPrivKey(dictionary["private_key_bytes"])
        elif "net_private_key_seed" in dictionary:
            return NetPrivKey.from_seed(dictionary["net_private_key_seed"])
        return None

    @property
    def private_key(self) -> Ed25519PrivateKey:
        return self._private_key

    @staticmethod
    def pub_key_from_bytes(pub_key_bytes: bytes) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(pub_key_bytes)

    @property
    def public_key_bytes(self) -> bytes:
        return self.private_key.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)




class ItemType(IntEnum):
    """
    Holds the three most iconic item types in abc protocol:
    TXN: Transaction
    ACK: Acknowledgement
    CHP: Checkpoint
    """
    TXN = 0xabce01
    ACK = 0xabce02
    CHP = 0xabce03

    UNSPENT_WALLET_COLLECTION = 0xabce04

    def __str__(self):
        return f'ItemType({self.name}, {self.value}'


class ItemQualifier:
    """
    Base class of items datatypes that have an id.
    """
    def item_type(self) -> int:
        pass

    def item_qualifier(self) -> AnyStr:
        pass

    def __str__(self):
        return f'ItemQualifier(type={self.item_type()}, ' \
               f'qualifier={_shorten(self.item_qualifier())})'


class ItemEncodeable:
    """
    Base class of items that can encode their content into a the given transcriber.
    """

    def item_type(self) -> int:
        pass

    def encode(self, transcriber: "Transcriber"):
        pass


class Ping:
    """
    Ping has an id and a send time and a original peer that signals the origin of the ping message.
    """
    def __init__(self, origin_peer: Optional[Qualifier] = None,
                 ping_id: str = None, send_time: StopTimer = None):
        if isinstance(origin_peer, str):
            origin_peer = PeerContactQualifier(origin_peer)
        self._origin_peer: Optional[PeerContactQualifier]= origin_peer
        self._ping_id: str = ping_id
        if not ping_id:
            self._ping_id = str(uuid4())
        self._st: StopTimer = send_time
        if not send_time:
            self._st = StopTimer()

    @property
    def original_peer(self) -> Optional[PeerContactQualifier]:
        return self._origin_peer

    @property
    def ping_id(self) -> str:
        return self._ping_id

    @property
    def send_time(self) -> StopTimer:
        return self._st

    def __eq__(self, other: "Ping"):
        return isinstance(other, Ping) and self.ping_id == other.ping_id

    def __hash__(self):
        return hash((1, self.ping_id))

    def __str__(self):
        return f'Ping({_shorten(self.ping_id)})'


class Pong:
    """
    Pong is the response to a ping message and has the qualifier of the replier together with the reply time.
    """
    def __init__(self, ping: Ping, replier: PeerContactQualifier, reply_time: StopTimer = None):
        self._ping = ping
        self._rep: PeerContactQualifier = replier
        if not replier or not isinstance(replier, PeerContactQualifier):
            raise ValueError("Provide a replier to a ping.")
        self._rt: StopTimer = reply_time
        if not reply_time:
            self._rt = StopTimer()

    @property
    def ping(self) -> Ping:
        return self._ping

    @property
    def replier(self) -> PeerContactQualifier:
        return self._rep

    @property
    def reply_time(self) -> StopTimer:
        return self._rt

    def __str__(self):
        return f'Pong({_shorten(self._ping.ping_id)})'

    def __hash__(self):
        return hash((0, self._ping.ping_id, self.replier.identifier))

    def __eq__(self, other: "Pong"):
        return isinstance(other, Pong) and \
                self.ping == other.ping and \
                self.replier.identifier == other.replier.identifier


def get_caller(stacks=2):
    caller_str = ""
    caller = "" # Assign a string so it can be deleted even if an exception is thrown before inspect finishes.
    try:
        caller = inspect.getframeinfo(inspect.stack()[stacks][0])
        caller_str = f"File \"{caller.filename}\", line {caller.lineno} in {caller.function}"
    except Exception:
        pass
    finally:
        del caller
    return caller_str