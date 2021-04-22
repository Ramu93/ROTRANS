import logging
from decimal import Decimal
from typing import Any, Tuple, Optional

from abccore.agent_items_parser import AgentItemsParser, decode_wallet
from abccore.network_datastructures import NetTransaction, encode_wallet
from abcnet.structures import ItemType
from abcnet.transcriber import ItemsParser, Parser

from abcckpt import ckptItems
from abcckpt.checkpoint_db import Checkpoint
from abcckpt.ckptItems import CkptItemType, Priority, CkptData, CkptHash
from abcckpt.ckpt_creation_state import CkptCreationState

logger = logging.getLogger("CkptItemsParser")

agent_parser = AgentItemsParser()


def decode_signature(parser: Parser) -> (bytes, bytes):
    signature_0 = parser.consume_nested_bytes()
    signature_1 = parser.consume_nested_bytes()
    if signature_0 == b'NO_SIGN' or signature_1 == b'NO_SIGN':
        signature = None
    else:
        signature = (signature_0, signature_1)
    return signature


class CkptItemsParser(ItemsParser):

    @staticmethod
    def decode_ckpt_msg(parser: Parser) -> Tuple[bytes, CkptCreationState, Optional[Tuple[bytes, bytes]]]:
        id = parser.consume_nested_bytes()
        state = ckptItems.decode_state(parser)
        signature = decode_signature(parser)
        return id, state, signature

    @staticmethod
    def decode_item(item_type: int, parser: Parser) -> Any:
        if item_type not in [CkptItemType.VALVOTE, CkptItemType.MAJVOTES, CkptItemType.PRIORITY,
                             CkptItemType.CKPT_DATA, CkptItemType.MOCK_CKPT_DATA, CkptItemType.CKPT_HASH]:
            raise ValueError("Unrecognized type: " + str(item_type))
        id_, state, signature = CkptItemsParser.decode_ckpt_msg(parser)
        if item_type == CkptItemType.VALVOTE:
            voted_item_type,vote_string,pub_k = decode_val_votes(parser)
            vote = ckptItems.ValidatorVote(state=state, voted_item_id=vote_string, voted_item_type=voted_item_type,
                                           pub_key=pub_k, id=id_)
            assert vote.set_sign(signature)
            return vote
        elif item_type == CkptItemType.MAJVOTES:
            voted_item_qualifier = parser.consume_nested_text()
            if voted_item_qualifier == "PASS":
                voted_item_qualifier = None
            vote_count = parser.consume_int()
            votes = list()
            for _ in range(vote_count):
                vote = parser.consume_nested_text()
                votes.append(vote)
            assert signature is None
            return ckptItems.MajorityVotes(state=state, votes=votes, voted_item_qualifier=voted_item_qualifier, id_=id_)
        elif item_type == CkptItemType.PRIORITY:
            pub_k, stake, proof, votes = ckptItems.decode_priority(parser)
            p = Priority(state=state, pub_k=pub_k, stake=stake,
                         proof=proof, votes=votes, id=id_)
            assert p.set_sign(signature)
            return p

        elif item_type == CkptItemType.CKPT_HASH:
            ckpt_hash = parser.consume_nested_bytes()
            hash_msg = CkptHash(ckpt_state=state, ckpt_hash=ckpt_hash, id=id_)
            assert hash_msg.set_sign(signature)
            return hash_msg
        elif item_type == CkptItemType.MOCK_CKPT_DATA:
            txn_len = parser.consume_int()
            txn_list = []
            for i in range(txn_len):
                net_txn: NetTransaction = agent_parser.decode_item(ItemType.TXN, parser)
                txn_list.append(net_txn.txn)
            ckpt = ckptItems.MockCkptData(state, txn_list, id_=id_)
            assert ckpt.set_sign(signature)
            return ckpt

        elif item_type == CkptItemType.CKPT_DATA:
            checkpoint = decode_ckpt_data(parser)
            ckpt_data = CkptData(state, checkpoint, id_)
            assert ckpt_data.set_sign(signature)
            return ckpt_data



def decode_ckpt_data(parser: Parser) -> Checkpoint:
    """
    Decodes the checkpoint object received over the network.
    Parameters:
        parser (Parser): parser object received from network module.
    Returns:
        Checkpoint: checkpoint object generated from the parsed state.
    """
    ckpt_id = parser.consume_nested_bytes()
    ckpt_origin = parser.consume_nested_bytes()
    ckpt_height = parser.consume_int()
    ckpt_time = parser.consume_double()
    ckpt_length = parser.consume_int()

    ckpt_utxo_list = decode_wallet(parser)

    ckpt_fees = decode_wallet(parser)

    ckpt_nutxo = parser.consume_int()

    ckpt_stakelist = parser.consume_nested_text()
    ckpt_stake_dict = {}

    # decode stake list
    stake_list_string = str(ckpt_stakelist).strip().split(';')
    for stake in stake_list_string:
        if stake == '':
            break

        validator = bytes.fromhex(stake.split(':')[0])
        validator_stake = Decimal(str(stake.split(':')[1]))
        ckpt_stake_dict[validator] = validator_stake

    ckpt_total_stake = parser.consume_nested_text()
    ckpt_total_coins = parser.consume_nested_text()
    ckpt_miner = parser.consume_nested_bytes()
    checkpointdb = Checkpoint(ckpt_origin, ckpt_height, ckpt_time, ckpt_length, ckpt_utxo_list,
                              ckpt_fees, ckpt_stake_dict, ckpt_nutxo, Decimal(ckpt_total_stake),
                              Decimal(ckpt_total_coins), ckpt_miner)
    assert checkpointdb.id == ckpt_id
    return checkpointdb


def decode_val_votes(parser: Parser):
    voted_item_type = parser.consume_int()
    vote_string = parser.consume_text()
    if vote_string == "PASS":
        vote_string = None
    pub_k = parser.consume_nested_bytes()
    return voted_item_type,vote_string,pub_k
