from typing import List, Union
from unittest.mock import MagicMock, create_autospec

import zmq

from abcnet import transcriber
from abcnet.handlers import MessageDelegator, MessageHandler
from abcnet.services import ChannelService, BaseApp
from abcnet.settings import configure_test_logging
from abcnet.structures import Ping
from abcnet.nettesthelpers import pseudo_peer, MockMsgSender, MockMsgReceiver, RecordMsgReceiver, set_test_magic_nr


configure_test_logging()

def test_inter_context_msg_passing():
    context1 = zmq.Context()
    context2 = zmq.Context()

    pub_socket = context1.socket(zmq.PUB)
    sub_socket = context2.socket(zmq.SUB)
    sub_socket.subscribe(b'')
    contact = pseudo_peer()
    pub_socket.bind(contact.publish_addr)
    sub_socket.connect(contact.publish_addr)
    pub_socket.send_multipart([b'05', b'16', b'28'], copy=False)
    # Doesn't work
    # msg = sub_socket.recv_multipart()
    #
    # assert msg == [b'05', b'16', b'28']



def test_zmq_sockets_tcp():
    zmq_sockets_test("tcp://127.0.0.1:60005", "tcp://127.0.0.1:60006")

def test_zmq_sockets_inproc():
    pseudo_contact = pseudo_peer()
    zmq_sockets_test(pseudo_contact.publish_addr, pseudo_contact.receive_addr)

def zmq_sockets_test(publish_addr, receive_addr):
    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    sub_socket = context.socket(zmq.SUB)
    sub_socket.subscribe(b'')

    import time
    pub_socket.bind(publish_addr)
    sub_socket.connect(publish_addr)
    time.sleep(0.05)

    pub_socket.send_multipart([b'00', b'11', b'22'])
    msg = sub_socket.recv_multipart()

    assert msg == [b'00', b'11', b'22']

    dealer_socket = context.socket(zmq.DEALER)
    pull_socket = context.socket(zmq.DEALER)
    dealer_socket.connect(receive_addr)
    pull_socket.bind(receive_addr)
    time.sleep(0.05)

    dealer_socket.send_multipart([b'00', b'11', b'22'])
    msg = pull_socket.recv_multipart()
    assert msg == [b'00', b'11', b'22']


def test_mock_broadcast():
    # set_test_magic_nr()
    sender = MockMsgSender()
    import abcnet.nettesthelpers as helpers
    receiver = MockMsgReceiver(sub_magic_nr=True)
    receiver.subscribe(sender.contact)
    sender.broadcast_channel().ping(Ping())

    # parts = receiver.sub_socket.recv_multipart()
    # assert parts is not None
    msg = receiver.next_msg(1)
    assert msg is not None
    assert transcriber.parse_ping(msg) is not None


def test_mock_direct():
    sender = MockMsgSender()
    receiver = MockMsgReceiver()
    sender.direct_message(receiver.contact).ping(Ping())
    msg = receiver.next_msg()
    assert msg is not None
    assert transcriber.parse_ping(msg) is not None


def test_record_receiver():
    sender = MockMsgSender()
    receiver = RecordMsgReceiver()

    assert receiver.next_msg() is None

    ping_count = 4
    pings: List[Ping] = [Ping() for i in range(ping_count)]
    for p in pings:
        sender.direct_message(receiver.contact).ping(p)

    for i in range(ping_count):
        msg_ping = receiver.next_msg()
        assert transcriber.parse_ping(msg_ping) == pings[i]

    receiver.replay()

    for i in range(ping_count):
        msg_ping = receiver.next_msg()
        assert transcriber.parse_ping(msg_ping) == pings[i]

    receiver.replay()
    msg_ping = receiver.next_msg()
    assert transcriber.parse_ping(msg_ping) == pings[0]

    receiver.clear_record()
    assert receiver.next_msg() is None

    def ping_matcher(ping):
        def specific_matcher(msg):
            try:
                return transcriber.parse_ping(msg) == ping
            except Exception:
                return False
        return specific_matcher

    for p in pings:
        sender.direct_message(receiver.contact).ping(p)

    for p in pings:
        assert receiver.matching_msg(ping_matcher(p)) is not None

    assert receiver.matching_msg(ping_matcher(Ping())) is None

    receiver.replay()
    assert receiver.next_matching_msg(ping_matcher(pings[-1])) is not None


def test_msg_delegator():
    mh_mock1: Union[MessageHandler, MagicMock] = create_autospec(MessageHandler)
    mh_mock2: Union[MessageHandler, MagicMock] = create_autospec(MessageHandler)
    mh_mock1.accept: MagicMock
    mh_mock2.accept: MagicMock
    mh_mock1.accept.return_value = False
    mh_mock2.accept.return_value = False

    md = MessageDelegator([mh_mock1, mh_mock2])

    cs: Union[ChannelService, MagicMock] = MagicMock()
    msg1 = MagicMock()
    msg1.is_discarded = False
    msg2 = MagicMock()
    msg2.is_discarded = True
    cs.poll_msg.side_effect = [msg1, msg2, None]

    md.delegate_next_msg(13.5, cs)
    mh_mock1.accept.assert_called_once_with(cs, msg1)
    mh_mock2.accept.assert_called_once_with(cs, msg1)
    mh_mock1.accept.reset_mock()
    mh_mock2.accept.reset_mock()

    md.delegate_next_msg(13.5, cs)
    mh_mock1.accept.assert_called_once_with(cs, msg2)
    mh_mock2.accept.assert_not_called()
    mh_mock1.accept.reset_mock()
    mh_mock2.accept.reset_mock()

    md.delegate_next_msg(13.5, cs)
    mh_mock1.accept.assert_not_called()
    mh_mock2.accept.assert_not_called()

def test_base_app_perform_maintenance():
    ba = BaseApp(MagicMock())

    maintenance_mock_old = MagicMock()
    class OldMsgHanlder(MessageHandler):
        def perform_maintenance(self, cs: "ChannelService"):
            maintenance_mock_old.perform_maintenance(cs)
    old_msg_handler = OldMsgHanlder()


    maintenance_mock_err = MagicMock()
    class ErrorThrower(MessageHandler):
        def perform_maintenance(self, cs: "ChannelService", force_maintenance):
            maintenance_mock_err.perform_maintenance(cs, force_maintenance)
            raise TypeError("Some error with typing")
    err_msg_handler = ErrorThrower()

    msg_handler1 = create_autospec(MessageHandler)
    ba.register_app_layer("old", old_msg_handler)

    ba.register_app_layer("err", err_msg_handler)
    ba.register_app_layer("msgh1", msg_handler1)

    ba.maintain(force_maintenance=True)
    msg_handler1.perform_maintenance: MagicMock
    msg_handler1.perform_maintenance.assert_called_once_with(ba.cs, True)
    maintenance_mock_old.perform_maintenance.assert_called_once_with(ba.cs)
    maintenance_mock_err.perform_maintenance.assert_called_once_with(ba.cs, True)