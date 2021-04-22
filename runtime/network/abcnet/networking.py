from enum import Enum, auto
from typing import List, Dict, Optional, Callable, Tuple

import zmq
import logging

from abcnet import settings, transcriber
from abcnet.handlers import MessageHandler
from abcnet.outch import OutputChannel, MultiSendSocketsSender, DropMessageSender, MsgSender, SingleSocketSender
from abcnet.settings import MsgPoller, PeerSetting
from abcnet.structures import Qualifier, PeerContactInfo, get_qualifier_helper, SocketBinding, Contact, get_caller, \
    PeerContactQualifier, Message, MsgType
from abcnet.timer import StopTimer, SimpleTimer

logger = logging.getLogger(__name__)


class PeerStats:
    """
    Wrapper around a peer contact info or qualifier.
    Each neighbor has a PeerStats object for them.
    Holds the current state of the connection, such as is introduced to or not.
    """

    peer_contact: Contact

    _introduced: bool

    _requested: bool

    _ingoing_contact_sw: Optional[StopTimer]
    _outgoing_contact_sw: Optional[StopTimer]

    def __init__(self, peer: Contact, unintroduced: bool):
        """
        Initializes a fresh peer stats objects.
        :param peer: Neighbor contact info or qualifier
        :param unintroduced: flag that indicates whether an introduction to the peer has happened yet.
        """
        self.peer_contact = self.__check_new_contact(peer)
        self._introduced = not unintroduced

        self._ingoing_contact_sw = None
        self._outgoing_contact_sw = None

        self._requested = False
        self._subscribed = False

    @staticmethod
    def __check_new_contact(new_peer_contact: Contact):
        """
        Validates contact information.
        :param new_peer_contact: To be validated contact information
        :return: the input if valid, else raises value error
        """
        if not new_peer_contact:
            raise ValueError("New peer contact is empty.")
        return new_peer_contact

    @property
    def is_full(self) -> bool:
        """
        Flag that indicates if the current peer contact info is full.
        If a contact info is full, then it holds the values neccessary to contact it.
        If false, then the contact info merely consists of the network identifier of the peer.
        :return: True, if information is enough to contact peer.
        """
        return isinstance(self.peer_contact, PeerContactInfo)

    @property
    def is_introduced(self) -> bool:
        """
        Flag that indicates whether this process has already introduced itself to the peer.
        An introduction consists of sending ones own contact info to the peer so it can send messages back.
        :return: True, if process has introduced itself to the peer.
        """
        return self._introduced

    @property
    def is_requested(self) -> bool:
        """
        Returns true if the contact is requested.
        """
        return self._requested

    @is_introduced.setter
    def is_introduced(self, introduced: bool):
        """
        Sets the introduce flag.
        The introduce flag can only be set to true or else an exception is thrown.
        :param introduced: The new state of the introduce flag.
        """
        if self._introduced and not introduced:
            raise ValueError("Cannot set introduced to false.")
        self._introduced = introduced

    @is_requested.setter
    def is_requested(self, requested: bool):
        """
        Sets the is_requested flag.
        """
        self._requested = requested

    @property
    def subscribed(self):
        return self._subscribed

    @subscribed.setter
    def subscribed(self, subscribed: bool):
        self._subscribed = subscribed

    def check_contact_match(self, new: PeerContactInfo):
        assert self.is_full
        original = self.peer_contact
        is_a_match = original == new
        if not is_a_match:
            raise ValueError(f"The new contact information of {new.identifier} is not compatible to the old record: "
                             f"\n Old: {original.__repr__()}"
                             f"\n New: {new.__repr__()}")

    def update_contact(self, new_peer_contact: Contact) -> bool:
        """
        Updates the contact information of the peer.
        If a full contact information is replaced by the qualifier a warning is posted.
        """
        self.__check_new_contact(new_peer_contact)
        if self.is_full:
            self.check_contact_match(new_peer_contact)
            return False
        if self.is_full and not isinstance(new_peer_contact, PeerContactInfo):
            logger.warning("Degrading peer contact info from:\n%s \nto:\n%s", self.peer_contact, new_peer_contact)
        if isinstance(new_peer_contact, PeerContactInfo):
            self.peer_contact = new_peer_contact
            return True
        return False

    def log_ingoing_contact(self):
        """
        Accepts the event that this peer has contacted us.
        A stop timer will be reset.
        """
        if self._ingoing_contact_sw is None:
            self._ingoing_contact_sw = PeerSetting.SILENT_PEER__REINTRO_TIMEOUT.stop_watch()
        self._ingoing_contact_sw.reset()

    def log_outgoing_contact(self):
        """
        Accepts the event that this peer has been directly contacted.
        A stop timer will be reset.
        """
        if self._outgoing_contact_sw is None:
            self._outgoing_contact_sw = PeerSetting.SILENT_PEER__REINTRO_TIMEOUT.stop_watch()
        self._outgoing_contact_sw.reset()

    @staticmethod
    def __stopwatch_passed_threshold(stop_watch: Optional[StopTimer], time_threshold: float) -> bool:
        if stop_watch is None:
            return False
        else:
            return stop_watch.has_passed(time_threshold)

    def __in_timeout(self, time_threshold: float) -> bool:
        """Measures if incoming contact stop watch has passed the given time threshold."""
        return self.__stopwatch_passed_threshold(self._ingoing_contact_sw, time_threshold)

    def __out_timeout(self, time_threshold: float) -> bool:
        """Measures if direct contact stop watch has passed the given time threshold."""
        return self.__stopwatch_passed_threshold(self._outgoing_contact_sw, time_threshold)

    def peer_reintroduction_timeout(self) -> bool:
        """
        Returns true if the peer has been silent for too long and is to be reintroduced to.
        threshold: PeerSetting.SILENT_PEER__REINTRO_TIMEOUT
        """
        return self.__in_timeout(PeerSetting.SILENT_PEER__REINTRO_TIMEOUT.time_period())

    def peer_stale_connection_timeout(self) -> bool:
        """
        Returns true if the connection is stale.
        The connection is considered stale if the time since the last incoming message form the peer
        has passed a certain threshold defined in the setting.
        threshold: PeerSetting.STALE_CONNECTION_TIMEOUT
        """
        return self.__in_timeout(PeerSetting.STALE_CONNECTION_TIMEOUT.time_period())

    def direct_connection_timeout(self) -> bool:
        """
        Returns true if the time since the last direct outbound contact to the peer is longer than a certain threshold.
        threshold: PeerSetting.DIRECT_CONTACT_CLEANUP_TIMEOUT
        """
        return self.__out_timeout(PeerSetting.DIRECT_CONTACT_CLEANUP_TIMEOUT.time_period())

    def reset_outgoing_contact_sw(self):
        """
        Sets the outgoing contact stopwatch to None.
        This way we know that we have no direct connection to the peer.
        """
        self._outgoing_contact_sw = None

