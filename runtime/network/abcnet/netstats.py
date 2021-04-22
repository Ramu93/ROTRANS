import logging
from datetime import datetime
from typing import List, Dict, Iterable, TextIO

from yaml import dump

from abcnet.netstats_serialization import format_time
from abcnet.transcriber import msg_network_bytes

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    print("Cannot import")
    from yaml import Loader, Dumper

import time
import pathlib

from abcnet import transcriber
from abcnet.handlers import MessageHandler
from abcnet.networking import MessageDissemination
from abcnet.outch import MsgSender
from abcnet.services import ChannelService, BaseApp
from abcnet.structures import Message, Qualifier, MsgType
from abcnet.settings import NetStatSettings

logger = logging.getLogger(__name__)


class LogEvent:

    timestamp: float

    def __init__(self, timestamp: float = None, **kwargs):
        if timestamp is None:
            timestamp = time.time()
        self.timestamp = timestamp


class MsgEvent(LogEvent):

    msg_bytes: bytes
    out_msg: bool
    direct_msg: bool

    def __init__(self, msg_bytes: bytes, out_msg: bool, direct_msg: bool, timestamp: float = None):
        super(MsgEvent, self).__init__(timestamp=timestamp)
        self.msg_bytes = msg_bytes
        self.out_msg = out_msg
        self.direct_msg = direct_msg


class NetworkMessagesStats:

    events: List[LogEvent]

    reader: "StatsReaders"

    def __init__(self):
        self.events = list()

    def push_event(self, log_event:LogEvent):
        self.events.append(log_event)

    def del_event(self, delete_range):
        del self.events[:delete_range]

    def has_event(self, index):
        if index < 0:
            return False
        return len(self.events) > index

    def get_event(self, index) -> LogEvent:
        return self.events[index]


class StatsReaders:

    stats: NetworkMessagesStats

    reader_positions: Dict[str, int]

    def __init__(self, stats: NetworkMessagesStats):
        self.reader_positions = dict()
        self.stats = stats

    def register_reader(self, reader_name: str):
        if reader_name in self.reader_positions:
            raise ValueError(f"Reader {reader_name} is already registered.")
        self.reader_positions[reader_name] = 0

    def read(self, reader_name: str) -> Iterable[LogEvent]:
        rp = self.reader_positions[reader_name]
        while self.stats.has_event(rp):
            yield self.stats.get_event(rp)
            rp += 1
        self.reader_positions[reader_name] = rp
        # No more stats
        self._clear_events()
        return None

    def _clear_events(self):
        min_reader_pos = min(self.reader_positions.values())
        if min_reader_pos >= NetStatSettings.EVENT_DELETE_BATCH_SIZE:
            self.stats.del_event(min_reader_pos)
            for reader in self.reader_positions.keys():
                self.reader_positions[reader] = self.reader_positions[reader] - NetStatSettings.EVENT_DELETE_BATCH_SIZE


class OutboundMsgStatCollector(MsgSender):

    _stats: NetworkMessagesStats
    _intercepted_sender: MsgSender

    def __init__(self, stats: NetworkMessagesStats, intercepted_sender: MsgSender, direct_msg: bool):
        self._stats = stats
        self._intercepted_sender = intercepted_sender
        self._direct_msg = direct_msg

    def _send(self, msg: Message, do_log=True):
        self._stats.push_event(MsgEvent(msg_bytes=msg_network_bytes(msg), out_msg=True, direct_msg=self._direct_msg))
        self._intercepted_sender._send(msg)


class StatsCollectorInterceptorMD(MessageDissemination):

    _intercepted_md: MessageDissemination

    def __init__(self, stats: NetworkMessagesStats, md: MessageDissemination):
        self._intercepted_md = md
        self.stats = stats

    def broadcast(self) -> MsgSender:
        return OutboundMsgStatCollector(self.stats, self._intercepted_md.broadcast(), direct_msg=False)

    def direct(self, peer: Qualifier) -> MsgSender:
        return OutboundMsgStatCollector(self.stats, self._intercepted_md.direct(peer), direct_msg=True)


class InboundMsgStatCollector(MessageHandler):

    _stats: NetworkMessagesStats

    def __init__(self, stats: NetworkMessagesStats):
        self._stats = stats

    def accept(self, cs: ChannelService, msg: Message):
        self._stats.push_event(MsgEvent(msg_bytes=msg_network_bytes(msg), out_msg=False, direct_msg=False))


