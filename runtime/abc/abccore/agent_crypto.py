from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization, hashes
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


def gen_key() -> Ed25519PrivateKey:
    """
    Function to generate a (random) private key for EdDSA of the 'cryptography' library
    :return: generated EdDSA private key
    """
    return Ed25519PrivateKey.generate()


def pub_key_to_bytes(key: Ed25519PublicKey) -> bytes:
    """
    Function to transform a public key for EdDSA of the 'cryptography' library to a bytestring
    :param key: Ed25519PublicKey of the 'cryptography' library
    :return: input public key transformed to bytes
    """
    return key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def pub_key_from_bytes(key: bytes) -> Ed25519PublicKey:
    """
    Function to transform a bytestring to a public key for EdDSA of the 'cryptography' library
    :param key: bytestring
    :return: input bytes transformed to a public EdDSA key
    """
    return Ed25519PublicKey.from_public_bytes(key)


def parse_to_bytes(key: Ed25519PrivateKey, password=None):
    """
    Function to transform a private key for EdDSA of the 'cryptography' library to a bytestring
    :param key: Ed25519PrivateKey of the 'cryptography' library
    :param password: password to encrypt the resulting bytestring
    :return: input private key transformed to bytes
    """
    # TODO: PASSWORD!
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def parse_from_bytes(key_bytes: bytes, password=None):
    """
    Function to transform a bytestring to a private key for EdDSA of the 'cryptography' library
    :param key: bytestring
    :param password: password to decrypt the input bytestring
    :return: input bytes transformed to a public EdDSA key
    """
    # TODO: PASSWORD?
    return Ed25519PrivateKey.from_private_bytes(key_bytes)


def auth_sign(data, key: Ed25519PrivateKey):
    """
    Function to create a signature for the given data with help of the given key
    :param data: the underlying data we want to create the signature for
    :param key: key for signature creation
    :return: signature of the data created with help of the input key
    """
    signature = (
        key.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw),
        key.sign(data),
    )
    return signature


def auth_validate(data, signature) -> bool:
    """
    Function to validate wether or not a signature matches the given data
    :param data: the underlying data of the signature
    :param signature: signature of the corresponding data which shell be validated
    :return: boolean wether or not the validation was successfull
    """
    try:
        signature_bytes: bytes = signature[1]
        key: bytes = signature[0]
        key_object = Ed25519PublicKey.from_public_bytes(key)
        key_object.verify(signature_bytes, data)
        return True
    except InvalidSignature:
        return False


def hash_bytes(byte_string: bytes) -> bytes:
    """
    Function to create a hash from a bytestring
    :param byte_string: bytes which shell be hashed
    :return: hash of input bytes
    """
    digest = hashes.Hash(hashes.SHA512_256())
    digest.update(byte_string)
    return digest.finalize()