class PeerEvent(Enum):
    """
    PeerEvent is the enum class of all peer events.
    PeerEvents are sent together with peerstats as a mechanism to convey their new state.
    """
    contact_new = auto()
    contact_update = auto()
    contact_connection_lost = auto()
    contact_delete = auto()

    subscribed = auto()


PeerObserver = Callable[[PeerEvent, PeerStats], None]
"""
PeerObserver is the type name of any object that is used as a observer.
Hooked observers are called with peer updates.
"""


class ContactBook:
    """
    This represents this set of all known network peers.
    A single contact book object is shared among network modules.
    """

    __all_peers: Dict[str, PeerStats] = dict()

    _self_contact: PeerContactInfo

    _observers: List[PeerObserver]

    event_logger = logging.getLogger(__name__ + ".events")

    def __init__(self, self_contact: PeerContactInfo = None, initial_contacts: List[PeerContactInfo] = None):
        """
        Initializes the contact book.
        Optionally accepts self contact info and initial contact list.
        If self contact info is not given, this contact book cannot make sure that the agent doesn't connect to itself.
        """
        self.__all_peers = dict()
        self._self_contact = self_contact
        self._observers = list()
        if initial_contacts is not None and isinstance(initial_contacts, List):
            for ic in initial_contacts:
                self.get_or_create_peer(ic)

    def hook_observer(self, observer: PeerObserver):
        """
        Adds the given observer to the list of overservers.
        If the key
        """
        if ContactBook.event_logger.isEnabledFor(logging.INFO):
            ContactBook.event_logger.info("Peer observer added by: %s", get_caller())
        self._observers.append(observer)

    def post_event(self, event: PeerEvent, peer: PeerStats):
        """
        Posts a peer event regarding the given peer and calls all observers.
        """
        if ContactBook.event_logger.isEnabledFor(logging.DEBUG):
            ContactBook.event_logger.debug("Peer event %s for peer `%s` was posted: \n\t%s",
                    event, peer.peer_contact.identifier,
                    get_caller())
        for o in self._observers:
            try:
                o(event, peer)
            except Exception as ex:
                import traceback
                logger.error("Error trying to post event to observer.")
                traceback.print_exc()

    @property
    def self_contact(self) -> Optional[PeerContactInfo]:
        """
        Optionally returns the self contact information if available.
        """
        return self._self_contact

    def is_self_contact(self, contact: Qualifier):
        """
        Returns true if the given qualifier matches the self contact.
        """
        q = get_qualifier_helper(contact)
        if self.self_contact is not None and \
                self.self_contact.identifier == q:
            return True
        return False

    def get_peer(self, _peer_qualifier: Qualifier) -> Optional[PeerStats]:
        """
        Gets the peer statistics for the given peer qualifier.
        """
        if self.is_self_contact(_peer_qualifier):
            return None
        q = get_qualifier_helper(_peer_qualifier)
        if q in self.__all_peers:
            return self.__all_peers[q]
        else:
            return None

    def __contains__(self, peer: Qualifier) -> bool:
        """
        Returns true if the given qualifier is defined in this instance.
        """
        return self.get_peer(peer) is not None

    def __delitem__(self, peer: Qualifier):
        """
        Deletes the peer from this instance.
        """
        q = get_qualifier_helper(peer)
        del self.__all_peers[q]

    def all_peers(self) -> List[PeerStats]:
        """
        Return a list of all peers statistics.
        """
        return list(self.__all_peers.values())

    def neighbors(self) -> List[Contact]:
        """
        Returns a list of all peer peer contact information.
        """
        return list(map(lambda p: p.peer_contact, self.__all_peers.values()))

    def get_or_create_peer(self, contact: Contact) -> Tuple[PeerStats, bool]:
        """
        Gets the peer statistics that can be found for the given contact qualifier
        or creates one with the given information.
        """
        if self.is_self_contact(contact):
            raise ValueError("Cannot create a peer object out of self contact.")
        ps: PeerStats = self.get_peer(contact)
        if ps:
            # Peer is already defined. Return from memory:
            return ps, False
        logger.debug("New contact was entered: %s", repr(contact))
        # New peer statistics is created.
        ps = PeerStats(contact, True)
        self.__all_peers[ps.peer_contact.identifier] = ps
        return ps, True

    def clear(self):
        """
        Clears all peer informations.
        """
        for ps in self.__all_peers.values():
            self.post_event(PeerEvent.contact_delete, ps)
        self.__all_peers.clear()