class StatsSerializer(MessageHandler):

    def __init__(self, stats_reader: StatsReaders, stat_dir: pathlib.PurePath):
        self.stats_reader: StatsReaders = stats_reader
        self.reader_name = f"Serializer{self.serialized_file_name()}(stat_dir={stat_dir})"
        self.stats_reader.register_reader(reader_name=self.reader_name)
        self.stat_dir = stat_dir
        self.serialization_timer = NetStatSettings.STAT_SERIALIZATION_TIMER.stop_timer(start=True)

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        if self.serialization_timer():
            self.serialize_stats()

    def close(self):
        self.serialize_stats()

    def serialize_stats(self):
        logger.debug("Serializing stats...")
        self.serialize_events_to_file()

    def serialized_file_name(self):
        raise NotImplemented

    def serialization_target_file_pointer(self) -> TextIO:
        file_name = self.serialized_file_name() + NetStatSettings.STAT_SERIALIZATION_FILE_ENDING
        return pathlib.Path(self.stat_dir / file_name).open(mode='a', encoding='utf-8')

    def serialize_events_to_file(self):
        with self.serialization_target_file_pointer() as fp:

            def write(line=None, lines=[], flush=False):
                if line:
                    lines.append(line)
                if flush or len(lines) >= NetStatSettings.MEM_LINE_CHUNKS:
                    fp.writelines(lines)
                    lines.clear()

            def write_sep():
                write(line=NetStatSettings.STAT_SERIALIZATION_EVENT_SEP)

            for event in self.stats_reader.read(self.reader_name):
                if not NetStatSettings.msg_serialization_filter(event):
                    continue
                try:
                    line: str = self.serialize_msg_event(event)
                    if line is not None:
                        write(line=line)
                        write_sep()
                except Exception as e:
                    logger.error("Trying to serialize event %s caused an error.", event, exc_info=True)

            write(flush=True)

    def serialize_msg_event(self, event: LogEvent):
        raise NotImplemented


class MsgSerializer(StatsSerializer):

    def __init__(self, stats_reader: StatsReaders, stat_dir: pathlib.PurePath):
        super().__init__(stats_reader, stat_dir)

    def serialized_file_name(self):
        return "messages"

    def serialize_msg_event(self, event: MsgEvent):
        if not isinstance(event, MsgEvent):
            return None
        obj = self.pack_msg_event(event)
        line: str = dump([obj], Dumper=Dumper)
        return line

    @staticmethod
    def pack_msg_event(event: MsgEvent) -> Dict:
        o = dict()
        o['datetime'] = format_time(event.timestamp)
        o['direction'] = "OUT" if event.out_msg else "IN"
        o['target'] = "DIRECT" if event.direct_msg else "BROADCAST"
        m = transcriber.msg_from_network_bytes(event.msg_bytes)
        m_type = MsgType(transcriber.parse_message_type(m))
        o['MsgType'] = str(m_type)
        sender = transcriber.parse_sender(m)
        o['sender'] = sender
        packer_oracle = NetStatSettings.MSG_PACKER_ORACLE()
        packer = packer_oracle.get(m_type, None)
        if packer is not None:
            o['Content'] = packer(m)

        return o


def enable_statistics(ba: BaseApp, stat_dir: pathlib.PurePath = None) -> NetworkMessagesStats:
    if stat_dir is None:
        dirname = NetStatSettings.STAT_SERIALIZATION_DIR
        if NetStatSettings.STAT_SERIALIZATION_DATE_TIME_SUB_DIR:
            date_time = datetime.today().strftime('%Y-%m-%d--%H,%M,%S')
            stat_dir = pathlib.PurePath(".") / dirname / date_time / ba.cs.contact.identifier
        else:
            stat_dir = pathlib.PurePath(".") / dirname / ba.cs.contact.identifier
    try:
        pathlib.Path(stat_dir).mkdir(parents=True)
    except FileExistsError:
        pass
    stats = NetworkMessagesStats()
    stats_reader = StatsReaders(stats)
    stats.reader = stats_reader
    cs: ChannelService = ba.cs
    cs._ChannelService__md = StatsCollectorInterceptorMD(stats, cs._ChannelService__md)
    inbound_collector = InboundMsgStatCollector(stats)
    ba.register_app_layer("InboundMsgStatCollector", inbound_collector)
    msgserializer = MsgSerializer(stats_reader, stat_dir)
    ba.register_app_layer("MsgSerializer", msgserializer)
    logger.info("Enabled network stat logging for peer %s. Stat directory: %s", ba.cs.contact, stat_dir)
    return stats
