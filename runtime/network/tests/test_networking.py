from abcnet.outch import SingleSocketSender, MultiSendSocketsSender, DropMessageSender
from abcnet.settings import NetworkBackend
from unittest.mock import MagicMock, patch

from abcnet.networking import SocketHandler, SimpleMD1, ContactBook
from abcnet.structures import SocketBinding
from abcnet.nettesthelpers import pseudo_peer


@patch('abcnet.settings.NetworkBackend')
def test_socket_handler(net_back_end_mock: NetworkBackend):
    import zmq
    socket_instances = {
        zmq.PUB: MagicMock(),
        zmq.SUB: MagicMock(),
        zmq.DEALER: MagicMock()
    }
    def socket_function(socket_type):
        return socket_instances[socket_type]

    mocked_context = MagicMock()
    mocked_context.socket.side_effect = socket_function
    mocked_socket_func: MagicMock = mocked_context.socket

    net_back_end_mock.context = MagicMock(return_value=mocked_context)

    expected_poller = MagicMock()
    net_back_end_mock.msg_poller = MagicMock(return_value=expected_poller)

    sb = SocketBinding('pub_address', 'rec_address')
    sh = SocketHandler(sb)

    assert not sh.closed
    net_back_end_mock.context.assert_called_once_with()
    mocked_socket_func.assert_any_call(zmq.PUB)
    socket_instances[zmq.PUB].bind.assert_called_once_with('pub_address')
    mocked_socket_func.assert_any_call(zmq.SUB)
    socket_instances[zmq.SUB].subscribe.assert_called_once_with(b'')
    mocked_socket_func.assert_any_call(zmq.DEALER)
    socket_instances[zmq.DEALER].bind.assert_called_once_with('rec_address')
    net_back_end_mock.msg_poller.assert_not_called()

    assert socket_instances[zmq.DEALER] in sh.receive_sockets()
    assert socket_instances[zmq.SUB] in sh.receive_sockets()

    actual_poller = sh.msg_poller()
    assert expected_poller is actual_poller
    net_back_end_mock.msg_poller.assert_called()

    assert sh.subscribe('sub_address') is None
    socket_instances[zmq.SUB].connect.assert_called_with('sub_address')

    assert sh.publish_socket() is socket_instances[zmq.PUB]

    mocked_socket_func.reset_mock()
    expected_direct_socket = MagicMock()
    socket_instances[zmq.DEALER] = expected_direct_socket

    actual_direct_socket = sh.direct_sending_socket("direct_address")
    assert mocked_socket_func.call_count == 1
    mocked_socket_func.assert_called_once_with(zmq.DEALER)
    assert actual_direct_socket == socket_instances[zmq.DEALER]
    expected_direct_socket.connect.assert_called_once_with("direct_address")

    mocked_socket_func.reset_mock()
    expected_direct_socket.connect.reset_mock()

    actual_direct_socket = sh.direct_sending_socket("direct_address")
    mocked_socket_func.assert_not_called()
    socket_instances[zmq.DEALER].connect.assert_not_called()
    assert socket_instances[zmq.DEALER] == actual_direct_socket

    sh.close_direct_sending_socket("direct_address_1")
    expected_direct_socket.close.assert_not_called()

    sh.close_direct_sending_socket("direct_address")
    expected_direct_socket.close.assert_called_once()


def test_simple_md1():
    cb = ContactBook()
    p1 = pseudo_peer("P1")
    p2 = pseudo_peer("P2")
    cb.get_or_create_peer(p1)
    cb.get_or_create_peer(p2)

    sh_mock = MagicMock()

    smd = SimpleMD1(cb, sh_mock)

    # If there is a publish socket, then create a single sender with the publish socket:
    publish_socket_mock = MagicMock()
    sh_mock.publish_socket = MagicMock(return_value=publish_socket_mock)
    sender = smd.broadcast()

    assert sender is not None
    assert isinstance(sender, SingleSocketSender)
    assert sender.socket is publish_socket_mock
    sh_mock.publish_socket.assert_called()
    publish_socket_mock.assert_not_called()

    # If there is no publish socket, it should create a multi sender with all neighbors:
    sh_mock.publish_socket = MagicMock(return_value=None)

    direct_socket_1 = MagicMock()
    direct_socket_2 = MagicMock()

    def create_direct_socket(addr):
        if addr == p1.receive_addr:
            return direct_socket_1
        if addr == p2.receive_addr:
            return direct_socket_2
        raise AssertionError("Unexpected address: " + addr)

    sh_mock.direct_sending_socket = MagicMock(side_effect=create_direct_socket)
    sender = smd.broadcast()
    assert sender is not None
    assert isinstance(sender, MultiSendSocketsSender)
    assert len(sender.inner_senders) == 2
    assert isinstance(sender.inner_senders[0], SingleSocketSender)
    actual_direct_socket_1: MagicMock = sender.inner_senders[0].socket
    actual_direct_socket_2: MagicMock = sender.inner_senders[1].socket
    assert actual_direct_socket_2 == direct_socket_2
    assert actual_direct_socket_1 == direct_socket_1
    direct_socket_1.assert_not_called()
    direct_socket_2.assert_not_called()

    # If there is no publish or neighbors drop message is returned:
    sh_mock.publish_socket = MagicMock(return_value=None)
    cb.clear()
    sender = smd.broadcast()
    assert sender is not None
    assert isinstance(sender, DropMessageSender)