def _check_is_closed(f):
    """
    A decorator that is used to check if the socket handler is closed or not.
    """
    def function_that_first_checks_closed(self: "SocketHandler", *args, **kwargs):
        if self.closed:
            raise ValueError("Socket handler is closed but was still called.")
        return f(self, *args, **kwargs)

    return function_that_first_checks_closed


class SocketHandler:
    """
    This class handles sockets and the integration of the network library.
    """
    def __init__(self, socket_binding: SocketBinding):
        self.socket_binding = socket_binding
        self.closed = False
        # Setting the properties:
        # Context object based on the settings:
        context: zmq.Context = settings.NetworkBackend.context()
        # The initial socket fields:
        self._publish_socket: Optional[zmq.Socket]
        self._all_receiving_sockets: List[zmq.Socket] = []
        self._msg_poller: Optional[MsgPoller] = None
        self._all_sending_sockets: Dict[str, zmq.Socket] = dict()
        # Bind the sockets
        # Publish socket
        if socket_binding.bind_publish_addr is None:
            self._publish_socket = None
            logger.warning("Not binding any publish address.")
        else:
            self._publish_socket = context.socket(zmq.PUB)
            self._publish_socket.bind(socket_binding.bind_publish_addr)
            logger.debug('Bound socket %s for publishing.', socket_binding.bind_publish_addr)
        # Direct and receiving socket
        self._direct_receive_socket: Optional[zmq.Socket]
        if socket_binding.bind_direct_addr is None:
            logger.warning("Not binding any direct receive address.")
            self._direct_receive_socket = None
        else:
            self._direct_receive_socket = context.socket(zmq.DEALER)
            self._direct_receive_socket.bind(socket_binding.bind_direct_addr)
            self._all_receiving_sockets.append(self._direct_receive_socket)
            logger.debug("Bound socket %s for listening to direct messaged.", socket_binding.bind_direct_addr)
        # Subscribe socket
        self._subscribe_socket: zmq.Socket = context.socket(zmq.SUB)
        self._subscribe_socket.subscribe(b'')
        self._all_receiving_sockets.append(self._subscribe_socket)
        logger.debug("Created subscribe socket.")

    @_check_is_closed
    def receive_sockets(self) -> List[zmq.Socket]:
        """
        Returns list of all receiving sockets that can be pulled for messages of the network.
        """
        return self._all_receiving_sockets

    @_check_is_closed
    def msg_poller(self) -> MsgPoller:
        """
        Returns a message poller object.
        """
        if self._msg_poller:
            return self._msg_poller
        self._msg_poller = settings.NetworkBackend.msg_poller(self.receive_sockets(),
                                                              lambda s: s != self._subscribe_socket)
        return self._msg_poller

    @_check_is_closed
    def subscribe(self, address: str):
        """Subscribes to the given address for broadcast messages."""
        self._subscribe_socket.connect(address)

    @_check_is_closed
    def unsubscribe(self, address: str):
        """Unsubscribes from the given address. If the address was not subscribed before nothing happens."""
        self._subscribe_socket.disconnect(address)

    @_check_is_closed
    def publish_socket(self) -> Optional[zmq.Socket]:
        """Returns the socket used for broadcast messages."""
        return self._publish_socket

    @_check_is_closed
    def direct_sending_socket(self, address: str) -> zmq.Socket:
        """Returns a socket for direct messages to the given peer."""
        if address in self._all_sending_sockets:
            return self._all_sending_sockets[address]
        direct_socket = settings.NetworkBackend.context().socket(zmq.DEALER)
        direct_socket.connect(address)
        self._all_sending_sockets[address] = direct_socket
        logger.info("Created direct sending socket to %s", address)
        return direct_socket

    @_check_is_closed
    def close_direct_sending_socket(self, address: str):
        """Closes a direct socket to the given peer. """
        if address in self._all_sending_sockets:
            self._all_sending_sockets[address].close()
            del self._all_sending_sockets[address]
            logger.info("Closed direct sending socket to %s", address)

    @_check_is_closed
    def close_all(self):
        """Closes all sockets."""
        self.closed = True
        if self._direct_receive_socket is not None:
            self._direct_receive_socket.close()
            del self._direct_receive_socket

        if self._publish_socket is not None:
            self._publish_socket.close()
            del self._publish_socket

        self._subscribe_socket.close()
        del self._subscribe_socket

        for socket in self._all_sending_sockets.values():
            socket.close()
        self._all_sending_sockets.clear()
        self._all_receiving_sockets.clear()


