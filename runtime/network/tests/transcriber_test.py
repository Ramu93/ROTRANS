import logging
from typing import List

from abcnet import transcriber
from abcnet.settings import MAGIC_NUMBERS, configure_test_logging
from abcnet.settings import configure_logging
from abcnet.structures import Message, MsgType, PeerContactInfo, PeerContactQualifier, Ping, Pong, ItemEncodeable, \
    ItemQualifier
from abcnet.transcriber import Transcriber, Parser, split_msg_parts, join_msg_parts
from abcnet.simenv import configure_mocked_network_env

configure_mocked_network_env()
configure_test_logging()
logger = logging.getLogger(__name__)


def test_magic_nr():
    magic_nr_test = MAGIC_NUMBERS['test']
    t = Transcriber()
    t.magic_nr(magic_nr_test)
    msg = t.msg
    assert isinstance(msg, Message)
    assert len(msg.parts) == 1

    p0 = transcriber.Parser(msg.parts[0])
    assert p0.consume_int() == MAGIC_NUMBERS['test']


def test_nested_message():
    t = Transcriber()
    t.m_type(MsgType.ping)
    with t.nested_msg():
        for i in range(10):
            t.integer(i)

    msg = t.msg
    parser = transcriber.Parser(msg.parts[0])
    assert parser.consume_int() == MsgType.ping.value
    n_p = parser.parse_nested()
    for i in range(10):
        assert n_p.consume_int() == i
    assert n_p.c.read() == b''
    assert parser.c.read() == b''


def test_transcriber_contact_info():
    t = Transcriber()
    t.contact_info(PeerContactInfo("abc", None, "publishaddr", "receiveaddr"))
    msg = t.msg
    parser = transcriber.Parser(msg.parts[0])
    c = parser.parse_nested().consume_contact()
    assert c.identifier == "abc"
    assert c.publish_addr == "publishaddr"
    assert c.receive_addr == "receiveaddr"
    assert c.public_key == None


def test_transcriber_contact_qualifier():
    t = Transcriber()
    pcq = PeerContactQualifier("peer1")
    t.contact_qualifier(pcq)
    part0 = t.msg.parts[0]
    p = transcriber.Parser(part0)
    parsed_pcq = p.parse_nested().consume_contact_qualifier()
    assert pcq == parsed_pcq


def test_ping():
    t = Transcriber()
    ping = Ping(ping_id="ping1234")
    t.ping(ping)
    p = transcriber.Parser(t.msg.parts[0])
    ping_parsed = p.parse_nested().consume_ping()
    assert ping == ping_parsed


def test_pong():
    t = Transcriber()
    pong = Pong(Ping(ping_id="ping1234"), PeerContactInfo("peer1", None, None, None))
    t.pong(pong)
    p = transcriber.Parser(t.msg.parts[0])
    pong_parsed = p.parse_nested().consume_pong()
    assert pong == pong_parsed


def test_item_listing():
    t = Transcriber()

    class FakeItem(ItemQualifier, ItemEncodeable):

        def __init__(self, nr):
            self.id = f"FakeItem({nr})"
            self.nr = nr

        def item_type(self) -> int:
            return 0xeeee010

        def item_qualifier(self):
            return self.id

        def encode(self, transcriber: "Transcriber"):
            transcriber.write_text(self.id)
            transcriber.write_double(self.nr)

    items = [FakeItem(i) for i in range(100)]
    for fi in items:
        t.item_qualifier(fi)
    p = transcriber.Parser(t.msg.parts[0])

    for fi in items:
        item_type, item_qualifier = p.consume_item_qualifier()
        assert item_type == 0xeeee010
        assert item_qualifier == fi.item_qualifier()


def test_empty_string():
    t = Transcriber()
    t.write_text("")
    p0 = t.msg.parts[0]
    p = transcriber.Parser(p0)
    assert p.consume_nested_text() == ""



def test_split_msg_parts():
    t = Transcriber()
    counter = 1
    parts = 10
    for i in range(parts):
        t.integer(counter + 1)
        t.write_text("abc")
        with t.nested_msg():
            t.integer(counter + 2)
            t.integer(counter + 3)
        if i < parts - 1:
            t.next_msg()
        counter += 1
    joined_msg = join_msg_parts(t.msg.parts)
    assert isinstance(joined_msg, bytes)
    msg_parts = split_msg_parts(joined_msg)
    assert isinstance(msg_parts, List)

    assert len(msg_parts) == parts
    counter = 1
    for i in range(parts):
        p = Parser(msg_parts[i])
        assert p.consume_int() == counter + 1
        assert p.consume_nested_text() == "abc"
        np = p.parse_nested()
        assert np.consume_int() == counter + 2
        assert np.consume_int() == counter + 3
        counter += 1


def test_empty_content():
    t = Transcriber()
    t.nested_bytes(None)
    t.nested_bytes(b'')
    t.write_text(None)
    t.write_text("")
    parts = t.msg.parts

    p = Parser(parts[-1])
    assert b'' == p.consume_nested_bytes()
    assert b'' == p.consume_nested_bytes()
    assert '' == p.consume_nested_text()
    assert '' == p.consume_nested_text()

