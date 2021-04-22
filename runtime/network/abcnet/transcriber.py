from io import BytesIO
from typing import List, Optional, Union, AnyStr, Tuple, Iterable, Any
from struct import pack, unpack
import logging

from abcnet.structures import *

logger = logging.getLogger(__name__)

NET_INT_SIZE = 4
NET_DOUBLE_SIZE = 8
NET_PARTS_MAX = 1000


def encode_int(number: int) -> bytes:
    if number < 0:
        raise ValueError("Cannot encode a negative integer. Convert integer to string and use write_text instead.")
    four_byte_magic_number = abs(number) & 0xFFFFFFFF
    return four_byte_magic_number.to_bytes(NET_INT_SIZE, 'big')


def decode_int(number_b: bytes) -> int:
    magic_number = int.from_bytes(number_b, byteorder='big')
    return magic_number


class Transcriber:
    """
    Used to transcribe messages to byte.
    """
    
    class NestedTranscriber:

        def __init__(self, parent_msg: Union["Transcriber.NestedTranscriber", "Transcriber"]):
            self.c = BytesIO()
            self.parent_msg = parent_msg


        def _write_to_buffer(self, content: bytes):
            self.c.write(content)

        def _collapse(self):
            self.parent_msg._collapse_nested_msg(self.c.getbuffer())

        def _collapse_nested_msg(self, sub_msg: bytes):
            self.c.write(encode_int(len(sub_msg)))
            self.c.write(sub_msg)

        def _pos(self):
            return len(self.c.getbuffer()) + self.parent_msg._pos()

    def __init__(self):
        self._parts: List[BytesIO] = list()
        self._cursor: BytesIO = None
        self._msg_type = None
        self._nested_transcriber: Union[Transcriber.NestedTranscriber, Transcriber] = self
        self.next_msg()

    def next_msg(self):
        if self._nested_transcriber is not self:
            raise RuntimeError("Nested message still pending and next message is called.")
        self._cursor = BytesIO()
        self._parts.append(self._cursor)

    def nested_msg(self):
        self._nested_transcriber = Transcriber.NestedTranscriber(self._nested_transcriber)
        return self

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._nested_transcriber is self:
            raise RuntimeError("First call nested message()")
        self._nested_transcriber._collapse()
        self._nested_transcriber = self._nested_transcriber.parent_msg

    def __msg_nr(self):
        return len(self._parts)

    def _pos(self):
        return len(self._cursor.getbuffer())

    def __debug_log(self, content: bytes, content_type: str = ""):
        if content_type and logger.isEnabledFor(logging.DEBUG):
            content_len = 0
            if content:
                content_len = len(content)
            logger.debug("Message %d, position %d, length %d: %s", self.__msg_nr(), self._nested_transcriber._pos(), content_len, content_type)

    def _write_to_buffer(self, content: bytes):
        self._cursor.write(content)

    def _collapse_nested_msg(self, sub_msg: bytes):
        self._cursor.write(encode_int(len(sub_msg)))
        self._cursor.write(sub_msg)

    def write_double(self, double_val: float, content_desc: str= ""):
        self.write_byte(pack('d', double_val), content_desc)

    def write_text(self, text_content: AnyStr, content_desc: str = ""):
        with self.nested_msg():
            if text_content:
                self.write_byte(bytes(text_content, "utf-8"), content_desc)

    def write_byte(self, content: bytes, content_desc: str = ""):
        self.__debug_log(content, content_desc)
        if content:
            self._nested_transcriber._write_to_buffer(content)

    def magic_nr(self, magic_nr: int):
        if self.__msg_nr() != 1:
            logger.warning("Writing magic number in message nr %d", self.__msg_nr())

        if logger.level >= logging.DEBUG:
            pos = self._pos()
            if pos > 0:
                logger.warning("Writing magic number at position %d", pos)
        magic_nr_b = encode_int(magic_nr)
        self.write_byte(magic_nr_b, "Network Magic Number " + hex(magic_nr))

    @staticmethod
    def __check_nr(nr: int, positive=False, bounded=True):
        if positive:
            if nr < 0:
                raise ValueError("Illegal number, its negative: " + str(nr))
        if bounded:
            if nr > 0xEFFFFFFF:
                raise ValueError("Illegal number, larger than 4 bytes: " + str(nr))

    def m_type(self, msg_type: MsgType):
        msg_type_b = encode_int(msg_type.value)
        self._msg_type = msg_type
        self.write_byte(msg_type_b, "Message Type " + str(msg_type))

    def integer(self, value: int, content_desc=""):
        value_b = encode_int(value)
        self.write_byte(value_b, content_desc)

    def nested_bytes(self, byte_arr: bytes, content_desc=""):
        with self.nested_msg():
            self.write_byte(byte_arr, content_desc)

    def content_length(self, length: int):
        self.__check_nr(length)
        length_b = encode_int(length)
        self.write_byte(length_b, "Content length " + str(length))

    def contact_qualifier(self, contact: PeerContactQualifier):
        self.write_text(contact.identifier, "Contact Identifier")

    def contact_info(self, contact: PeerContactInfo):
        with self.nested_msg():
            self.write_text(contact.identifier, "Contact Identifier")
            with self.nested_msg():
                self.write_byte(contact.public_key, "Public Key")
            self.write_text(contact.publish_addr, "Publish address")
            self.write_text(contact.receive_addr, "Receive address")

    def ping(self, ping: Ping):
        with self.nested_msg():
            self.write_text(ping.ping_id, "Ping Id")
            if ping.original_peer:
                self.contact_qualifier(ping.original_peer)
            else:
                self.empty()
            self.write_double(ping.send_time.start_time, "Ping start time")

    def pong(self, pong: Pong):
        with self.nested_msg():
            self.ping(pong.ping)
            self.contact_qualifier(pong.replier)
            self.write_double(pong.reply_time.start_time, "Pong reply time")

    def item_qualifier(self, item: ItemQualifier):
        self.integer(item.item_type(), "Item Type")
        self.write_text(item.item_qualifier(), "Item Qualifier")

    def item_content(self, item: ItemEncodeable):
        self.integer(item.item_type(), "Item Type")
        with self.nested_msg():
            item.encode(self)

    def empty(self):
        with self.nested_msg():
            pass

    @property
    def content(self) -> bytes:
        if len(self._parts) > 1:
            raise Exception("Cannot get the single content byte out of a multi part message. Use msg instead.")
        return self._parts[0].getvalue()

    @property
    def msg(self) -> Message:
        m = Message(msg_parts=[bytesio.getvalue() for bytesio in self._parts], msg_type=self._msg_type)
        return m




