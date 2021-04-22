import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


NUM = 10  # Number of wanted genesis keys


def gen_genesis_keys():
    """
    Generates NUM many random private keys for genesis usage and saves them in a json file.
    """
    keys = []
    for i in range(0, NUM):
        keys.append(Ed25519PrivateKey.generate())

    s = "------------GENESIS PRIVATE KEYS------------ \n"
    js = {}
    js["private_keys"] = []
    js["public_keys"] = []

    for i in range(0, len(keys)):
        private_key_bytes = keys[i].private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )

        public_key_bytes = (
            keys[i]
            .public_key()
            .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
        )
        s += private_key_bytes.hex() + "\n"  # reverse: bytes.fromhex('abc')
        js["private_keys"].append({"id": str(i), "key": private_key_bytes.hex()})
        js["public_keys"].append({"id": str(i), "key": public_key_bytes.hex()})

        # sk = Ed25519PrivateKey.from_private_bytes(private_key_bytes)

    with open("generated_test_keys.json", "w") as outfile:
        json.dump(js, outfile)


def print_genesis_keys():
    """
    Prints the content of the 'generated_keys.json' file
    """
    with open("generated_keys.json") as json_file:
        data = json.load(json_file)
        print("Private Keys:")
        for k in data["private_keys"]:
            print(k["id"] + ": " + k["key"])

        print("\n Corresponding Public Keys:")
        for k in data["public_keys"]:
            print(k["id"] + ": " + k["key"])


def print_test_keys():
    """
    Prints the content of the 'generated_keys.json' file
    """
    with open("generated_test_keys.json") as json_file:
        data = json.load(json_file)
        print("Private Keys:")
        for k in data["private_keys"]:
            print(k["id"] + ": " + k["key"])

        print("\n Corresponding Public Keys:")
        for k in data["public_keys"]:
            print(k["id"] + ": " + k["key"])


def load_genesis_keys() -> [Ed25519PrivateKey]:
    """
    Loads all keys included in the 'generated_keys.json' and returns a list of Ed25519PrivateKey keys.
    :return: List of Ed25519PrivateKeys
    """
    with open("generated_keys.json") as json_file:
        data = json.load(json_file)

    keys = []
    for k in data["private_keys"]:
        keys.append(Ed25519PrivateKey.from_private_bytes(bytes.fromhex(k["key"])))

    return keys


gen_genesis_keys()  # !!!! ONLY EXECUTE IF YOU WANT TO OVERWRITE THE CURRENT GENESIS KEYS
print_test_keys()
