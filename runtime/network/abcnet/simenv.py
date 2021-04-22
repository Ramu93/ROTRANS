from typing import Dict, List, Optional, Iterable, Callable
import logging
import zmq
import time

from abcnet.services import BaseApp
from abcnet import transcriber
from abcnet.timer import SimpleTimer, StopTimer

logger = logging.getLogger(__name__)


class MockedNetworkContext:
    """
    Mocks the network layer and replaces zeroMQ context.
    """

    listeners: Dict[str, "MockedSocket"]

    subscriptions: Dict[str, List["MockedSocket"]]

    def __init__(self):
        self.listeners = dict()
        self.subscriptions = dict()

    def socket(self, socket_type):
        new_socket: MockedSocket
        if socket_type == zmq.PUB:
            new_socket = PublishSocket(self)
        elif socket_type == zmq.SUB:
            new_socket = SubscribeSocket(self)
        elif socket_type == zmq.DEALER:
            new_socket = DealerSocket(self)
        else:
            raise ValueError("Unrecognized socket type: " + str(socket_type))
        return new_socket

    def listen(self, address: str, listener: "MockedSocket"):
        self.listeners[address] = listener

    def subscribe(self, address: str, subscriber: "MockedSocket"):
        if address not in self.subscriptions:
            self.subscriptions[address] = []
        self.subscriptions[address].append(subscriber)

    def unlisten(self, address: str, listener: "MockedSocket"):
        if address in self.listeners and self.listeners[address] is listener:
            del self.listeners[address]

    def unsub(self, address: str, subscriber: "MockedSocket"):
        if address not in self.subscriptions:
            return
        self.subscriptions[address].remove(subscriber)

    def broadcast_from(self, source: str, msg_bytes: bytes):
        if source in self.subscriptions:
            for target in self.subscriptions[source]:
                target.enqueue(msg_bytes)

    def send_to(self, target:str, msg_bytes: bytes):
        if target in self.listeners:
            self.listeners[target].enqueue(msg_bytes)


class MockedSocket:
    """
    Base class of mocked sockets.
    """
    context: "MockedNetworkContext"

    msg_queue: List[bytes]

    def __init__(self, context: "MockedNetworkContext"):
        self.context = context
        self.msg_queue = list()

    def bind(self, address: str):
        raise RuntimeError("This socket is not capable of binding.")

    def connect(self, address):
        raise RuntimeError("This socket is not capable of connecting.")

    def send(self, msg_bytes: bytes):
        raise RuntimeError("This socket is not capable of sending bytes messages.")

    def send_multipart(self, parts: List[bytes]):
        raise RuntimeError("This socket is not capable of sending multipart messages.")

    def enqueue(self, parts: bytes):
        self.msg_queue.append(parts)

    def dequeue(self) -> Optional[bytes]:
        if self.msg_queue:
            return self.msg_queue.pop(0)
        return None

    def close(self):
        self.msg_queue.clear()


class SubscribeSocket(MockedSocket):
    """
    Mocks the zmq.SUB socket.
    Can receive from pub sockets.
    """

    def __init__(self, context):
        MockedSocket.__init__(self, context)
        self.connections = list()

    def connect(self, address):
        self.connections.append(address)
        self.context.subscribe(address, self)

    def disconnect(self, address):
        self.connections.remove(address)
        self.context.unsub(address, self)

    def close(self):
        super(SubscribeSocket, self).close()
        for connection in self.connections:
            self.context.unsub(connection, self)

    def subscribe(self, keyword: bytes):
        pass


class PublishSocket(MockedSocket):
    """
    Mocks the zmq.PUB socket.
    Can send to sub sockets.
    """

    def __init__(self, context):
        MockedSocket.__init__(self, context)
        self.bound = None

    def bind(self, address: str):
        if self.bound:
            raise ValueError("Already bound.")
        self.bound = address

    def send(self, msg_bytes: bytes):
        if not self.bound:
            raise ValueError("Socket wasn't bound yet.")
        self.context.broadcast_from(self.bound, msg_bytes)


