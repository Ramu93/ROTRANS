from typing import List, Union

from abcnet import handlers
from abcnet import transcriber
from abcnet.services import ChannelService
from abcnet import timer
from abcnet.structures import Message, MsgType, Ping, Pong, PeerContactQualifier

from logging import getLogger

logger = getLogger(__name__)

class PingApp(handlers.MessageHandler):
    """
    Ping application that uses responds to pings with pongs.
    """

    def __init__(self, contact_qualifier: PeerContactQualifier, gen_time=0):
        self.contact_qualifier = contact_qualifier
        self.output_queue: List[Union[Ping, Pong]] = list()
        self.marked_items = set()
        self.gen_timer = None
        if gen_time != 0:
            self.gen_timer = timer.SimpleTimer(gen_time, start=True)

    def broadcast_new_ping(self):
        ping = Ping(self.contact_qualifier)
        self.output_queue.append(ping)

    def enqueue_output(self, item: Union[Ping, Pong]):
        if item:
            self.output_queue.append(item)

    def marked_seen(self, item: Union[Ping, Pong]):
        if item:
            self.marked_items.add(item)

    def accept(self, cs: ChannelService, msg: Message, **kwargs):
        if not msg.msg_type:
            cs.clog.warning("No message type was specified")
            return False
        if msg.msg_type == MsgType.ping:
            ping: Ping = transcriber.parse_ping(msg)
            if ping not in self.marked_items:
                cs.clog.info("%s message received in %s. Replying with pong message.", ping, ping.send_time)
                pong: Pong = Pong(ping, cs.contact)
                cs.broadcast_channel().pong(pong)
                # if msg.sender is not None and msg.sender.is_reachable:
                #     cs.direct_channel(msg.sender).pong(pong)
                # else:
                #     cs.broadcast_channel().pong(pong)
                # self.marked_seen(ping)
        if msg.msg_type == MsgType.pong:
            pong: Pong = transcriber.parse_pong(msg)
            if pong.ping.original_peer.identifier == cs.contact.identifier:
                cs.clog.info("%s. Sent since: %s. Replied since: %s. Replier: %s", pong, pong.ping.send_time,
                             pong.reply_time, pong.replier)
                if msg.sender is not None:
                    ps = cs.contacts.get_peer(msg.sender.identifier)
                    if ps is not None:
                        ps.log_ingoing_contact()
        return False

    def perform_maintenance(self, cs: ChannelService, force_maintenance=False):
        outch = cs.broadcast_channel()
        for i in range(len(self.output_queue)):
            item = self.output_queue[i]
            if isinstance(item, Ping):
                outch.ping(item)
            elif isinstance(item, Pong):
                outch.pong(item)
            else:
                del self.output_queue[:i]
                raise ValueError("Expected ping or pong, unrecognized item kind: " + str(item.__class__))

        if self.gen_timer and self.gen_timer():
            cs.broadcast_channel().ping(Ping(self.contact_qualifier))
            logger.info("Broadcasted a new ping to the network.")
        self.output_queue.clear()
