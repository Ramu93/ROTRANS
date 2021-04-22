import json
import logging
import math
from typing import List, Tuple

from abccore import outputs_helper
from abccore.DAG import Wallet, Transaction, get_wallet_value, Decimal, Genesis, Checkpoint
from abccore.agent_crypto import auth_sign
from abccore.agent_service import AgentService
from abccore.network_datastructures import NetTransaction
from abcnet.handlers import MessageHandler
from abcnet.services import ChannelService, BaseApp
from abcnet.timer import StopTimer, SimpleTimer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from runtime.txnstats import TransactionConfirmationLogger

SPLIT_FACTOR = 1000

logger = logging.getLogger(__name__)

class TxnSpammer(MessageHandler):

    def __init__(self, txn_conf_logger: TransactionConfirmationLogger, agent_service: AgentService, keys: List[Tuple[Ed25519PrivateKey, bytes]],
                 txn_creation_rate: float):
        self.txn_conf_logger = txn_conf_logger
        self.agent_service = agent_service
        self.keys = keys
        self.txn_creation_rate = txn_creation_rate
        self.txn_creation_time = 1.0 / txn_creation_rate

        self.late_start = SimpleTimer(4, start=True)
        self.output_gen_phase = True
        self.utxo: List[Wallet] = list()
        self.pending_utxo: List[Wallet] = list()

        self.output_wait_phase = False

        self.last_creation_time: StopTimer = None
        self.spam_phase = False

        self.out_queue: List[Tuple[NetTransaction, int]] = list()
        self.broadcast_time = SimpleTimer(2, start=True)

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        if not self.late_start.check():
            return
        if self.output_gen_phase:
            self.gen_splits(cs)
        elif self.output_wait_phase:
            self.check_splits()
        elif self.spam_phase:
            self.spam(cs)
            self.check_utxo_confirmed()

        if self.broadcast_time() and self.out_queue:
            items = list(map(lambda o: o[0], self.out_queue))
            cs.broadcast_channel().items(items)
            self.out_queue = list(map(lambda o: (o[0], o[1] -1), self.out_queue))
            self.out_queue = list(filter(lambda o: o[1] > 0, self.out_queue))

    def gen_splits(self, cs: ChannelService):
        for node in self.agent_service.get_DAG().get_all():
            if not isinstance(node, Genesis) or isinstance(node, Checkpoint):
                continue
            node: Genesis
            outputs: List[Wallet] = node.outputs
            for o in outputs:
                self.split_wallet(cs, [o])

    def split_wallet(self, cs, outputs: List[Wallet]):
        new_outs: List[Wallet] = list()
        for old_out in outputs:
            new_out_val = Decimal((Decimal(0.99) * get_wallet_value([old_out])) / SPLIT_FACTOR)
            for o in range(SPLIT_FACTOR):
                new_outs.append(Wallet(old_out.get_pk(), new_out_val))
        outputs_helper.outputs_helper(outputs, new_outs)
        self.release_txn(cs, Transaction(outputs, new_outs, old_out.get_pk()))
        self.output_gen_phase = False
        self.output_wait_phase = True

    def check_utxo_confirmed(self):
        new_pending_utxo = list()
        for wallet in self.pending_utxo:
            is_confirmed = self.agent_service.get_DAG().search(wallet.get_origin()) is not None
            if not is_confirmed:
                new_pending_utxo.append(wallet)
            else:
                self.utxo.append(wallet)
        self.pending_utxo = new_pending_utxo

    def check_splits(self):
        self.check_utxo_confirmed()
        if len(self.pending_utxo) == 0:
            self.output_wait_phase = False
            self.spam_phase = True

    def spam(self, cs: ChannelService):
        if self.last_creation_time is None:
            self.last_creation_time = StopTimer()
            return

        txn_to_be_made = math.floor(self.last_creation_time.time() * self.txn_creation_rate)
        # logger.info("Spamming %s many txn.", txn_to_be_made)
        txn_to_be_made = min(txn_to_be_made, 400)
        txn_created = False
        if txn_to_be_made > 0:
            for i in range(txn_to_be_made):
                txn_created = self.generate_txn(cs)
                if not txn_created:
                    break
            logger.warning("Spammed txns: %s/%s", i+1, txn_to_be_made)
            if txn_created:
                self.last_creation_time.reset()

    def generate_txn(self, cs: ChannelService):
        if len(self.utxo) == 0:
            return False
        wallet = self.utxo.pop(0)
        new_outs = []
        outputs_helper.outputs_helper([wallet], new_outs)
        txn = Transaction([wallet], new_outs, wallet.get_pk())
        self.release_txn(cs, txn)
        return True

    def release_txn(self, cs, txn):
        self.pending_utxo.extend(txn.outputs)
        self.sign_txn(txn)
        self.txn_conf_logger.register_txn(txn.get_identifier())
        netTxn = NetTransaction(transaction=txn)
        self.out_queue.append((netTxn, 2))
        return True

    def sign_txn(self, txn: Transaction):
        signed = set()
        for input in txn.inputs:
            input: Wallet
            for private_key, pb_key in self.keys:
                if pb_key == input.get_pk() and pb_key not in signed:
                    signature = auth_sign(txn.get_identifier(), private_key)
                    txn.add_signature(signature)
                    signed.add(pb_key)
        return txn



def activate_spammer(ba: BaseApp, txn_conf_logger: TransactionConfirmationLogger, agent_service: AgentService,
                 txn_creation_rate: float):
    keys = list()
    with open('generated_keys.json') as fp:
        loaded_keys = json.load(fp)
        for k in loaded_keys['private_keys']:
            keyhex = k['key']
            from abccore.agent_crypto import pub_key_to_bytes, parse_from_bytes
            keypriv = parse_from_bytes(bytes.fromhex(keyhex))
            pub_key = pub_key_to_bytes(keypriv.public_key())
            keys.append((keypriv, pub_key))
    assert len(keys) == 10
    spammer = TxnSpammer(txn_conf_logger, agent_service, keys, txn_creation_rate)
    ba.register_app_layer("TXNSPAMMER", spammer)
