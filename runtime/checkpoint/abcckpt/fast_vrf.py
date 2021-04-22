import decimal
from decimal import Decimal
from typing import Tuple, Union, Dict, Optional

import random
import secrets
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

import json

hash_bytes_size = 32
float_bytes_size = 4

VRF_SAMPLE_CONTEXT = decimal.Context(prec=6, rounding=decimal.ROUND_DOWN)

def create_hash(text: bytes) -> bytes:
    digest = hashes.Hash(hashes.SHA512_256())
    digest.update(text)
    return digest.finalize()


def hash_to_sample(hash_bytes: bytes) -> Decimal:
    if hash_bytes is None or len(hash_bytes) != hash_bytes_size:
        raise ValueError(f"Hash is malformed. Requiring a {hash_bytes_size} length bytes object.")
    ctx_copy = decimal.getcontext()
    decimal.setcontext(VRF_SAMPLE_CONTEXT)
    try:
        hash_nr = Decimal(int.from_bytes(hash_bytes, 'big'))
        max_nr = Decimal(2**(hash_bytes_size * 8))
        sample = hash_nr / max_nr
        sample_quantized = sample.quantize(Decimal('1.0000'), rounding=decimal.ROUND_DOWN)
    finally:
        decimal.setcontext(ctx_copy)
    return sample_quantized


def gen_key(seed: Optional[Union[str, bytes, int]] = None) -> Ed25519PrivateKey:
    if seed is None:
        key_bytes = secrets.token_bytes(32)
    else:
        prng = random.Random(seed)
        key_bytes = bytearray(prng.getrandbits(8) for _ in range(32))
    return Ed25519PrivateKey.from_private_bytes(key_bytes)



def encode_sec_key(sk: Ed25519PrivateKey) -> bytes:
    secret_key = sk.private_bytes(encoding=serialization.Encoding.Raw,
                                       format=serialization.PrivateFormat.Raw,
                                       encryption_algorithm=serialization.NoEncryption())
    return secret_key

def decode_sec_key(sk_bytes: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(sk_bytes)


def sign_hash(hash_bytes: bytes, pv_key: Ed25519PrivateKey) -> bytes:
    return pv_key.sign(hash_bytes)


def decode_pub_key(pub_key_bytes: bytes) -> Ed25519PublicKey:
    key_object = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
    return key_object


def encode_pub_key(pub_key: Ed25519PublicKey) -> bytes:
    encoding: Encoding = Encoding('Raw')
    format_: PublicFormat = PublicFormat('Raw')
    pb_key_bytes = pub_key.public_bytes(encoding, format_)
    # return int.from_bytes(pb_key_bytes, 'big')
    return pb_key_bytes

def encode_sample(sample: Decimal) -> bytes:
    return str(sample).encode("utf-8")

def decode_sample(sample:bytes) -> Decimal:
    return Decimal(sample.decode('utf-8'))

def validate_signature(hash_bytes: bytes, signature: bytes, pub_key: Ed25519PublicKey):
    pub_key.verify(signature, hash_bytes)

def decode_and_validate_signature(hash_bytes: bytes, signature: bytes, pub_key_bytes: bytes) -> bool:
    try:
        pb_key = decode_pub_key(pub_key_bytes)
        validate_signature(hash_bytes, signature, pb_key)
        return True
    except InvalidSignature:
        return False
    except ValueError:
        return False

def append_pub_key_to_alpha(alpha_string: str, key: Union[bytes, Ed25519PublicKey, Ed25519PrivateKey]) -> bytes:
    if key is None:
        raise ValueError()
    if isinstance(key, Ed25519PrivateKey):
        key = key.public_key()
    if isinstance(key, Ed25519PublicKey):
        key = encode_pub_key(key)
    if not isinstance(key, bytes):
        raise ValueError("Unrecognized key: " + str(key))
    key_hex = key.hex()
    return json.dumps([alpha_string, key_hex]).encode('utf-8')

def hash_vrf_prove(sk: Union[bytes, Ed25519PrivateKey], alpha_string: bytes, raise_exception=False)-> Tuple[str, bytes]:
    """
    Input:
        sk - private key
        alpha_string - input alpha, the common string.
        raise_exception - if True, raises exception instead of returning INVALID
    Output:
        pi_string - VRF proof
    """
    try:
        if isinstance(sk, bytes):
            sk = decode_sec_key(sk)
        if not isinstance(sk, Ed25519PrivateKey):
            raise ValueError(f"Unrecognized secret key object: {sk}")
        pub_k = sk.public_key()
        pub_k_bytes = encode_pub_key(pub_k)
        alpha_string_bytes = alpha_string.hex()
        alpha_string_pub_key = append_pub_key_to_alpha(alpha_string_bytes, pub_k_bytes)
        alpha_hash = create_hash(alpha_string_pub_key)
        signature = sign_hash(alpha_hash, sk)
        signature_hex = signature.hex()
        proof: Dict[str, str] = {
            "hash": alpha_hash.hex(),
            "sign": signature_hex
        }
        return 'VALID', json.dumps(proof).encode('utf-8')
    except Exception as e:
        if raise_exception:
            raise e
        return 'INVALID', bytes()


def hash_vrf_proof_to_hash(pi_string: bytes, raise_exception=False) -> Tuple[str, Decimal]:
    """
    Input:
        pi_string - VRF proof output
        raise_exception - if True, raises exception instead of returning INVALID
    Output:
        status - VALID or INVALID
        sample - The randomly drawn sample from 0.0 (inclusive) to 1.0 (exclusive).
    """
    try:
        proof = json.loads(pi_string.decode('utf-8'))
        alpha_hash: bytes = bytes.fromhex(proof['hash'])
        sample = hash_to_sample(alpha_hash)
        return 'VALID', sample
    except Exception as e:
        if raise_exception:
            raise e
        return 'INVALID', Decimal()


def hash_vrf_verify(pub_k_bytes: bytes, pi_string: bytes, alpha_string: bytes, raise_exception=False) \
        -> Tuple[str, Decimal]:
    """
    Input:
        pub_k_bytes - public key bytes
        pi_string - VRF proof output, which is validated.
        alpha_string - the common string
        raise_exception - if True, raises exception instead of returning INVALID
    Output:
        status - VALID or INVALID
        sample - The randomly drawn sample from 0.0 (inclusive) to 1.0 (exclusive).
    """
    try:
        # Decode the pi string:
        proof: Dict[str, str] = json.loads(pi_string.decode('utf-8'))
        proof_sign = proof['sign']
        given_hash: bytes = bytes.fromhex(proof['hash'])
        signature_bytes = bytes.fromhex(proof_sign)

        # Recalculate the hash:
        alpha_string_bytes = alpha_string.hex()
        alpha_string_pub_key = append_pub_key_to_alpha(alpha_string_bytes, pub_k_bytes)
        alpha_hash = create_hash(alpha_string_pub_key)

        # Verify the hashes match
        if alpha_hash != given_hash:
            raise ValueError("The proof doesn't match the given alpha_string")

        # Validate signature:
        decode_and_validate_signature(alpha_hash, signature_bytes, pub_k_bytes)

        # Encode sample
        sample: Decimal = hash_to_sample(alpha_hash)
        return 'VALID', sample
    except Exception as e:
        if raise_exception:
            raise e
        return 'INVALID', Decimal()
