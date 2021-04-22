import logging
from typing import List, Iterable, Tuple, Callable, Any

from abcnet.structures import Message, MsgType
from abcnet.timer import StopTimer
from abcnet import transcriber


class MessageHandler:
    """
    A message handler represents application level logic.
    It handles messages and can optionally consume them.
    Every so often message handler instances perform maintenance and can send requests to peers.
    """

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        """
        Performs maintenance on the message handler.
        The given channel service can be used to send messages to peers.

        :param cs: Channel Service that can be used to contact peers
        :type cs:  ChannelService

        :param force_maintenance: If true, maintenance is forced. Handlers should ignore their timers
        and perform all queued tasks.

        :return: None
        :rtype: None
        """
        pass

    def accept(self, cs: "ChannelService", msg: Message) -> None:
        """
        Accepts next message.
        Returns true if the message handler consumes the message.
        If false is returned the message handler signals that the message requires further handling.
        This way the message is not relegated to any further message handler.
        Implementations should avoid sending messages while accepting messages,
         because it can introduce messaging loops.
        :param cs: Channel service that can be used for messages to peers.
        :type cs: ChannelService
        :param msg: To be accepted message
        :type msg: Message
        """

    def close(self):
        """
        Invoking this method signals that the app is closing.
        Any unfinished tasks should be executed and files closed.
        """
        pass


class MessageDelegator:
    """
    Delegates messages to registered message handlers.
    """

    logger = logging.getLogger(__name__ + ".MessageDelegator")

    def __init__(self, msg_handlers: Iterable[MessageHandler]):
        """
        Initializes a message delegator with a list of message handlers.
        :param msg_handlers: list of initial message handlers.
        :type msg_handlers: List[MessageHandler]
        """
        self.msg_handlers: List[MessageHandler] = list(msg_handlers)

    def register_mh(self, mh: MessageHandler):
        """
        Registers an implementation of message handler for incoming messages.
        :param mh: Message handler instance to be registered
        :type mh: MessageHandler
        :return: None
        :rtype: None
        """
        self.msg_handlers.append(mh)

    def _delegate_to_handlers(self, cs: "ChannelService", msg: Message):
        if not msg:
            MessageDelegator.logger.warning("Empty message %s", msg)
            return
        for mh in self.msg_handlers:
            try:
                msg_consumed = mh.accept(cs, msg)
                if msg_consumed:
                    MessageDelegator.logger.warning("Message handler, %s, returned True. This mechanic is deprecated.",
                                                    mh)
                if msg.is_discarded:
                    MessageDelegator.logger.debug("Message was discarded by %s", mh)
                    return
            except Exception as e:
                MessageDelegator.logger.error("Error handling msg by handler %s.", mh, exc_info=e)
        # MessageDelegator.logger.debug("No handler consumed message. Dropping message quietly.")

    def delegate_next_msg(self, timeout: float, cs: "ChannelService") -> bool:
        """
        Reads the next message of the channel service and delegates it to the message handlers.
        Returns false, if no message was received in the given timeout and no message handler was invoked.
        :param timeout: Max amount of time in seconds to wait until the next message arrives.
        :type timeout: float
        :param cs: channel to be read from
        :type cs: ChannelService
        :return: true, if a message was handled, false if timeout happened instead.
        :rtype: bool
        """
        msg = cs.poll_msg(timeout)
        if not msg:
            MessageDelegator.logger.debug("No message received in the specified timeout: %f sec.", timeout)
            return False
        timer = StopTimer()
        self._delegate_to_handlers(cs, msg)
        MessageDelegator.logger.debug("Message was handled in %s seconds.", timer)
        return True


class MagicNumberCheck(MessageHandler):
    """
    Message handler that drops messages with mismatching magic number.
    The magic number of a message are the first 4 bytes of the message.
    They have to match the specific magic number that is given by the channel service
    """

    logger = logging.getLogger(__name__ + ".MagicNumberCheck")

    def accept(self, cs: "ChannelService", msg: Message, **kwargs):
        mn = transcriber.parse_magic_number(msg)
        if mn != cs.magic_number:
            MagicNumberCheck.logger.warning("Dropped message because magic number didn't match. Expected: %s, got: %s",
                           hex(cs.magic_number), hex(mn))
            # return true, to signal that the message was consumed and is finished in order to drop the message.
            msg.discard()

    def __str__(self):
        return f'MagicNumberCheck'


class MessageTypeCheck(MessageHandler):
    """
    Message handler that extracts the message type from every message and re inserts it into the message object.
    """

    def __init__(self):
        super().__init__()

    def accept(self, cs: "ChannelService", msg: Message, **kwargs):
        m_type = transcriber.parse_message_type(msg)
        msg.msg_type = m_type


