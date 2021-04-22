from typing import List, Tuple, Callable

import zmq
import logging

from abcnet.structures import Message, ItemEncodeable, PeerContactInfo, MsgType, PeerContactQualifier, Ping, Pong
from abcnet.transcriber import Transcriber, msg_network_bytes
from abcnet.structures import ItemQualifier

from abcnet.settings import RuntimeSetting

logger = logging.getLogger(__name__)


class MessageAuthenticator:
    """
    Appends a part to the given message that authenticates the peer.
    """

    def authenticate(self, msg: Message):
        """
        Authenticates the message in-place.
        :param msg: Message to be authenticated
        :type msg: Message
        :return: None
        :rtype: None
        """
        raise NotImplementedError("No authentication was selected.")


class MsgSender:
    """
    MsgSender is a the Interface of all classes that are capable of sending messages.
    """

    def _send(self, msg: Message, do_log=True):
        """
        Sends the message.
        """


def _create_tc_then_send(msg_type: MsgType):
    """
    This decorator removes duplicate code by having the transcriber object created and supplied to the function.
    And then afterwards it also sends the filled message.
    """
    def new_decorator(function: Callable):
        def new_function(self, *args, **kwargs):
            tc: Transcriber = self._transcriber(msg_type)
            kwargs.update({'tc': tc})
            function(self, *args, **kwargs)
            self._send(tc.msg)
        return new_function
    return new_decorator