class MessageDissemination:
    """
    This class implements the message dissemination strategy.
    Direct channels are usually using direct messages.
    Broadcast channels can use a combinations of direct messages and publish messages. For example the Push Protocol.
    """

    def broadcast(self) -> MsgSender:
        """
        Creates and returns an OutputChannel, that passes messages as broadcast to the entire network.

        :return: Broadcast OutputChannel
        :rtype: OutputChannel
        """

    def direct(self, peer: Qualifier) -> MsgSender:
        """
        Creates and returns an OutputChannel, that passes messages directly to the given peer.
        Sent messages are not encrypted and could potent.

        :param peer: Peer to be directly contacted.
        :type peer: PeerContactInfo
        :return: Direct OutputChannel
        :rtype: OutputChannel
        """

    def close_connection(self, peer: Qualifier):
        """
        Closes the connection to the given peer.
        """


class SimpleMD1(MessageDissemination):
    """
    Implementation of the message dissemination protocoll that assumes a clique network topology.
    Broadcast messages are sent over the publish socket once.
    And direct messages are sent using direct sockets.
    """
    def __init__(self, contact_book: ContactBook, socket_handler: SocketHandler):
        self.socket_handler: SocketHandler = socket_handler
        self.contact_book: ContactBook = contact_book

    def neighbors(self) -> List[Qualifier]:
        """List of neighbors"""
        return self.contact_book.neighbors()

    def broadcast(self) -> MsgSender:
        if self.socket_handler.publish_socket() is not None:
            return SingleSocketSender(self.socket_handler.publish_socket())
        else:
            if self.neighbors():
                senders: List[MsgSender] = [sender for sender in
                                            [self.direct(peer) for peer in self.neighbors()]
                                            if sender is not None]
                if senders:
                    return MultiSendSocketsSender(senders)
        return DropMessageSender()

    def direct(self, peer: Qualifier) -> MsgSender:
        if peer in self.contact_book:
            ps = self.contact_book.get_peer(peer)
            peer = ps.peer_contact
        if not isinstance(peer, PeerContactInfo):
            return DropMessageSender()
        if not peer.is_reachable:
            logger.debug("Cannot create direct connection to %s, as it is not reachable.", peer)
            return DropMessageSender()
        socket = self.socket_handler.direct_sending_socket(peer.receive_addr)
        return SingleSocketSender(socket)


