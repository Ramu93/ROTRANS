from typing import Any, Dict, Optional
import logging
import traceback

from abcnet import settings
from abcnet.auth import MessageAuthenticator, NoMessageAuthenticator
from abcnet.handlers import MessageDelegator, MessageHandler
from abcnet.networking import SocketHandler, SimpleMD1, MessageDissemination, ContactBook, NetMaintainer
from abcnet.outch import OutputChannel
from abcnet.structures import Message, PeerContactQualifier, PeerContactInfo, MsgType, SocketBinding, Contact
from abcnet.settings import RuntimeSetting
from abcnet.timer import SimpleTimer

logger = logging.getLogger(__name__)


class ChannelLogger:
    """
    This module wraps around a logger and prepends peer id to every log message.
    It is used to distinguish log messages from different service channels from each other
    if they are started in the same process.
    """

    def __init__(self, my_contactinfo: PeerContactQualifier, inner_logger=logger, ):
        """
        :param my_contactinfo: contact information of the peer
        :param inner_logger:  the inner logger that is called for every log invocation. By default the module logger is used.
        """
        self.my_contactinfo = my_contactinfo
        self.inner_logger = inner_logger

    def _pre_id(self, msg):
        """
        Prepends peer id in-front of the given message and returns it as a string.
        """
        return "Node {} - {}".format(self.my_contactinfo, msg)

    def debug(self, msg, *args, **kwargs):
        self.inner_logger.debug(self._pre_id(msg), *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.inner_logger.info(self._pre_id(msg), *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.inner_logger.warning(self._pre_id(msg), *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.inner_logger.error(self._pre_id(msg), *args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self.inner_logger.exception(self._pre_id(msg), exc_info=exc_info, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.inner_logger.critical(self._pre_id(msg), *args, **kwargs)


class ChannelService:
    """
    A ChannelService manages the sockets necessary to send, broadcast and receive messages to and from peers.
    An instance of ChannelService is handed to each application in the perform maintenance method,
    to be used to contact peers in the network.
    It contains a netmaintainer instance that is responsible for the network topology.

    The most important methods are broadcast_channel and direct_channel.
    """

    def __init__(self, cb: ContactBook,
                 bind_info: SocketBinding,
                 sh: SocketHandler,
                 md: MessageDissemination,
                 ma: MessageAuthenticator,
                 nm: NetMaintainer,
                 magic_number: int):
        """
        Initializes the service by binding zeroMQ sockets.

        :param cb: Contact book instance of this service.
        :type cb: ContactBook
        :param bind_info: Socket binding info of this service.
        :type bind_info: SocketBinding
        :param ma: The authenticator implementation that is used to sign outgoing messages.
        :type ma: MessageAuthenticator
        """
        self.clog = ChannelLogger(cb.self_contact)
        self.__cb: ContactBook = cb
        self.__bind_info: SocketBinding = bind_info
        self.__sh: SocketHandler = sh
        self.__md: MessageDissemination = md
        self.__ma: MessageAuthenticator = ma
        self.__nm: NetMaintainer = nm

        self.magic_number: int = magic_number

    @staticmethod
    def initialize_service(cb: ContactBook,
                           bind_info: SocketBinding,
                           md: MessageDissemination = None,
                           ma: MessageAuthenticator = None) -> "ChannelService":
        """
        Initializes the service with default components.

        :param cb: Contact book instance of this service.
        :type cb: ContactBook
        :param bind_info: Socket binding info of this service.
        :type bind_info: SocketBinding
        :param md: Message dissemination strategy.
        :param ma: The authenticator implementation that is used to sign outgoing messages.
        :type ma: MessageAuthenticator
        """
        if cb is None or not isinstance(cb, ContactBook):
            raise ValueError("Contact book argument is not valid.")
        if bind_info is None and cb.self_contact is not None:
            bind_info = SocketBinding(publish_addr=cb.self_contact.publish_addr, direct_receive_addr=cb.self_contact.receive_addr)
        if not isinstance(bind_info, SocketBinding):
            raise ValueError("binding info is not valid.")

        if ma is None:
            logger.warning("Channel service has no message authenticator. "
                              "Outbound messages will not be authenticated.")
            ma = NoMessageAuthenticator()
            if cb.self_contact and cb.self_contact.public_key:
                raise ValueError("No authenticator was specified that can sign messages. "
                                 "The self contact however has a public key specified.")

        sh = SocketHandler(bind_info)

        if md is None:
            md: MessageDissemination = SimpleMD1(cb, sh)

        magic_nr: int = settings.RuntimeSetting.MAGIC_NUMBER

        from abcnet.networking import CliqueNetMaintainer
        nm = CliqueNetMaintainer(cb, sh)

        return ChannelService(cb, bind_info, sh, md, ma, nm, magic_nr)

    @property
    def contact(self):
        """
        Returns the self contact information of this peer.
        """
        return self.__cb.self_contact

    @property
    def contacts(self) -> ContactBook:
        """
        Returns the contact book of network peers.
        """
        return self.__cb

    @property
    def net_maintainer(self) -> NetMaintainer:
        """
        Returns the net maintainer implementation.
        """
        return self.__nm

    def poll_msg(self, timeout: float = 0.01) -> Optional[Message]:
        """
        Polls the next message from the receive sockets, waiting the given timeout if necessary.
        If no message was present in the given time, None is returned.
        polling message consumed them, and there is no way to requeue messages.
        That is why this method should only be used by a single MessageDelegator.

        :param timeout: Time in seconds to wait for the next message.
        :type timeout: float
        :return: Optionally a newly received message.
        :rtype: Optional[Message]
        """
        poller = self.__sh.msg_poller()
        msg: Optional[Message] = poller(timeout)
        return msg

    def broadcast_channel(self) -> OutputChannel:
        """
        Creates and returns an OutputChannel, that passes messages as broadcast to the entire network.

        :return: Broadcast OutputChannel
        :rtype: OutputChannel
        """
        return OutputChannel(self.__ma, self.__md.broadcast())

    def direct_channel(self, peer: PeerContactInfo) -> OutputChannel:
        """
        Creates and returns an OutputChannel, that passes messages directly to the given peer.
        Sent messages are not encrypted and could potent

        :param peer: Peer to be directly contacted.
        :type peer: PeerContactInfo
        :return: Direct OutputChannel
        :rtype: OutputChannel
        """
        if peer in self.__cb:
            self.__cb.get_peer(peer).log_outgoing_contact()
        msg_sender = self.__md.direct(peer)
        return OutputChannel(self.__ma, msg_sender)

    def shutdown(self):
        """
        Closes the sockets used by this ChannelService.
        After shutdown is called, this instance is unusable.
        This method does not block, but the underlying sockets may not close immediately.
        :return: None
        :rtype: None
        """
        self.__sh.close_all()


class BaseApp:
    """
    A Base Application instance represents a single network peer application stack.
    Each BaseApp controls a single ChannelService instance.
    There is a 1-to-1-relation between BaseApp and ChannelService.
    In the `step` method, it reads the messages from the input sockets and delegates them to the message handlers.
    """

    _handlers: Dict[str, MessageHandler]

    _msg_delegator: Optional[MessageDelegator]

    def __init__(self, cs: ChannelService, handlers: Dict[str, MessageHandler] = None):
        """
        Initializes the base application given its channel service and initial message handlers.
        Message handlers can also be registered after the baseapp has been initialized.
        The given handlers
        :param cs: Channel Service to be used.
        :type cs: ChannelService
        :param handlers: list of initial message handlers
        :type handlers: MessageHandler
        """
        self.cs = cs
        self._handlers = {}
        self._msg_delegator = None
        if handlers:
            for app_name in handlers:
                if isinstance(handlers[app_name], MessageHandler):
                    self.register_app_layer(app_name, handlers[app_name])

    def register_app_layer(self, app_name:str,  app_layer: MessageHandler):
        """
        Registers the application under the given name.
        """
        if app_name not in self._handlers:
            logger.debug("Added new app layer: %s", app_name)
        else:
            logger.info("App replaced: %s", app_name)
        self._handlers[app_name] = app_layer
        del self._msg_delegator
        self._msg_delegator = None

    def app(self, app_name: str) -> Any:
        """
        Returns the app that was registered under the given name.
        """
        return self._handlers[app_name]

    @property
    def msg_del(self):
        """
        Returns the message delegator.
        """
        if self._msg_delegator is None:
            self._msg_delegator = MessageDelegator(self._handlers.values())
        return self._msg_delegator

    def maintain(self, force_maintenance=False):
        """
        Performs a maintenance of all registered applications.
        """
        for app_name in self._handlers:
            app = self._handlers[app_name]
            timer = RuntimeSetting.APP_LAYER_MAINTENANCE_TIMEOUT_WARN_LOG.stop_timer(start=True)
            try:
                maintenance_performed = False
                try:
                    app.perform_maintenance(self.cs, force_maintenance=force_maintenance)
                    maintenance_performed = True
                except TypeError as e:
                    if str(e) != 'perform_maintenance() got an unexpected keyword argument \'force_maintenance\'':
                        raise
                if not maintenance_performed:
                    app.perform_maintenance(self.cs)
            except Exception as e:
                logger.error("Error performing maintenance in %s.", app_name, exc_info=True)

            if timer.check():
                logger.warning("App maintenance of handler %s took too long: %s", app_name, timer.run_time_str())

    def handle_next_msg(self, timeout: float) -> bool:
        """
        Handles a single message that can be polled in the given time.
        """
        return self.msg_del.delegate_next_msg(timeout, self.cs)

    def handle_remaining_messages(self, timeout: float = 0):
        """
        Pulls messages until timeout and handles each message sequentially.
        """
        timer = SimpleTimer(timeout, start=True)
        message_remain = True
        while message_remain:
            message_remain = self.handle_next_msg(timer.remaining_time)

    def step(self, timeout: float):
        """
        Performs a step.
        A step consists of a perform maintenance round and handling the remaining input queue.
        """
        self.maintain()
        self.handle_remaining_messages(timeout)

    def close(self):
        """
        Closes the application, shutting down all apps.
        """
        for app in self._handlers.values():
            try:
                app.close()
            except Exception:
                logger.warning("Exception while closing app: {}", app)
                traceback.print_exc()
        self.cs.shutdown()
