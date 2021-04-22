import logging

from abcnet.handlers import MessageHandler
from abcnet.networking import ContactBook
from abcnet.services import ChannelService
from abcnet.structures import Message

logger = logging.getLogger(__name__)

class GatewayRebroadcast(MessageHandler):

    def __init__(self, cb: ContactBook):
        self.__cb = cb

    def accept(self, cs: ChannelService, msg: Message) -> None:
        if msg.sender is not None:
            logger.info("Rebroadcast message from:\n%s", msg.sender)
        else:
            logger.info("Rebroadcast anonymous message.")

        cs.broadcast_channel().sender._send(msg)

