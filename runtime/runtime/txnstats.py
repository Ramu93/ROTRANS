import csv
from datetime import datetime
import logging
import pathlib
import time
from typing import Dict, Set, Tuple, List, TextIO

from abccore.DAG import Transaction, Decimal, Acknowledge
from abccore.agent import Agent
from abccore.agent_items_parser import AgentItemsParser
from abccore.checkpoint_service import CheckpointService
from abccore.network_datastructures import NetAcknowledgement
from abcnet import transcriber
from abcnet.handlers import MessageHandler
from abcnet.netstats import LogEvent, NetworkMessagesStats, StatsReaders, MsgEvent, StatsCollectorInterceptorMD, \
    InboundMsgStatCollector
from abcnet.netstats_serialization import format_time
from abcnet.services import ChannelService, BaseApp
from abcnet.settings import NetStatSettings
from abcnet.structures import MsgType, ItemType, Message
from abcnet.timer import StopTimer, SimpleTimer

logger = logging.getLogger(__name__)


class TransactionRecord(LogEvent):

    def __init__(self, transaction: bytes, confirmed: bool, creation_time: float, timestamp: float = None):
        super().__init__(timestamp)
        self.txn: bytes = transaction
        self.confirmed: bool = confirmed
        self.created: bool = not confirmed
        self.creation_time = creation_time


class TransactionConfirmationLogger(MessageHandler):

    pending_txns: Dict[bytes, Tuple[Decimal, Set[bytes], float]]

    confirmed_txn: Set[bytes]

    parser: AgentItemsParser = AgentItemsParser()

    def __init__(self, ckpt_service: CheckpointService,
                 collector: "TransactionStatsCollector"):
        self.pending_txns = dict()
        self.confirmed_txn = set()
        self.ckpt_service = ckpt_service
        self.outstanding_report = SimpleTimer(10, start=True)
        self.collector = collector

    def register_txn(self, txn: bytes):
        self.pending_txns[txn] = (Decimal(0.0), set(), time.time())

    def confirm_txn(self, txn: bytes):
        self.confirmed_txn.add(txn)
        record = TransactionRecord(txn, confirmed=True, creation_time=self.pending_txns[txn][2])
        self.collector.enqueue(record)

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        if self.outstanding_report():
            logger.warning("Pending transactions: %s/%s", len(self.pending_txns) - len(self.confirmed_txn),
                           len(self.pending_txns))

    def accept(self, cs: "ChannelService", msg: Message) -> None:
        self.eval_msg(msg)

    def eval_msg(self, msg: Message):
        m_type = transcriber.parse_message_type(msg)
        if m_type != MsgType.items_content:
            return
        items = transcriber.parse_item_contents(msg)
        for item_type, item_content in items:
            self.eval_item(item_type, item_content)

    def eval_item(self, item_type: int, item_content: bytes):
        if item_type != ItemType.ACK:
            return
        na: NetAcknowledgement = self.parser.decode_item_bytes(item_type, item_content)
        ack: Acknowledge = na.ack
        self.eval_ack(ack)

    def eval_ack(self, ack: Acknowledge):
        if ack.get_trans_id() in self.confirmed_txn:
            return
        if not ack.get_trans_id() in self.pending_txns:
            logger.error("Txn id not found: %s", ack.get_trans_id().hex(), exc_info=True)
            return
        stake, acks, creation_time = self.pending_txns[ack.get_trans_id()]
        if ack.get_identifier() in acks:
            return
        stake += self.ckpt_service.delegated_stake(ack.get_pb_key())
        acks.add(ack.get_identifier())
        if stake > (self.ckpt_service.stake_sum() * (Decimal(2) / Decimal(3))):
            self.confirm_txn(ack.get_trans_id())
        self.pending_txns[ack.get_trans_id()] = (stake, acks, creation_time)


class TransactionLatency(LogEvent):

    def __init__(self, latency: float, timestamp: float = None):
        super().__init__(timestamp)
        self.latency: float = latency

