import unittest
import random

from abccore.agent_crypto import *
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


class TestCrypto(unittest.TestCase):
    def test_hash_bytes(self):
        h = rnd_hex().split("x")[1]
        if len(h) % 2 == 1:
            h = "0" + h
        b = bytes.fromhex(h)
        assert hash_bytes(b)

    def test_gen_key(self):
        assert gen_key()

    def test_pub_key_bytes(self):
        key: Ed25519PrivateKey = gen_key()
        pub_bytes: bytes = pub_key_to_bytes(key.public_key())
        assert pub_bytes == key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        pk1 = pub_key_from_bytes(pub_bytes)
        pk2 = key.public_key()
        assert pub_key_to_bytes(pk1) == pub_key_to_bytes(pk2)

    def test_priv_key_bytes(self):
        key: Ed25519PrivateKey = gen_key()
        priv_bytes: bytes = parse_to_bytes(key)
        assert priv_bytes == key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        sk1 = parse_from_bytes(priv_bytes)
        assert parse_to_bytes(sk1) == parse_to_bytes(key)

    def test_sign_validate(self):
        h = rnd_hex().split("x")[1]
        if len(h) % 2 == 1:
            h = "0" + h
        data = bytes.fromhex(h)
        key = gen_key()

        signature = auth_sign(data, key)
        assert auth_validate(data, signature)


def rnd_hex(minint=99999, maxint=99999999) -> str:
    return hex(random.randint(int(minint), int(maxint)))