class Parser:

    def __init__(self, b: bytes):
        self._is_empty = len(b) == 0
        self.c: BytesIO = BytesIO(b)

    def is_empty(self):
        return self._is_empty

    def consume_int(self) -> int:
        return decode_int(self.c.read(NET_INT_SIZE))

    def consume_double(self) -> float:
        return unpack('d', self.c.read(NET_DOUBLE_SIZE))[0]

    def consume_rest_as_text(self) -> str:
        return self.c.read().decode('utf-8')

    def __nested_msg(self) -> Tuple[int, bytes]:
        nested_msg_len = self.consume_int()
        nested_msg = self.c.read(nested_msg_len)
        if len(nested_msg) < nested_msg_len:
            raise RuntimeError("Message is malformed."
                               f" Expected a nested message with length {nested_msg_len} "
                               f" but found a nested message with length {len(nested_msg)}.")
        return nested_msg_len, nested_msg

    def parse_nested(self) -> "Parser":
        _, nested_msg = self.__nested_msg()
        return Parser(nested_msg)

    def consume_nested_text(self) -> str:
        _, nested_msg = self.__nested_msg()
        return nested_msg.decode('utf-8')

    def consume_text(self) -> str:
        return self.consume_nested_text()

    def consume_nested_bytes(self) -> bytes:
        _, nested_msg = self.__nested_msg()
        return nested_msg

    def consume_ping(self) -> Ping:
        ping_id: str = self.consume_nested_text()
        origin_peer_parser = self.parse_nested()
        if origin_peer_parser.is_empty():
            origin = None
        else:
            origin: PeerContactQualifier = origin_peer_parser.consume_contact_qualifier()
        send_time: float = self.consume_double()
        return Ping(origin, ping_id, StopTimer(send_time))

    def consume_pong(self) -> Pong:
        ping_parser = self.parse_nested()
        ping: Ping = ping_parser.consume_ping()
        replier_parser = self.parse_nested()
        sender: PeerContactQualifier = replier_parser.consume_contact_qualifier()
        send_timer: float = self.consume_double()
        return Pong(ping, sender, StopTimer(send_timer))

    def consume_contact(self) -> PeerContactInfo:
        identifier = self.consume_nested_text()
        public_key = self.consume_nested_bytes()
        publish_addr = self.consume_nested_text()
        receive_addr = self.consume_nested_text()

        public_key = public_key if public_key else None
        publish_addr = publish_addr if publish_addr else None
        receive_addr = receive_addr if receive_addr else None

        return PeerContactInfo(identifier, public_key, publish_addr, receive_addr)

    def consume_contact_qualifier(self) -> PeerContactQualifier:
        identifier = self.consume_rest_as_text()
        return PeerContactQualifier(identifier)

    def consume_item_content(self):
        item_type = self.consume_int()
        item_content = self.consume_nested_bytes()
        return item_type, item_content

    def consume_item_qualifier(self):
        item_type = self.consume_int()
        item_qualifier = self.consume_nested_text()
        return item_type, item_qualifier


def parse_contacts_qualifier(msg: Message) -> List[PeerContactQualifier]:
    body: bytes = msg.parts[1]
    main_parser: Parser = Parser(body)
    main_parser.consume_int()  # message type
    contact_count: int = main_parser.consume_int()
    contacts: List[PeerContactQualifier] = list()
    for i in range(contact_count):
        contact_parser: Parser = main_parser.parse_nested()
        contact = contact_parser.consume_contact_qualifier()
        contacts.append(contact)
    return contacts