class NetMaintainer(MessageHandler):
    """
    This class implements the strategy of the process integrate into the network. Different topologies can be
    achieved by creating a sub-class of this class. It is assumed that all nodes use the same net maintainer
    protocol. Every net maintainer is a message handler that receives and handles the network bootstrap messages and
    performs maintenance.
    """

    def accept(self, cs: "ChannelService", msg: Message, **kwargs):
        """
        Accept a network message.
        A network message have one of the following types:
        contacts_checklist, contacts_request, contacts_content

        :param cs: Channel Service used for messages to be sent back.
        :param msg: Incoming message.
        :param kwargs: Further arguments
        """
        if not msg.msg_type:
            cs.clog.warning("No message type was specified")
        if msg.msg_type == MsgType.contacts_checklist:
            self._handle_checklist(cs, msg)
        if msg.msg_type == MsgType.contacts_request:
            self._handle_contact_request(cs, msg)
        if msg.msg_type == MsgType.contacts_content:
            self._handle_contact_info(cs, msg)

    def _handle_checklist(self, cs: "ChannelService", msg: Message):
        contact_checklist: List[PeerContactQualifier] = transcriber.parse_contacts_qualifier(msg)
        self.sync_checklist(cs, contact_checklist)

    def _handle_contact_request(self, cs: "ChannelService", msg: Message):
        requested_contacts: List[PeerContactQualifier] = transcriber.parse_contacts_qualifier(msg)
        self.resolve_contact_info_request(requested_contacts)

    def _handle_contact_info(self, cs: "ChannelService", msg: Message):
        contact_info_list: List[PeerContactInfo] = transcriber.parse_contacts(msg)
        self.enter_contacts(cs, contact_info_list)

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        """
        Performs maintenance on the network layer. This includes sending messages to neighbors
        to resolve peer contact information and so on.
        :param cs: channel used to contact peers
        :type cs: ChannelService
        :return: None
        :rtype: None
        """
        pass

    def enter_contacts(self, cs: "ChannelService", new_peers: List[PeerContactInfo]):
        """
        The NetMaintainer is offered a list of peers to enter as new contacts.
        The implementation of the NetMaintainer can decide against adding these contacts,
        even if they are unknown to it.

        :param new_peers: Peers to be entered as new contacts.
        :type new_peers: List[PeerContactInfo]
        :return: None
        :rtype: None
        """
        pass

    def sync_checklist(self, cs: "ChannelService", checklist: List[PeerContactQualifier]):
        """
        The NetMaintainer syncronizes its contact info book with the provided list of peer qualifier.
        If any unkown contacts are among it, the netmaintainer can decide to resolve them in his "perform maintenance"
        round.
        :param checklist: Peer qualifier of neighbors.
        :type checklist: List[PeerContactQualifier]
        :return: None
        :rtype: None
        """
        pass

    @property
    def neighbors(self) -> List[PeerContactInfo]:
        """
        Returns the list of contact info on neighbors nodes.
        Not every neighbor can be contacted necessarily.

        :return: List of neighbor node contact info.
        """
        pass

    def resolve_contact_info_request(self, requested_contacts: List[PeerContactQualifier]):
        """
        Handles the request for contact details of the given list.

        :param requested_contacts: Required contacts.
        :type requested_contacts: List[PeerContactQualifier]
        :return: None
        :rtype: None
        """

    def resolve_contact_info(self, requested_contacts: List[PeerContactQualifier]) \
            -> Tuple[List[PeerContactInfo], List[PeerContactQualifier]]:
        """
        Given a list of peer qualifier, this method resolves the contact info of those peers he knows.

        :param requested_contacts: Requested peers by the contact qualifier.
        :type requested_contacts: List of PeerContactQualifier
        :return: First return item is the list of resolved contact info. The second return item is the list of
        unknown contact qualifier.
        """


