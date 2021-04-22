import sqlite3
from datetime import datetime
from decimal import Decimal
import logging

from cryptography.hazmat.primitives._serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abccore.DAG import Wallet, Checkpoint
from tests.testUtil import TestUtility
import os.path
from abcckpt.checkpoint_db import ckpt_extract, ckpt_save, ckpt_init
import unittest


class TestDB(unittest.TestCase):
    def setUp(self) -> None:
        self.testutil = TestUtility()
        self.gen = self.testutil.get_sample_checkpoint()

    def test_checkpoint_gen(self):

        self.assertEqual(self.gen.origin, b'Genesis')
        self.assertEqual(self.gen.lock_time, self.testutil.time_stamp)
        self.assertEqual(self.gen.utxos, self.testutil.utxo)
        self.assertEqual(self.gen.nutxo, 4)
        self.assertEqual(self.gen.stake_dict, self.testutil.stake_dict)

        self.assertEqual(self.gen.total_coins, Decimal(100))
        self.assertEqual(self.gen.total_stake, Decimal(100))

    def test_create_extract_table(self):
        if os.path.isfile('checkpoint.db'):
            os.remove('checkpoint.db')
            logging.info("checkpoint.db deleted")

        ckpt_init()
        # todo read from file and insert genesis.

        p1 = "b45467f907401eb614e56a2920847e3900eb89559f66f39f822c0e42a938d261"
        p2 = "a3bf22d30bad4bf1fbfa42025ff15d46c8815f9e98c5d6fd5d3cbc72fd804d82"
        p3 = "3b32a3c4a5f30982be33f7f76e73e96e2798de729ffd8595772006cd807f329d"

        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p1))
        pub_key1 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p2))
        pub_key2 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p3))
        pub_key3 = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        time_stamp = datetime.utcnow().timestamp()
        utxo = [Wallet(pub_key1, Decimal(50), b'Genesis', 0),
                Wallet(pub_key2, Decimal(50), b'Genesis', 0),
                Wallet(pub_key3, Decimal(50), b'Genesis', 0)]

        stake_list = {pub_key1: Decimal(50), pub_key2: Decimal(50), pub_key3: Decimal(50)}

        gen = Checkpoint(b'Genesis', 0, time_stamp, length=3, utxos=utxo, stake_list=stake_list,
                         nutxo=3, outputs=[], tstake=Decimal(150), tcoins=Decimal(150),
                         miner=b'Genesis')
        ckpt_save(gen)
        if os.path.isfile('checkpoint.db'):
            logging.info("checkpoint.db creation successful")
            ckpt = ckpt_extract(0)
            self.assertEqual(ckpt.height, 0)
            logging.info("genesis creation successful!")
            #os.remove('checkpoint.db')
            logging.info("checkpoint.db deleted!")
        try:
            ckpt_save(gen)
        except sqlite3.IntegrityError as err:
            logging.info(str(err)+"DB already has checkpoint with identifier"+str(gen.id.hex()))


    def test_get_origin(self):
        self.assertEqual(b'Genesis', self.gen.get_origin())

    def test_get_locktime(self):
        self.assertEqual(self.testutil.time_stamp, self.gen.get_locktime())

    def test_get_acklength(self):
        self.assertEqual(10000, self.gen.get_acklength())

    def test_get_outputs(self):
        self.assertEqual(self.testutil.utxo, self.gen.get_utxos())

    def test_get_outputs_len(self):
        self.assertEqual(4, self.gen.get_outputs_len())

    def test_get_stake_list(self):
        self.assertEqual(self.testutil.stake_dict, self.gen.get_stake_list())

    def test_stake_sum(self):
        self.assertEqual(Decimal(100), self.gen.get_stake_sum())

    def test_get_total_coins(self):
        self.assertEqual(100, self.gen.get_total_coins())

    # def test_get_common_string(self):
    #     self.assertEqual(b'Genesis', self.gen.get_common_string())

    def test_save(self):
        if os.path.isfile('checkpoint.db'):
            os.remove('checkpoint.db')
            logging.info("checkpoint.db deleted")
        ckpt_save(self.gen)
        extracted_gen = ckpt_extract(self.gen.height)

        self.assertEqual(self.gen.total_stake, extracted_gen.total_stake)

        if os.path.isfile('checkpoint.db'):
            os.remove('checkpoint.db')