def parse_magic_number(msg: Message) -> int:
    header: bytes = msg.parts[0]
    if len(header) < NET_INT_SIZE:
        raise ValueError("No magic number specified in the header.")
    return decode_int(header[:NET_INT_SIZE])


def parse_message_type(msg: Message) -> MsgType:
    try:
        msg_type_number: int = decode_int(msg.parts[1][0:NET_INT_SIZE])
    except (ValueError, IndexError) as e:
        raise ValueError("No message type was specified.\n"
                         "Looked at the first four bytes of the second part.\n" +
                         str(e))
    try:
        msg_type = MsgType(msg_type_number)
        return msg_type
    except ValueError as e:
        raise ValueError("Encoded message type was not recognized: " +
                         str(msg_type_number), e)


def parse_contacts(msg: Message) -> List[PeerContactInfo]:
    body: bytes = msg.parts[1]
    main_parser: Parser = Parser(body)
    main_parser.consume_int()  # message type
    contact_count: int = main_parser.consume_int()
    contacts: List[PeerContactInfo] = list()
    for i in range(contact_count):
        contact_parser: Parser = main_parser.parse_nested()
        contact = contact_parser.consume_contact()
        contacts.append(contact)
    return contacts


def parse_ping(msg: Message) -> Ping:
    body: bytes = msg.parts[1]
    main_parser: Parser = Parser(body)
    main_parser.consume_int()  # message type
    ping_parser = main_parser.parse_nested()
    return ping_parser.consume_ping()


def parse_pong(msg: Message) -> Pong:
    body: bytes = msg.parts[1]
    main_parser: Parser = Parser(body)
    main_parser.consume_int()  # message type
    pong_parser = main_parser.parse_nested()
    return pong_parser.consume_pong()


def parse_item_contents(msg: Message) -> List[Tuple[int, bytes]]:
    body: bytes = msg.parts[1]
    mt = parse_message_type(msg)
    if mt != MsgType.items_content:
        raise ValueError("Msg type is mismatching. Expected items_content but found: " + str(mt))
    main_parser: Parser = Parser(body)
    main_parser.consume_int()  # message type
    item_count: int = main_parser.consume_int()
    items: List[Tuple[int, bytes]] = list()
    for i in range(item_count):
        item_type, item_content = main_parser.consume_item_content()
        items.append((item_type, item_content))
    return items


def parse_item_qualifier(msg: Message) -> List[Tuple[int, str]]:
    body: bytes = msg.parts[1]
    mt = parse_message_type(msg)
    if not MsgType.is_items(mt):
        raise ValueError("Msg type is mismatching. Expected items message but found: " + str(mt))
    main_parser: Parser = Parser(body)
    main_parser.consume_int()  # message type
    item_count: int = main_parser.consume_int()
    items: List[Tuple[int, str]] = list()
    for i in range(item_count):
        item_type, item_qualifier = main_parser.consume_item_qualifier()
        items.append((item_type, item_qualifier))
    return items


class ItemsParser:

    def decode_item_bytes(self, item_type: int, item_content: bytes) -> Any:
        return self.decode_item(item_type, Parser(item_content))

    def decode_item(self, item_type: int, parser: Parser) -> Any:
        return None

    def decode_item_list_raw(self, items_list_raw: Iterable[Tuple[int, bytes]]) -> Iterable[Tuple[int, Any]]:
        return map(lambda item: (item[0], self.decode_item_bytes(item[0], item[1])),
                        items_list_raw)


def join_msg_parts(msg_parts: List[bytes]) -> bytes:
    """
    Given a list of bytes, this method joins them into a single bytes object.
    The output can be used to split the message parts using the `split_msg_parts` method.
    """
    if not msg_parts:
        raise ValueError("Empty msg parts")
    t = Transcriber()
    t.integer(len(msg_parts))
    for part in msg_parts:
        t.nested_bytes(part)
    return t.msg.parts[0]


def split_msg_parts(msg_bytes: bytes) -> List[bytes]:
    """
    Given joined message bytes objects this method splits the message parts and returns a list of bytes object.
    """
    if not msg_bytes:
        raise ValueError("Empty msg bytes")
    parser = Parser(msg_bytes)
    msg_part_count = parser.consume_int()
    parts = []
    if msg_part_count <= 0 or msg_part_count >= NET_PARTS_MAX:
        raise ValueError(f"Illegal message part count: {msg_part_count}")
    for i in range(msg_part_count):
        part = parser.consume_nested_bytes()
        parts.append(part)
    return parts


def msg_network_bytes(m: Message) -> bytes:
    t = Transcriber()
    t.nested_bytes(join_msg_parts(m.parts))
    t.nested_bytes(m.signature)
    return t.content

def msg_from_network_bytes(network_bytes: bytes) -> Message:
    parser = Parser(network_bytes)
    content = parser.consume_nested_bytes()
    signature = parser.consume_nested_bytes()
    parts = split_msg_parts(content)
    m = Message(parts)
    if signature:
        m.signature = signature
    return m


def parse_sender(m: Message) -> Optional[PeerContactQualifier]:
    if len(m.parts) < 3:
        return None
    parser = Parser(m.parts[2])
    return parser.parse_nested().consume_contact_qualifier()