class ItemExtraction(MessageHandler):
    """
    Message handler that extracts the content and item types and stores it in the message.
    """
    def __init__(self):
        super().__init__()

    def accept(self, cs: "ChannelService", msg: Message):
        if msg.msg_type == MsgType.items_content:
            self._decode_item_contents(msg)
        elif MsgType.is_items(msg.msg_type):
            self._decode_item_listings(msg)

    @staticmethod
    def _decode_item_contents(msg: Message):
        items: List[Tuple[int, bytes]] = transcriber.parse_item_contents(msg)
        msg.items = items

    @staticmethod
    def _decode_item_listings(msg: Message):
        items: List[Tuple[int, str]] = transcriber.parse_item_qualifier(msg)
        msg.items = items


class AbstractItemHandler(MessageHandler):
    """
    An abstract super class of all message handlers that are about handling item messages.

    This class filters the items and calls the overridden methods from its implementation.
    Implementations override: handle_item_content, handle_item_request, handle_item_checklist, handle_item_notfound

    For a faster runtime implementations can also overwrite the batch version instead.

    """

    def __init__(self, interesting_item_types: List[int], item_parser: transcriber.ItemsParser):
        """
        Initializes the item handler with the given list of interested item types and the given item parser.

        :param interesting_item_types: list of item types that are only considered when handling messages.
        :type interesting_item_types: List[int]
        :param item_parser: Item parser that is used to decode the item contents.
        :type item_parser: transcriber.ItemParser
        """
        super().__init__()
        self.interesting_item_types: List[int] = interesting_item_types
        self.item_parser = item_parser

    def accept(self, cs: "ChannelService", msg: Message):
        if MsgType.is_items(msg.msg_type) and msg.items is None:
            raise ValueError("Items are expected to be extracted by ItemExtraction message handler. "
                             "Add it to the application stack before item message handlers. ")
        elif MsgType.is_items(msg.msg_type):
            self._handle_item_msg(cs, msg)

    def _msg_has_interesting_item(self, msg) -> bool:
        for interested_item in self.interesting_item_types:
            if msg.has_item_of_type(interested_item):
                return True
        return False

    def _filter_interesting_items(self, items: List[Tuple[int, Any]]) -> Iterable[Tuple[int, Any]]:
        return filter(lambda i: i[0] in self.interesting_item_types, items)

    def _msg_type_handler(self, msg_type) -> Callable[["ChannelService", Message, Iterable], None]:
        if msg_type == MsgType.items_content:
            handler = self.handle_item_batch_raw_contents
        elif msg_type == MsgType.items_request:
            handler = self.handle_item_batch_request
        elif msg_type == MsgType.items_checklist:
            handler = self.handle_item_batch_checklist
        elif msg_type == MsgType.items_notfound:
            handler = self.handle_item_batch_notfound
        else:
            raise ValueError("Unexpected message type: " + str(msg_type))
        return handler

    def _handle_item_msg(self, cs, msg: Message):
        if not self._msg_has_interesting_item(msg):
            return
        interesting_items = self._filter_interesting_items(msg.items)
        handler = self._msg_type_handler(msg.msg_type)
        handler(cs, msg, interesting_items)

    def handle_item_batch_raw_contents(self, cs: "ChannelService",
                                       msg: Message,
                                       item_batch: Iterable[Tuple[int, bytes]]):
        # Transforms the item to their decoded version by using the item_parser
        decoded_items = self.item_parser.decode_item_list_raw(item_batch)
        self.handle_item_batch_contents(cs, msg, decoded_items)

    def handle_item_batch_contents(self, cs: "ChannelService",
                                        msg: Message,
                                        item_batch: Iterable[Tuple[int, Any]]):
        for item_type, item_content in item_batch:
            self.handle_item_content(cs, msg, item_type, item_content)

    def handle_item_batch_request(self, cs: "ChannelService",
                                        msg: Message,
                                        item_batch: Iterable[Tuple[int, str]]):
        for item_type, item_qualifier in item_batch:
            self.handle_item_request(cs, msg, item_type, item_qualifier)

    def handle_item_batch_checklist(self, cs: "ChannelService",
                                        msg: Message,
                                        item_batch: Iterable[Tuple[int, str]]):
        for item_type, item_qualifier in item_batch:
            self.handle_item_checklist(cs, msg, item_type, item_qualifier)

    def handle_item_batch_notfound(self, cs: "ChannelService",
                                        msg: Message,
                                        item_batch: Iterable[Tuple[int, str]]):
        for item_type, item_qualifier in item_batch:
            self.handle_item_notfound(cs, msg, item_type, item_qualifier)

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any):
        pass

    def handle_item_request(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        pass

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        pass

    def handle_item_notfound(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        pass
