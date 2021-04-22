from typing import Dict, Callable, List, Union, Optional
import os

import zmq

from abcnet import zmq_integration
from abcnet.timer import SimpleTimer, StopTimer

from abcnet.zmq_integration import _new_zmq_context


class Units:
    """
    This class contains all units that are used in settings.
    """
    class ConstantTimeout:
        """
        Constant timeout unit is used anywhere a timeout period or a frequency of operation is being configured.
        """
        def __init__(self, time_seconds: float):
            self.period_in_seconds = time_seconds

        def time_period(self):
            return self.period_in_seconds

        def stop_timer(self, *args, **kwargs) -> SimpleTimer:
            return SimpleTimer(self.time_period(), *args, **kwargs)

        def stop_watch(self) -> StopTimer:
            return StopTimer(self.time_period())

# Message poller type:
MsgPoller = Callable[[Optional[float]], Optional["Message"]]

# The protocol version
PROTOCOL_VERSION = 0x00000001

# The network magic values
MAGIC_NUMBERS = {
    "main":     0xD7F4446B,
    "test":     0x94B07E6F,
}


class PeerSetting:

    CLIQUE_PEER_SYNC_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(10)
    """
    Timeout in seconds, after which the network maintainer broadcasts a list of his neighbors to each of it neighbors 
    to the network.
    """

    CLIQUE_NEW_PEERS_SYNC_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(2)
    """
    Timeout in seconds, after which the network maintainer broadcasts information about new peers to the network.
    """

    CLIQUE_UNKNOWN_PEER_REQUEST_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(2)
    """
    Timeout in seconds, after which the network maintainer requests peer contact information for the peers
    he only knows the id of. 
    """

    CLIQUE_PEER_INTRODUCTION: Units.ConstantTimeout = Units.ConstantTimeout(3)
    """
    Timeout in seconds, after which the network maintainer introduces it self to all unintroduced peers.
    """

    CLIQUE_DIRECT_CONTACT_CLEANUP_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(10)
    """
    Timeout in seconds, after which the network maintainer cleans up direct sockets that were unused for at least 
    `DIRECT_CONTACT_CLEANUP_TIMEOUT` time.
    """

    DIRECT_CONTACT_CLEANUP_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(10)
    """
    Timeout in seconds, after which an direct socket will be cleaned up.
    Using the direct socket will reset the timeout.
    """

    CLIQUE_RESOLVE_REQUESTED_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(5)
    """
    Timeout in seconds, after which all requested peer contact info will be broadcasted.
    """

    SILENT_PEER__REINTRO_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(30)
    """
    Number of seconds that we wait while a peer is silent until we reintroduce ourselves.
    """

    STALE_CONNECTION_TIMEOUT: Units.ConstantTimeout = Units.ConstantTimeout(300)
    """
    Number of seconds that we wait until we declare a silent peer connection as stale.
    """


class RuntimeSetting:

    MAGIC_NUMBER: int = MAGIC_NUMBERS["main"]
    """
    The magic number prepended to all messages.
    This number signals the network.
    """

    APP_LAYER_MAINTENANCE_TIMEOUT_WARN_LOG: Units.ConstantTimeout = Units.ConstantTimeout(0.1)
    """
    If the time of application layer maintenance exceed this timeout, it will be logged as warning.
    """


class PingSetting:

    PING_BEACON_ENABLED: bool = True
    """
    If true, a ping is broadcast every so often.
    """

    PING_INTERVAL: Units.ConstantTimeout = Units.ConstantTimeout(2)
    """
    Ping beacon timeout.
    """