class OutputChannel:
    """
    Represents the channel to one or more peers.
    Can be used to send messages asynchronously.
    """

    def __init__(self, authenticator: MessageAuthenticator = None, sender: MsgSender = None):
        """
        Initializes the output channel.
        :param authenticator: Message authenticator that is used to authenticate the message.
        :type authenticator: MessageAuthenticator
        """
        if not authenticator:
            from abcnet.auth import NoMessageAuthenticator
            authenticator = NoMessageAuthenticator()
        self.authenticator = authenticator
        if sender is None:
            sender = DropMessageSender()
        self.sender: MsgSender = sender

    @staticmethod
    def _transcriber(msg_type: MsgType) -> Transcriber:
        tc = Transcriber()
        tc.magic_nr(RuntimeSetting.MAGIC_NUMBER)
        tc.next_msg()
        if not msg_type:
            raise ValueError("No message type was provided.")
        tc.m_type(msg_type)
        return tc

    def _auth(self, msg: Message):
        if not msg.parts:
            logger.error("Sending empty message")
        self.authenticator.authenticate(msg)

    def _send(self, msg: Message):
        self.authenticator.authenticate(msg)
        self.sender._send(msg)

    def _item_list(self, tc: Transcriber, listings: List[ItemQualifier]):
        tc.content_length(len(listings))
        for item in listings:
            tc.integer(item.item_type(), "Item Type")
            tc.write_text(item.item_qualifier(), "Item Qualifier")

    def _item_list_tuple(self, tc: Transcriber, listings: List[Tuple[int, str]]):
        tc.content_length(len(listings))
        for item in listings:
            tc.integer(item[0], "Item Type")
            tc.write_text(item[1], "Item Qualifier")

    @_create_tc_then_send(MsgType.items_checklist)
    def checklist(self, listings: List[ItemQualifier], tc: Transcriber = None):
        """
        Sends a checklist of item ids.

        :param listings: items whose ids are sent as a checklist
        :type listings: List
        :param tc: Transcriber that is auto created and supplied to the function.
        :type tc: Transcriber
        :return: None
        :rtype: None
        """
        self._item_list(tc, listings)

    @_create_tc_then_send(MsgType.items_request)
    def fetch_items(self, listings: List[Tuple[int, str]], tc: Transcriber = None):
        """
        Sends a request for items, given their ids.

        :param listings: list of tuples of item type and item id, whose content is requested.
        :type listings: List
        :param tc: Transcriber that is auto created and supplied to the function.
        :type tc: Transcriber
        :return: None
        :rtype: None
        """
        self._item_list_tuple(tc, listings)

    @_create_tc_then_send(MsgType.items_notfound)
    def not_found(self, listings: List[Tuple[int, str]], tc: Transcriber = None):
        """
        Sends a list of item ids that were not found.
        Can be sent after receiving a fetch items for items that were not found.

        :param listings: list of tuples of item type and item id whose content was not found
        :type listings: List
        :param tc: Transcriber that is auto created and supplied to the function.
        :type tc: Transcriber
        :return: None
        :rtype: None
        """
        self._item_list_tuple(tc, listings)

    @_create_tc_then_send(MsgType.items_content)
    def items(self, item_list: List[ItemEncodeable], tc: Transcriber = None):
        """
        Sends the items.

        :param item_list: List of items to be encoded and sent.
        :type item_list: List
        :param tc: Transcriber that is auto created and supplied to the function.
        :type tc: Transcriber
        :return: None
        :rtype: None
        """
        tc.content_length(len(item_list))

        for i in item_list:
            tc.item_content(i)

    @_create_tc_then_send(MsgType.contacts_content)
    def contacts(self, contacts: List[PeerContactInfo], tc: Transcriber = None):
        """
        Sends the contacts.
        """
        tc.content_length(len(contacts))
        for c in contacts:
            tc.contact_info(c)

    @_create_tc_then_send(MsgType.contacts_checklist)
    def contact_checklist(self, contacts: List[PeerContactQualifier], tc: Transcriber = None):
        """
        Sends a list of contact ids to neighbors.
        """
        tc.content_length(len(contacts))
        for c in contacts:
            tc.contact_qualifier(c)

    @_create_tc_then_send(MsgType.contacts_request)
    def fetch_contacts(self, contacts: List[PeerContactQualifier], tc: Transcriber = None):
        """
        Sends a request for contact information of the given ids.
        """
        tc.content_length(len(contacts))
        for c in contacts:
            tc.contact_qualifier(c)

    @_create_tc_then_send(MsgType.ping)
    def ping(self, ping: Ping = None, tc: Transcriber = None):
        """
        Sends a ping.

        :param tc: Transcriber that is auto created and supplied to the function.
        :type tc: Transcriber
        :param ping: Ping object to be sent. If None, a new ping object is created.
        :type ping: Ping
        """
        if not ping:
            ping = Ping()
        tc.ping(ping)

    @_create_tc_then_send(MsgType.pong)
    def pong(self, pong: Pong, tc: Transcriber = None):
        """
        Sends a pong in response to a ping object.
        """
        tc.pong(pong)


class SingleSocketSender(MsgSender):
    """
    Implementation of MsgSender that only sends the message over a single zmq socket.
    """

    def __init__(self, socket: zmq.Socket):
        self.socket: zmq.Socket = socket

    def _send(self, msg: Message, do_log=True):
        msg_bytes = msg_network_bytes(msg)
        if do_log:
            logger.debug("Sending message over a single socket: %s", msg_bytes)
        self.socket.send(msg_bytes)


class MultiSendSocketsSender(MsgSender):
    """
    Implementation of MsgSender that is a composition of n many MsgSender instances.
    Messages are sent over all senders.
    """

    def __init__(self, inner_senders: List[MsgSender]):
        self.inner_senders: List[MsgSender] = inner_senders

    def _send(self, msg: Message, do_log=True):
        logger.debug("Sending message to %d many recipients directly:  %s", len(self.inner_senders), msg)
        for sender in self.inner_senders:
            sender._send(msg, do_log=False)


class DropMessageSender(MsgSender):
    """
    Implementation of MsgSender that drops all outbound messages.
    """

    def __init__(self):
        super().__init__()

    def _send(self, msg: Message, do_log=True):
        logger.debug("No correct output channel was formed. Dropping to-be-sent message %s.", msg)