class TransactionThroughput(LogEvent):

    def __init__(self, number_txn: int, time_span: float, timestamp: float = None):
        super().__init__(timestamp)
        self.number_txn = number_txn
        self.time_span = time_span
        self.throughput = float(number_txn) / time_span

class TransactionStatsCollector(MessageHandler):

    txn_latencies: List[TransactionLatency]

    txn_throughput: List[TransactionThroughput]

    last_through_put_time: StopTimer

    events_check_timeout: SimpleTimer

    def __init__(self, stat_dir: pathlib.PurePath):
        # self.stats_reader.register_reader("TXN")
        self.txn_latencies = list()
        self.txn_throughput = list()
        self.events_check_timeout = SimpleTimer(10.0, start=True)
        self.last_through_put_time = StopTimer()
        self.stat_dir = stat_dir
        self.stats_dump_time = SimpleTimer(30.0, start=True)
        self.queue: List[TransactionRecord] = list()

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        if self.events_check_timeout() or force_maintenance:
            self.crawl_transaction_records()
        if self.stats_dump_time() or force_maintenance:
            self.dump_stats()

    def crawl_transaction_records(self):
        time_span = self.last_through_put_time.time()
        confirmed_txn_count = 0
        for event in self.queue:
            if isinstance(event, TransactionRecord):
                if not event.confirmed:
                    continue
                tl = TransactionLatency(event.timestamp - event.creation_time)
                self.txn_latencies.append(tl)
                confirmed_txn_count += 1
        self.queue.clear()
        self.txn_throughput.append(TransactionThroughput(confirmed_txn_count, time_span))
        self.last_through_put_time.reset()

    @staticmethod
    def throughput_to_row(tp: TransactionThroughput):
        return [
            format_time(tp.timestamp),
            tp.timestamp,
            tp.number_txn,
            tp.time_span,
            tp.throughput
        ]

    @staticmethod
    def latency_to_row(tl: TransactionLatency):
        return [
            format_time(tl.timestamp),
            tl.timestamp,
            tl.latency,
        ]

    def dump_stats(self):
        with self.serialization_target_file_pointer("txn_thoughtput") as fp:
            writer = csv.writer(fp)
            writer.writerow(["Time", "Timestamp", "Confirmed txn count (txn)", "Timespan (sec)", "Average throughput (txn/sec)"])
            writer.writerows(list(
                map(
                    self.throughput_to_row,
                    self.txn_throughput
                )
            ))

        with self.serialization_target_file_pointer("txn_latencies") as fp:
            writer = csv.writer(fp)
            writer.writerow(["Time", "Timestamp", "Txn latency (sec)"])
            writer.writerows(list(
                map(
                    self.latency_to_row,
                    self.txn_latencies
                )
            ))

    def serialization_target_file_pointer(self, stat_name: str) -> TextIO:
        file_name = stat_name + ".csv"
        return pathlib.Path(self.stat_dir / file_name).open('w', newline='')

    def enqueue(self, record):
        self.queue.append(record)


def enable_statistics(ba: BaseApp, checkpoint_service: CheckpointService, stat_dir: pathlib.PurePath = None)\
        -> TransactionConfirmationLogger:
    if stat_dir is None:
        dirname = NetStatSettings.STAT_SERIALIZATION_DIR
        if NetStatSettings.STAT_SERIALIZATION_DATE_TIME_SUB_DIR:
            date_time = datetime.today().strftime('%Y-%m-%d--%H,%M,%S')
            stat_dir = pathlib.PurePath(".") / dirname / date_time
        else:
            stat_dir = pathlib.PurePath(".") / dirname
    try:
        pathlib.Path(stat_dir).mkdir(parents=True)
    except FileExistsError:
        pass

    txn_stats = TransactionStatsCollector(stat_dir)
    ba.register_app_layer("TxnStats", txn_stats)
    txn_confirm = TransactionConfirmationLogger(checkpoint_service, txn_stats)
    ba.register_app_layer("TxnConfirm", txn_confirm)

    logger.info("Enabled txn stat. Stat directory: %s", stat_dir)

    return txn_confirm