class NetStatSettings:

    STAT_SERIALIZATION_TIMER: Units.ConstantTimeout = Units.ConstantTimeout(5)
    """
    The time in seconds between each time the cache of logs are pushed onto the disk.
    """

    MEM_LINE_CHUNKS: int = 20
    """
    Number of lines that are kept in memory before writing it into the file.
    """

    STAT_SERIALIZATION_EVENT_SEP: str = '-' + ('=' * 78) + os.linesep
    """
    The line that separates two events in the stat file"""

    EVENT_DELETE_BATCH_SIZE: int = 500
    """
    The size at which the event are deleted in batched.
    At 500 with an avg event size of 100 bytes memory is cleared in batches of 50 kilobytes.
    """

    STAT_SERIALIZATION_FILE_ENDING: str = ".stats.yaml"
    """
    The file ending of statisitc serialization file.
    """

    STAT_SERIALIZATION_DIR: str = "netstats"
    """
    The directory that contains the serialized stats.
    """

    STAT_SERIALIZATION_DATE_TIME_SUB_DIR: bool = True
    """
    If true, another directory is created below the STAT_SERIALIZATION_DIR file that has the process time as name.
    Use to avoid collision when running multiple times.
    """

    __MSG_PACKER_MAPPING: Dict[int, Callable[["Message"], Union[Dict, List, int, str]]] = None

    @staticmethod
    def MSG_PACKER_ORACLE() -> Dict[int,
                                  Callable[["Message"], Union[Dict, List, int, str]]]:
        if NetStatSettings.__MSG_PACKER_MAPPING is None:
            import abcnet.netstats_serialization
            NetStatSettings.__MSG_PACKER_MAPPING = abcnet.netstats_serialization.default_msg_packers()
        return NetStatSettings.__MSG_PACKER_MAPPING

    __ITEM_TYPE_MAPPING: Dict[int, str] = None

    @staticmethod
    def item_type_oracle() -> Dict[int, str]:
        if NetStatSettings.__ITEM_TYPE_MAPPING is None:
            import abcnet.netstats_serialization
            NetStatSettings.__ITEM_TYPE_MAPPING = abcnet.netstats_serialization.default_item_types()
        return NetStatSettings.__ITEM_TYPE_MAPPING

    __ITEM_CONTENT_MAPPING: Dict[int, Callable[[bytes], Union[Dict, List, int, str]]] = None

    @staticmethod
    def item_packer_oracle() -> Dict[int,
                                        Callable[[bytes], Union[Dict, List, int, str]]]:
        if NetStatSettings.__ITEM_CONTENT_MAPPING is None:
            import abcnet.netstats_serialization
            NetStatSettings.__ITEM_CONTENT_MAPPING = abcnet.netstats_serialization.default_item_packer()
        return NetStatSettings.__ITEM_CONTENT_MAPPING

    @staticmethod
    def msg_serialization_filter(event: "LogEvent"):
        return True


class NetworkBackend:
    """
    Holds Network Backend settings.
    In std case, these settings shouldn't be touched.
    """

    _zmq_context = None
    """
    The context object used by the current process.
    """

    CONTEXT_INITIALIZER = _new_zmq_context

    MSG_POLLER_BUILDER: Callable[[List["zmq.Socket"], Callable[[zmq.Socket], bool]],
                                 Callable[[Optional[float]], Optional["abcnet.structures.Message"]]]
    MSG_POLLER_BUILDER = zmq_integration.build_zmq_poller

    @staticmethod
    def msg_poller(sockets: List["zmq.Socket"],
                   direct_socket_predicate: Callable[[zmq.Socket], bool]= lambda _:False) -> MsgPoller:
        return NetworkBackend.MSG_POLLER_BUILDER(sockets, direct_socket_predicate)

    @staticmethod
    def context() -> "zmq.Context":
        """
        Returns the cached context.
        Creates the context for the first invocation.
        :return:
        :rtype:
        """
        if NetworkBackend._zmq_context is None:
            NetworkBackend._set_context()
        return NetworkBackend._zmq_context

    @staticmethod
    def clean_up() -> None:
        if NetworkBackend._zmq_context is not None:
            NetworkBackend._zmq_context.destroy()

    @staticmethod
    def _set_context():
        """
        Creates a new network context.
        By default the zeroMQ context is used and cleaned up.

        Is replaced by simenv.MockedNetwork for simulation purposes.

        :return: Returns a fresh zeromq context.
        :rtype: zmq.Context
        """
        NetworkBackend.clean_up()
        NetworkBackend._zmq_context = NetworkBackend.CONTEXT_INITIALIZER()


def configure_logging(log_conf):
    """
    Configures the logging library given the log configuration file.
    """
    if isinstance(log_conf, dict):
        import logging.config
        logging.config.dictConfig(log_conf)
    elif isinstance(log_conf, str):
        if log_conf.endswith(".yaml"):
            import yaml
            with open(log_conf, 'r') as log_fp:
                configure_logging(yaml.safe_load(log_fp))
        else:
            import logging.config
            logging.config.fileConfig(log_conf, disable_existing_loggers=False)
    else:
        raise ValueError("Configuration unrecognized: " + str(log_conf))

def configure_test_logging():
    """
    Configures the logging library by the default test config file location.
    """
    configure_logging('log_conf/test_setting.yaml')

def configure_fast_test_network():
    """
    Configures the Peer settings for testing environment that ensures quick network topology formation.
    """
    PeerSetting.CLIQUE_PEER_SYNC_TIMEOUT = Units.ConstantTimeout(1)
    PeerSetting.CLIQUE_NEW_PEERS_SYNC_TIMEOUT = Units.ConstantTimeout(1.0)
    PeerSetting.CLIQUE_UNKNOWN_PEER_REQUEST_TIMEOUT = Units.ConstantTimeout(0.5)
    PeerSetting.CLIQUE_PEER_INTRODUCTION = Units.ConstantTimeout(0.5)
    PeerSetting.CLIQUE_RESOLVE_REQUESTED_TIMEOUT = Units.ConstantTimeout(0.5)