class CliqueNetMaintainer(NetMaintainer):
    """
    This implementation of the netmaintainer connects to every node and forms a clique.
    """

    timer_peer_sync: SimpleTimer
    timer_peer_broadcast: SimpleTimer
    timer_unknown_peer_request: SimpleTimer

    new_peers: bool

    def __init__(self, cb: ContactBook, sh: SocketHandler):
        """
        :param channel_service: There is a one to one relation between channel service and netmaintainer
        instances because they are so closely related.
        """
        self.__cb = cb
        self.__sh = sh
        self.timer_peer_sync = PeerSetting.CLIQUE_PEER_SYNC_TIMEOUT.stop_timer()
        self.timer_peer_broadcast = PeerSetting.CLIQUE_NEW_PEERS_SYNC_TIMEOUT.stop_timer()
        self.timer_unknown_peer_request = PeerSetting.CLIQUE_UNKNOWN_PEER_REQUEST_TIMEOUT.stop_timer()
        self.timer_peer_introduction = PeerSetting.CLIQUE_PEER_INTRODUCTION.stop_timer()
        self.timer_direct_contact_cleanup = PeerSetting.CLIQUE_DIRECT_CONTACT_CLEANUP_TIMEOUT.stop_timer()
        self.timer_resolve_requested = PeerSetting.CLIQUE_RESOLVE_REQUESTED_TIMEOUT.stop_timer()
        self.new_peers = False
        for peer in cb.all_peers():
            self.process_peer(peer, True, peer.peer_contact)

    @property
    def neighbors(self) -> List[PeerContactQualifier]:
        return self.__cb.neighbors()

    def _handle_contact_info(self, cs: "ChannelService", msg: Message):
        contact_info_list: List[PeerContactInfo] = transcriber.parse_contacts(msg)
        self.enter_contacts(cs, contact_info_list)

    def enter_contacts(self, cs: "ChannelService", new_peers: List[PeerContactInfo]):
        for peer in new_peers:
            self.process_contact(peer)
            self.unset_requested(peer)

    def sync_checklist(self, cs: "ChannelService", checklist: List[PeerContactQualifier]):
        for peer in checklist:
            self.process_contact(peer)

    def process_contact(self, peer: Contact):
        if peer is None:
            raise ValueError("New contact info is empty.")

        if self.__cb.is_self_contact(peer):
            return

        is_full: bool = isinstance(peer, PeerContactInfo)
        is_qualifier: bool = isinstance(peer, PeerContactQualifier)
        if not (is_full or is_qualifier):
            raise ValueError("New contact has unexpected type: " + str(peer.__class__))
        ps, is_new = self.__cb.get_or_create_peer(peer)
        self.process_peer(ps, is_new, peer)

    def process_peer(self, ps: PeerStats, is_new: bool, contact_info: Contact):
        peer = ps.peer_contact
        if is_new:
            logger.info("New contact found: %s", peer.identifier)
            self.__cb.post_event(PeerEvent.contact_new, ps)
        if not ps.is_full:
            logger.info("Updating contact information of: %s", repr(peer))
            was_updated = ps.update_contact(contact_info)
            if was_updated:
                self.__cb.post_event(PeerEvent.contact_update, ps)
        if not ps.subscribed and ps.is_full and ps.peer_contact.is_publisher:
            self.__sh.subscribe(ps.peer_contact.publish_addr)
            ps.subscribed = True
            self.__cb.post_event(PeerEvent.subscribed, ps)

    def unset_requested(self, peer: PeerContactInfo):
        ps = self.__cb.get_peer(peer)
        if ps:
            ps.is_requested = False

    def broadcast_peer_checklist(self, cs):
        peers = self.__cb.neighbors()
        if self.__cb.self_contact:
            peers.append(self.__cb.self_contact)
        cs.broadcast_channel().contact_checklist(peers)

    @staticmethod
    def unintroduced_peers_filter(ps: PeerStats) -> bool:
        return ps.is_full and not ps.is_introduced

    @staticmethod
    def silent_peers_filter(ps: PeerStats) -> bool:
        return ps.is_full and ps.peer_reintroduction_timeout()

    def introduce_to_peers(self, cs):
        # introduce to both silent and unintroduced peers
        for ps in filter(lambda p:
                         self.unintroduced_peers_filter(p) or
                         self.silent_peers_filter(p),
                         self.__cb.all_peers()):
            peer = ps.peer_contact
            if not peer.is_reachable:
                cs.clog.warning("cannot introduce to %s because it is not directly reachable.", peer)
                ps.is_introduced = True
                continue
            else:
                cs.clog.info("Introducing my contact information to peer: %s", peer)
            ch: OutputChannel = cs.direct_channel(peer)
            ch.contacts([cs.contact])
            if not ps.is_introduced:
                ps.is_introduced = True

    def unknown_peers(self) -> List[PeerStats]:
        return [p for p in self.__cb.all_peers() if not p.is_full]

    def request_unknown_peers(self, cs):
        u_peers = self.unknown_peers()
        if u_peers:
            cs.clog.info("Unknown peers have been found. Requesting their contact information "
                         "by broadcasting their ids.")
            cs.broadcast_channel().fetch_contacts([ps.peer_contact
                                                        for ps in u_peers])

    def resolve_contact_info_request(self, requested_contacts: List[PeerContactQualifier]):
        for contact in requested_contacts:
            ps = self.__cb.get_peer(contact)
            if ps:
                ps.is_requested = True

    def requested_peers(self) -> List[PeerStats]:
        return [p for p in self.__cb.all_peers() if p.is_full and p.is_requested]

    def broadcast_requested_peers(self, cs: "ChannelService"):
        requested_peers = self.requested_peers()
        if requested_peers:
            requested_peer_contacts = [ps.peer_contact for ps in requested_peers]
            resolved_contacts, _ = self.resolve_contact_info(requested_peer_contacts)
            cs.broadcast_channel().contacts(resolved_contacts)
            for requested_peer in requested_peers:
                requested_peer.is_requested = False
            cs.clog.info("Just Broadcast %d many requested contact infos to the network.", len(resolved_contacts))

    def resolve_contact_info(self, requested_contacts: List[PeerContactQualifier]) \
            -> Tuple[List[PeerContactInfo], List[PeerContactQualifier]]:
        found_contacts: List[PeerContactInfo] = list()
        not_found_contacts = list()
        for contact_qualifier in requested_contacts:
            ps: PeerStats = self.__cb.get_peer(contact_qualifier)
            contact_found = False
            if ps and ps.is_full:
                found_contacts.append(ps.peer_contact)
                contact_found = True
            if not contact_found:
                not_found_contacts.append(contact_qualifier)
        return found_contacts, not_found_contacts

    def clean_direct_channel(self, p: PeerStats):
        if p.is_full and p.peer_contact.is_reachable:
            self.__sh.close_direct_sending_socket(p.peer_contact.receive_addr)

    def close_peer_connection(self, peer: PeerStats):
        logger.info("Peer `%s`, is found to be stale. Closing peer connection.", peer)
        if not peer.is_full:
            return
        if peer.peer_contact.is_reachable:
            self.__sh.close_direct_sending_socket(peer.peer_contact.receive_addr)
        if peer.peer_contact.is_publisher:
            self.__sh.unsubscribe(peer.peer_contact.publish_addr)

    def remove_peer_stats(self, peer: PeerStats):
        logger.info("Peer `%s`, is found to be stale. Removing information from memory", peer)
        if peer.peer_contact in self.__cb:
            del self.__cb[peer.peer_contact]

    def clean_peers(self, cs: "ChannelService"):
        # Clean all stale direct channels
        for p in self.__cb.all_peers():
            out_going_timeout = p.direct_connection_timeout()
            if out_going_timeout:
                self.clean_direct_channel(p)
            p.reset_outgoing_contact_sw()

        stale_peers = list(filter(PeerStats.peer_stale_connection_timeout, self.__cb.all_peers()))
        for p in stale_peers:
            self.close_peer_connection(p)
            self.remove_peer_stats(p)

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        stopper = StopTimer()
        if self.new_peers and self.timer_peer_broadcast():
            cs.clog.info("New peers have been found. Broadcasting peer list.")
            self.new_peers = False
            self.broadcast_peer_checklist(cs)
        elif force_maintenance or self.timer_peer_sync():
            cs.clog.debug("Syncing peer qualifier list by broadcasting it to the network.")
            self.broadcast_peer_checklist(cs)
        if force_maintenance or self.timer_unknown_peer_request():
            self.request_unknown_peers(cs)
        if force_maintenance or self.timer_peer_introduction():
            self.introduce_to_peers(cs)
        if force_maintenance or self.timer_direct_contact_cleanup():
            self.clean_peers(cs)
        if force_maintenance or self.timer_resolve_requested():
            self.broadcast_requested_peers(cs)
        if stopper.time() > 0.1:
            cs.clog.info("Network maintenance took %s", stopper)


class PeerConnectionWatchdog(MessageHandler):

    def __init__(self, __cb: ContactBook):
        self.__cb = __cb

    def accept(self, cs: "ChannelService", msg: Message) -> None:
        if msg.sender is None:
            logger.debug("The received message has no sender.")
            return
        if not msg.is_authenticated:
            logger.debug("Message was not authenticated by the sender: %s", msg.sender)
            return
        if not msg.is_direct:
            logger.debug("Only interested in direct messages.")
            return
        peer_stats: PeerStats = self.__cb.get_peer(msg.sender)
        if peer_stats is not None:
            peer_stats.log_ingoing_contact()