class DealerSocket(MockedSocket):
    """
    Mocks the zmq.DEALER socket.
    Can send and receive to other dealer socket.
    """

    def __init__(self, context):
        MockedSocket.__init__(self, context)
        self.connection = None
        self.bound = None

    def bind(self, address: str):
        if self.bound:
            raise ValueError("Already bound.")
        self.bound = address
        self.context.listen(address, self)

    def close(self):
        super(DealerSocket, self).close()
        if self.bound:
            self.context.unlisten(self.bound, self)

    def connect(self, address):
        if self.connection:
            raise ValueError("Already connected.")
        self.connection = address

    def send(self, msg_bytes: bytes):
        if not self.connection:
            raise ValueError("Socket wasn't connected yet.")
        self.context.send_to(self.connection, msg_bytes)

    def send_multipart(self, parts: List[bytes]):
        raise ValueError("Multipart sending is not ")


def configure_mocked_network_env():
    """
    Configures the network backend to use a mocked version, that is able to have many more sockets than zmq allows.
    """
    from abcnet import settings
    settings.NetworkBackend.CONTEXT_INITIALIZER = MockedNetworkContext

    def mocked_msg_poller(sockets, direct_socket_predicate: Callable):
        """
        Returns a poller that polls from mocked sockets.
        """
        def poll_multipart(timeout=0, _sockets=sockets):
            for socket in _sockets:
                socket: MockedSocket
                msg_bytes = socket.dequeue()
                if msg_bytes:
                    msg = transcriber.msg_from_network_bytes(msg_bytes)
                    if direct_socket_predicate(socket):
                        msg.is_direct = True
                    return msg
            return None
        return poll_multipart

    settings.NetworkBackend.MSG_POLLER_BUILDER = mocked_msg_poller


class Simulation:
    """
    This class allows simulation by registering apps with the ``+=`` operator.
    And then next_round can be used to simulate n many rounds.

    Simulation participants are excluusive to a single simulation instance.
    That means, different simulation instances must have a distinct set of participants.
    """

    def __init__(self,
                 init_participants: Iterable = tuple(),
                 msg_timeout=0.0):
        """
        Initializes the simulation with the given app instances and msg_timeout.

        :param init_participants: Initial simulation participants.
        :type init_participants: Iterable[BaseApp]
        :param msg_timeout: The time for each participant to wait until a message timeout has been reached.
        :type msg_timeout: float
        """
        self._participants: Dict[str, BaseApp] = dict()
        self.msg_timeout = msg_timeout
        self.timer = SimpleTimer(3)
        self._round_count: int = 0
        for p in init_participants:
            self.__iadd__(p)

    @property
    def round_count(self) -> int:
        """
        Returns the round count in this simulation.

        :return:  Number of rounds simulated in this simulation instance.
        :rtype: int
        """
        return self._round_count

    @property
    def participants(self) -> List[BaseApp]:
        return list(self._participants.values())

    def next_round(self, rounds=1):
        """
        Simulates n many rounds.
        In each round, each participants are stepped.
        Within each step, a participant reads all incoming messages, and is performs maintenance.

        :param rounds: amount of rounds to simulate. Defaults to a single round.
        :type rounds: int
        :return: None
        :rtype: None
        """
        for i in range(rounds):
            for instance in self._participants.values():
                instance.step(self.msg_timeout)
            self._round_count += 1
            if self.timer():
                logger.info("Round %i ended.", self._round_count)

    def __iadd__(self, other: BaseApp):
        if isinstance(other, BaseApp):
            self._participants[other.cs.contact.identifier] = other
        return self

    def close(self):
        logger.info("Shutting down simulation...")
        for p in self._participants.values():
            p.close()
        logger.info("Simulation finished shutdown.")
