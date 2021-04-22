import logging
from typing import Optional, List, Callable

import zmq

from abcnet.timer import SimpleTimer

logger = logging.getLogger(__name__)

class TimedPoll:

    def __init__(self, inner_poller: "ZMQMsgPoller"):
        self.inner_poller: "ZMQMsgPoller" = inner_poller

    def __call__(self, timeout: Optional[float]):
        timer = None
        if timeout is not None and timeout> 0:
            timer = SimpleTimer(timeout, start=True)

        while timeout is None or timeout == 0 or timer.remaining_time > 0:
            remaining_time = timeout
            if timer is not None:
                remaining_time = timer.remaining_time
            try:
                msg = self.inner_poller(remaining_time)
                return msg
            except Exception as e:
                logger.error("Error reading a network msg.", exc_info=e)
            if timeout == 0:
                return None# No message found in the given time.


class ZMQMsgPoller:

    sockets: List[zmq.Socket]

    poller: zmq.Poller

    input_socket_predicate: Callable

    def __init__(self, sockets: List[zmq.Socket],
                 input_socket_predicate: Callable[[zmq.Socket], bool]= lambda _: False):
        self.sockets = sockets
        self.poller = zmq.Poller()
        for s in sockets:
            self.poller.register(s, zmq.POLLIN)
        self.input_socket_predicate = input_socket_predicate
        from abcnet.transcriber import msg_from_network_bytes
        self.msg_composer = msg_from_network_bytes

    def __call__(self, timeout: Optional[float]) -> Optional["abcnet.structures.Message"]:
        if timeout == 0:
            timeout = 0
        elif not timeout:
            timeout = -1
        else:
            timeout *= 1000

        events = dict(self.poller.poll(timeout))
        for socket in self.sockets:
            if socket in events:
                msg_bytes = socket.recv(flags=zmq.NOBLOCK)
                msg = self.msg_composer(msg_bytes)
                if self.input_socket_predicate(socket):
                    msg.is_direct = True
                return msg
        return None


def build_zmq_poller(sockets, direct_socket_check: Callable[["zmq.Socket"], bool] = lambda s: False):
    return TimedPoll(ZMQMsgPoller(sockets, direct_socket_check))

def _new_zmq_context():
    import zmq
    context = zmq.Context()
    context.setsockopt(zmq.MAX_SOCKETS, 10000000)
    return zmq.Context()
