from abcnet.transcriber import ItemsParser, Parser
from abcnet.structures import ItemType
from abcnet import transcriber
from typing import Any, List
from decimal import Decimal, Context, ROUND_HALF_DOWN

from abccore.DAG import Wallet, Transaction, Acknowledge, Node
from abccore.network_datastructures import NetTransaction, NetAcknowledgement, NetUSPWR


def decode_signature(parser: Parser) -> (bytes, bytes):
    """
    Decodes a single signature of the parser and returns the bytevalues.
    :param parser: The parser which holds the related bytestring which shall be decoded
    :return: Bytes tuple representation of a signature
    """

    pk = parser.consume_nested_bytes()
    if pk == bytes():
        pk = None
    sig = parser.consume_nested_bytes()
    if sig == bytes():
        sig = None

    if pk is None or sig is None:
        return None

    return (pk, sig)


def decode_wallet(parser: Parser) -> List[Wallet]:
    """
    Decodes all outputs (or inputs) of a wallet from the parser.
    :param parser: The parser which holds the related bytestring which shall be decoded
    :return: List of wallets
    """
    length = parser.consume_int()

    wallets = []

    for i in range(0, length):
        s = str(parser.consume_nested_text())
        value = Decimal(s)
        own_key = parser.consume_nested_bytes()
        origin = parser.consume_nested_bytes()
        id = parser.consume_int()
        wallets.append(Wallet(own_key, value, origin, id))

    return wallets


class AgentItemsParser(ItemsParser):
    """
    Class for decoding and parsing items related to the abccore from the network.
    """

    def decode_item(self, item_type: int, parser: Parser) -> Any:
        """
        Method to actually decode bytestring from the network to useable data.
        :param item_type: The type of the data as in abcnet.structures.ItemType
        :param parser: The parser used for decoding
        :return: A network compatible datatype as defined in abccore.network_datastructures, namely NetTransaction, NetAcknowledgement or NetUSPWR
        """
        if item_type == ItemType.TXN:
            identifier = parser.consume_nested_bytes()
            inputs = decode_wallet(parser)
            outputs = decode_wallet(parser)
            validator_key = parser.consume_nested_bytes()
            if validator_key == bytes():
                # Interpret an empty byte string as None
                validator_key = None

            txn = Transaction(inputs, outputs, validator_key)
            length = parser.consume_int()
            for i in range(0, length):
                sig = decode_signature(parser)
                if sig is not None:
                    txn.signatures.append(sig)
                # decode_signature(txn, parser)

            return NetTransaction(txn, identifier)

        elif item_type == ItemType.ACK:
            identifier = parser.consume_nested_bytes()
            if identifier == bytes():
                identifier = None
            transaction_id = parser.consume_nested_bytes()
            prev_ack_id = parser.consume_nested_bytes()
            if prev_ack_id == bytes():
                prev_ack_id = None
            pb_key = parser.consume_nested_bytes()

            ack = Acknowledge(transaction_id, prev_ack_id, pb_key)
            sig = decode_signature(parser)  # (pk, sig)
            if sig is not None:
                ack.signatures.append(sig)
            return NetAcknowledgement(ack, identifier)

        elif item_type == ItemType.UNSPENT_WALLET_COLLECTION:
            identifier = parser.consume_nested_bytes()
            if identifier == bytes():
                identifier = None
            is_req = parser.consume_int()
            length = parser.consume_int()
            uspnt_wllts = set()
            for i in range(0, length):
                origin_id = parser.consume_nested_bytes()
                wallet_id = parser.consume_int()
                uspnt_wllts.add((origin_id, wallet_id))
            return NetUSPWR(uspnt_wllts, is_req, identifier)

        else:
            return None
