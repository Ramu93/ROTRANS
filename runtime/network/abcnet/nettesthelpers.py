import time
from typing import Union, Iterable, Optional, Callable, List, Any
from uuid import uuid4

import zmq
from abcnet import handlers, transcriber, auth, networking
from abcnet import outch
from abcnet import settings
from abcnet.outch import MessageAuthenticator
from abcnet.services import BaseApp, ChannelService
from abcnet.simenv import Simulation
from abcnet.structures import PeerContactInfo, Message, NetPrivKey
from abcnet.networking import ContactBook
from abcnet import netstats

context = settings.NetworkBackend.context

magic_nr = settings.MAGIC_NUMBERS["test"]

def set_test_magic_nr():
    settings.RuntimeSetting.MAGIC_NUMBER = magic_nr


def rand_bind():
    return 'inproc://' + str(uuid4())


def pseudo_peer(name=None) -> PeerContactInfo:
    if name is None:
        name = str(uuid4())
    return PeerContactInfo(name, None, rand_bind(), rand_bind())

def pseude_cs(name=None) -> ChannelService:
    pp = pseudo_peer(name)
    cb = ContactBook(pp, [])
    return ChannelService.initialize_service(cb, None)

def msg_authenticator(contact_info: PeerContactInfo) -> MessageAuthenticator:
    priv_key = NetPrivKey.from_seed()
    contact_info.public_key = priv_key.public_key_bytes
    ma = auth.MessageAuthenticatorImpl(contact_info, priv_key)
    return ma


def net_app(contact_info: PeerContactInfo, initial_contacts=None, ma=None) -> BaseApp:
    if ma is None:
        ma = msg_authenticator(contact_info)
    cb = ContactBook(contact_info, initial_contacts)
    cs = ChannelService.initialize_service(cb, None, ma=ma)
    ba = BaseApp(cs)
    ba.register_app_layer("magicnr", handlers.MagicNumberCheck())
    ba.register_app_layer("authcheck", auth.AuthenticationHandler(cb))
    ba.register_app_layer("messagetype", handlers.MessageTypeCheck())
    ba.register_app_layer("network", cs.net_maintainer)
    ba.register_app_layer("conntection_watcher", networking.PeerConnectionWatchdog(cb))
    ba.register_app_layer("itemextractor", handlers.ItemExtraction())

    netstats.enable_statistics(ba)
    return ba


def ping_app(contact_info, initial_contacts=None) -> BaseApp:
    from abcnet import pingpong
    ba = net_app(contact_info, initial_contacts)
    ba.register_app_layer("ping", pingpong.PingApp(contact_info, 10))
    return ba


class MockMsgSender:

    def __init__(self, contact: PeerContactInfo = None):
        if not contact:
            contact = pseudo_peer()
        self.contact = contact
        self.pub_socket = context().socket(zmq.PUB)
        self.pub_socket.bind(contact.publish_addr)
        self.direct_socket = None

    def broadcast_channel(self) -> outch.OutputChannel:
        return outch.OutputChannel(sender=outch.SingleSocketSender(self.pub_socket), authenticator=None)

    def direct_message(self, peer: PeerContactInfo) -> outch.OutputChannel:
        if self.direct_socket:
            self.direct_socket.close()
            del self.direct_socket
        self.direct_socket = context().socket(zmq.DEALER)
        self.direct_socket.connect(peer.receive_addr)
        return outch.OutputChannel(sender=outch.SingleSocketSender(self.direct_socket), authenticator=None)


class MockMsgReceiver:

    def __init__(self, contact: PeerContactInfo = None, sub_magic_nr=None, magic_nr_bytes=b'', ):
        if not contact:
            contact = pseudo_peer()
        self.contact = contact
        self.receive_socket = context().socket(zmq.DEALER)
        self.receive_socket.bind(contact.receive_addr)
        self.sub_socket = context().socket(zmq.SUB)
        self.sub_socket.subscribe(b'')

    def subscribe(self, peer: Union[Iterable[PeerContactInfo], PeerContactInfo]):
        if isinstance(peer, PeerContactInfo):
            peer = [peer]
        if isinstance(peer, Iterable):
            for p in peer:
                self.sub_socket.connect(p.publish_addr)
            time.sleep(0.05)
            return
        raise ValueError("Peer mistyped.")

    def next_msg(self, timeout: float = 0.01) -> Optional[Message]:
        poller = settings.NetworkBackend.msg_poller([self.receive_socket, self.sub_socket])
        msg: Message = poller(timeout)
        return msg


MsgMatcherType = Callable[[Message], Union[bool, Any]]

class RecordMsgReceiver(MockMsgReceiver):

    def __init__(self, contact: PeerContactInfo = None):
        super(RecordMsgReceiver, self).__init__(contact)
        self.msg_record = list()
        self.record_index = 0

    def _pop(self) -> Optional[Message]:
        if self.record_index >= len(self.msg_record):
            return None
        else:
            msg = self.msg_record[self.record_index]
            self.record_index += 1
            return msg

    def _record(self, msg: Message):
        if msg:
            self.msg_record.append(msg)

    def clear_record(self):
        self.msg_record.clear()
        self.record_index = 0

    def replay(self):
        self.record_index = 0

    def next_msg(self, timeout: float = 0.01) -> Optional[Message]:
        next_msg: Message = self._pop()
        if not next_msg:
            msg = super(RecordMsgReceiver, self).next_msg(timeout)
            self._record(msg)
            return self._pop()
        else:
            return next_msg

    def matching_msg(self, matcher: MsgMatcherType) -> Optional[Any]:
        self.replay()
        return self.next_matching_msg(matcher)

    def next_matching_msg(self, matcher: MsgMatcherType) -> Optional[Any]:
        while True:
            msg = self.next_msg()
            if not msg:
                break
            match_result = matcher(msg)
            if match_result is not None and match_result is not False:
                if match_result is True:
                    return msg
                else:
                    return match_result
        return None


def long_test(test_f):
    def check_env_for_long_test_flag():
        import os
        if 'LONG_TESTS' in os.environ:
            test_f()
    return check_env_for_long_test_flag


def clique_is_formed(apps: List[BaseApp]):
    for i in range(len(apps)):
        app = apps[i]
        neighbors = app.cs.net_maintainer.neighbors
        for j in range(len(apps)):
            if i == j:
                continue
            other_peer = apps[j]
            if other_peer.cs.contact not in neighbors:
                return False
    return True


def simulate_till_clique_is_formed(apps: List[BaseApp], round_limit=-1):
    sim = Simulation(apps)
    is_clique_found = clique_is_formed(apps)
    while not is_clique_found and round_limit > 0:
        sim.next_round()
        round_limit -= 1
        is_clique_found = clique_is_formed(apps)
    return is_clique_found, round_limit

def data_tester(test_data: List):
    def data_test_dec(test_function):
        def new_test_function(self):
            for case in test_data:
                test_function(self, **case)
        return new_test_function
    return data_test_dec

def send_and_receive_msg(msg: Message) -> Message:
    msg_bytes = transcriber.msg_network_bytes(msg)
    return transcriber.msg_from_network_bytes(msg_bytes)