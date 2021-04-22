import unittest
from decimal import Decimal
from typing import List, Dict

from abccore.DAG import Checkpoint, Wallet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abcckpt import fast_vrf
from abcckpt.ckptItems import ValidatorVote, CkptItemType, MajorityVotes, Priority, encode_state, CkptHash, CkptData
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState
from abcnet.nettesthelpers import data_tester
from abcnet.transcriber import Transcriber, Parser
from abcckpt.ckpt_creation_state import PreCkptStatus


priv_key_0 = fast_vrf.gen_key(0)
pub_key_0 = fast_vrf.encode_pub_key(priv_key_0.public_key())

pub_key_1 = fast_vrf.encode_pub_key(fast_vrf.gen_key(2).public_key())
pub_key_2 = fast_vrf.encode_pub_key(fast_vrf.gen_key(3).public_key())


def equality_tester(item_provider):
    item1 = item_provider()
    assert item1.get_id() is not None
    item2 = item_provider()
    assert item1.get_id() == item2.get_id()
    item_provider(id_=item1.get_id())
    assert item1.item_qualifier() is not None and len(item1.item_qualifier()) >= 10
    assert item1.item_qualifier() == item2.item_qualifier()

def inequality_tester(item_provider1, item_provider2):
    item1 = item_provider1()
    item2 = item_provider2()
    assert item1 != item2
    assert item1.get_id() != item2.get_id()
    assert item1.item_qualifier() != item2.item_qualifier()

def serialization_tester(item_provider, expected_item_type, key: Ed25519PrivateKey = None):
    item1 = item_provider()
    if key is not None:
        item1.add_signature(key)
        item1.verify_signature()
    assert item1.item_type() == expected_item_type
    t = Transcriber()
    item1.encode(t)
    p = Parser(t.msg.parts[0])
    item2 = CkptItemsParser.decode_item(item1.item_type(), p)
    if key:
        assert item2.verify_signature()
    assert item1 == item2


def fail_tester(item_providor, key=None, signature= None, expected_exception_class=Exception):
    try:
        item = item_providor()
        if key is not None:
            item.add_signature(key)
            item.verify_signature()
        if signature is not None:
            item.set_sign(signature)
            item.verify_signature()
        assert False # Shouldn't be reached
    except Exception as e:
        assert isinstance(e, expected_exception_class)


class TestCkptItems(unittest.TestCase):

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "voted_item_1",
            "item_id": CkptItemType.PRIORITY,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       chosen_validator=b'Some_chosen_Validator'),
            "vote": "voted_item_1",
            "item_id": CkptItemType.PRIORITY,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       content_hash=b'Some_chosen_Hash'),
            "vote": "voted_item_1",
            "item_id": CkptItemType.PRIORITY,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "voted_item_1",
            "item_id": CkptItemType.PRIORITY,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'#1@', 1000, PreCkptStatus.AGREE_CONTENT),
            "vote": "Voted_item1",
            "item_id": CkptItemType.PRIORITY,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "",
            "item_id": CkptItemType.PRIORITY,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC" * 100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC" * 100,
            "item_id": CkptItemType.CKPT_HASH,
            "pub_key": b'12345'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC" * 100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": fast_vrf.encode_pub_key(fast_vrf.gen_key().public_key())
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": None,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": fast_vrf.encode_pub_key(fast_vrf.gen_key().public_key())
        },
    ])
    def test_vote_id_equality(self, state, vote, pub_key, item_id=None):
        equality_tester(lambda id_=None: ValidatorVote(state, vote, item_id, pub_key, id=id_))

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_2
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       chosen_validator=b'Some_chosen_Validator'),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       chosen_validator=b'Some_chosen_Validator'),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       chosen_validator=b'Some_chosen_Validator2'),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       content_hash=b'Some_chosen_Hash'),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       content_hash=b'Some_chosen_Hash'),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR,
                                       content_hash=b'Some_chosen_Hash_2'),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str2', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str1', 1, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 5, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str1', 10, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_CONTENT),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "DEF"*100,
            "item_id2": CkptItemType.CKPT_DATA,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": "ABC"*100,
            "item_id2": CkptItemType.CKPT_HASH,
            "pub_key2": pub_key_1
        },
        {
            "state": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote": "ABC"*100,
            "item_id": CkptItemType.CKPT_DATA,
            "pub_key": pub_key_1,
            "state2": CkptCreationState(b'prev_common_str1', 0, PreCkptStatus.AGREE_VALIDATOR),
            "vote2": None,
            "item_id2": CkptItemType.CKPT_HASH,
            "pub_key2": pub_key_1
        },
    ])
    def test_vote_id_inequality(self, state, vote, pub_key, item_id, state2, vote2, pub_key2, item_id2):
        inequality_tester(lambda : ValidatorVote(state, vote, item_id, pub_key),
                            lambda : ValidatorVote(state2, vote2, item_id2, pub_key2))


    @data_tester(test_data=[
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "vote": "ABC" * 100,
                "item_id": CkptItemType.CKPT_DATA,
                "pub_key": pub_key_0,
                "key" : priv_key_0
            },
            {
                "state": CkptCreationState(b'abc_0_', 0, PreCkptStatus.AGREE_HASH),
                "vote": "ABC" * 100,
                "item_id": CkptItemType.CKPT_HASH,
                "pub_key": pub_key_0,
                "key" : None
            },
            {
                "state": CkptCreationState(b'abc_1_', 5, PreCkptStatus.AGREE_CONTENT),
                "vote": None,
                "item_id": CkptItemType.PRIORITY,
                "pub_key": pub_key_0,
                "key" : priv_key_0
            },
            {
                "state": CkptCreationState(b'abc_2', 60, PreCkptStatus.AGREE_VALIDATOR),
                "vote": None,
                "item_id": CkptItemType.PRIORITY,
                "pub_key": pub_key_0,
                "key" : None
            },
        ])
    def test_vote_serialisation(self, state, vote, pub_key, key: Ed25519PrivateKey, item_id):
        serialization_tester(lambda : ValidatorVote(state, vote, item_id, pub_key), CkptItemType.VALVOTE, key)


    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["One vote only"],
            "voted_item": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_ckpt_1', 2, PreCkptStatus.AGREE_CONTENT),
            "votes": ["One vote only"],
            "voted_item": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_CONTENT),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": None
        },
    ])
    def test_majority_votes_id_equality(self, state: CkptCreationState, votes: List[str], voted_item: str):
        equality_tester(lambda id_=None: MajorityVotes(state, votes, voted_item, id_=id_))

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_2', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes2": ["v1_id", "v2_id", "v3_id"],
            "voted_item2": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 1, PreCkptStatus.AGREE_VALIDATOR),
            "votes2": ["v1_id", "v2_id", "v3_id"],
            "voted_item2": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_CONTENT),
            "votes2": ["v1_id", "v2_id", "v3_id"],
            "voted_item2": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_HASH),
            "votes2": ["v1_id", "v2_id", "v3_id"],
            "voted_item2": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id", "v2_id", "v3_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes2": ["v1_id"],
            "voted_item2": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes2": ["v1_id_2"],
            "voted_item2": "voted_item"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes2": ["v1_id"],
            "voted_item2": "voted_item2"
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id"],
            "voted_item": "voted_item",
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes2": ["v1_id"],
            "voted_item2": None
        },
    ])
    def test_majority_votes_id_inequality(self, state: CkptCreationState, votes: List[str], voted_item: str,
                                          state2: CkptCreationState, votes2: List[str], voted_item2: str):
        inequality_tester(lambda :MajorityVotes(state, votes, voted_item),
                          lambda : MajorityVotes(state2, votes2, voted_item2))

    @data_tester(test_data=[
        # {
        #     "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
        #     "votes": ["v1_id", "v2_id", "v3_id"],
        #     "voted_item": "voted_item"
        # },
        # {
        #     "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
        #     "votes": ["v1_id"],
        #     "voted_item": "voted_item"
        # },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "votes": ["v1_id"],
            "voted_item": None
        },
    ])
    def test_majority_votes_serialisation(self, state: CkptCreationState, votes: List[str], voted_item: str):
        serialization_tester(lambda: MajorityVotes(state, votes, voted_item), CkptItemType.MAJVOTES)

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "pub_k": pub_key_1,
            "stake": Decimal(2.0),
            "proof": b'PROOF_OF_VOTES',
            'votes': 10,
        },
        {
            "state": CkptCreationState(b'abc_checkpoint_1', 1, PreCkptStatus.AGREE_CONTENT),
            "pub_k": pub_key_2,
            "stake": Decimal(0.0),
            "proof": b'PROOF_OF_VOTES_1',
            'votes': 100,
        },
    ])
    def test_priority_id_equality(self, state: CkptCreationState, pub_k: bytes,
                 stake: Decimal, proof: bytes, votes: int):
        equality_tester(lambda id_=None: Priority(state, pub_k, stake, proof, votes, id=id_))

    @data_tester(
        test_data=[
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 1, PreCkptStatus.AGREE_CONTENT),
                "pub_k2": pub_key_1,
                "stake2": Decimal(2.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'checkpoint', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_1,
                "stake2": Decimal(2.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 2, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 10, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_1,
                "stake2": Decimal(2.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_2,
                "stake2": Decimal(2.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_1,
                "stake2": Decimal(20.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_1,
                "stake2": Decimal(0.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_1,
                "stake2": Decimal(2.0),
                "proof2": b'PROOF_OF_VOTES_two',
                'votes2': 10,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k2": pub_key_1,
                "stake2": Decimal(2.0),
                "proof2": b'PROOF_OF_VOTES',
                'votes2': 0,
            },
            {
                "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
                "pub_k": pub_key_1,
                "stake": Decimal(2.0),
                "proof": b'PROOF_OF_VOTES',
                'votes': 10,
                "state2": CkptCreationState(b'abc_checkpoint_2', 1, PreCkptStatus.AGREE_CONTENT),
                "pub_k2": pub_key_2,
                "stake2": Decimal(10.0),
                "proof2": b'NO_PROOF',
                'votes2': 1,
            },
        ]
    )
    def test_priority_id_inequality(self,
                                    state: CkptCreationState, pub_k: bytes,
                                    stake: Decimal, proof: bytes, votes: int,
                                    state2: CkptCreationState, pub_k2: bytes,
                                    stake2: Decimal, proof2: bytes, votes2: int,
                                    ):
        inequality_tester(lambda: Priority(state, pub_k, stake, proof, votes),
                          lambda: Priority(state2, pub_k2, stake2, proof2, votes2))

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR),
            "pub_k": pub_key_1,
            "stake": Decimal(2.0),
            "proof": b'PROOF_OF_VOTES',
            'votes': 10,
        },
        {
            "state": CkptCreationState(b'abc_checkpoint_1', 1, PreCkptStatus.AGREE_CONTENT),
            "pub_k": pub_key_2,
            "stake": Decimal(0.0),
            "proof": b'PROOF_OF_VOTES_1',
            'votes': 100,
        },
        {
            "state": CkptCreationState(b'abc_checkpoint_1', 1, PreCkptStatus.AGREE_CONTENT),
            "pub_k": pub_key_1,
            "stake": Decimal(0.0),
            "proof": b'PROOF_OF_VOTES_1',
            'votes': 100,
            "key": priv_key_0
        },
    ])
    def test_priority_serialisation(self,
                                    state: CkptCreationState, pub_k: bytes,
                                    stake: Decimal, proof: bytes, votes: int, key=None):
        serialization_tester(lambda :Priority(state, pub_k, stake, proof, votes), CkptItemType.PRIORITY, key)

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_0),
            "ckpt_hash": b'abcdef',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'abcdef',
        },
    ])
    def test_ckpt_hash_equality(self,
                                state: CkptCreationState, ckpt_hash):
        equality_tester(lambda id_=None: CkptHash(state, ckpt_hash, id=id_))


    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
        },
    ])
    def test_ckpt_hash_equality(self,
                                state: CkptCreationState, ckpt_hash,
                                ):
        equality_tester(lambda id_=None: CkptHash(state, ckpt_hash, id_))

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash2": b'',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_0),
            "ckpt_hash2": b'12345',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash2": b'abcdef',
        },
    ])
    def test_ckpt_hash_inequality(self,
                                state: CkptCreationState, ckpt_hash,
                                state2: CkptCreationState, ckpt_hash2):
        inequality_tester(lambda: CkptHash(state, ckpt_hash),
                          lambda: CkptHash(state2, ckpt_hash2))

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "ckpt_hash": b'12345',
            "key": priv_key_0
        },
    ])
    def test_ckpt_hash_serialization(self,
                                    state: CkptCreationState, ckpt_hash, key=None):
        serialization_tester(lambda : CkptHash(state, ckpt_hash), CkptItemType.CKPT_HASH, key)


    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
            ],
            "outputs": [
            ],
            "stake_list": {
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1'
        },
    ])
    def test_ckpt_data_equality(self, state, origin: bytes, height: int, locktime: float, length: int,
                 utxos: List[Wallet], outputs: List[Wallet], stake_list: Dict,
                 nutxo: int, tstake: Decimal, tcoins: Decimal, miner: bytes):

        def creator(id_=None):
            ckpt_data = Checkpoint(origin, height, locktime, length,
                                   utxos, outputs, stake_list,
                                   nutxo, tstake, tcoins, miner)
            return CkptData(state, ckpt_data, id_)

        equality_tester(creator)

    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 1, PreCkptStatus.AGREE_CONTENT, chosen_validator=pub_key_2),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',
            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis2',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 6,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100301.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10001,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(2.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner2',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(12.06),
            "miner": b'Miner1',

            "state2": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin2": b'Genesis',
            "height2": 5,
            "locktime2": 100201.0,
            "length2": 10000,
            "utxos2": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs2": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list2": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo2": 5,
            "tstake2": Decimal(1.099),
            "tcoins2": Decimal(10.06),
            "miner2": b'Miner1'
        },
    ])
    def test_ckpt_data_inequality(self, state, origin: bytes, height: int, locktime: float, length: int,
                 utxos: List[Wallet], outputs: List[Wallet], stake_list: Dict,
                 nutxo: int, tstake: Decimal, tcoins: Decimal, miner: bytes,
                                  state2, origin2: bytes, height2: int, locktime2: float, length2: int,
                                  utxos2: List[Wallet], outputs2: List[Wallet], stake_list2: Dict,
                                  nutxo2: int, tstake2: Decimal, tcoins2: Decimal, miner2: bytes
                                  ):

        def creator(id_=None):
            ckpt_data = Checkpoint(origin, height, locktime, length,
                                   utxos, outputs, stake_list,
                                   nutxo, tstake, tcoins, miner)
            return CkptData(state, ckpt_data, id_)

        def creator2(id_=None):
            ckpt_data = Checkpoint(origin2, height2, locktime2, length2,
                                   utxos2, outputs2, stake_list2,
                                   nutxo2, tstake2, tcoins2, miner2)
            return CkptData(state2, ckpt_data, id_)

        inequality_tester(creator, creator2)



    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',
            "key": priv_key_0
        },
    ])
    def test_ckpt_data_serialization(self,
                                    state: CkptCreationState, origin: bytes, height: int, locktime: float, length: int,
                 utxos: List[Wallet], outputs: List[Wallet], stake_list: Dict,
                 nutxo: int, tstake: Decimal, tcoins: Decimal, miner: bytes, key=None):

        def creator(id_=None):
            ckpt_data = Checkpoint(origin, height, locktime, length,
                                   utxos, outputs, stake_list,
                                   nutxo, tstake, tcoins, miner)
            return CkptData(state, ckpt_data, id_)

        serialization_tester(creator, CkptItemType.CKPT_DATA, key)


    @data_tester(test_data=[
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_1),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',
            "key": None
        },
        {
            "state": CkptCreationState(b'abc_genesis_', 0, PreCkptStatus.AGREE_VALIDATOR, chosen_validator=pub_key_0),
            "origin": b'Genesis',
            "height": 5,
            "locktime": 100201.0,
            "length": 10000,
            "utxos": [
                Wallet(pub_key_1, Decimal(10.5), b'txn1', 1),
                Wallet(pub_key_1, Decimal(15.5), b'txn1', 2),
                Wallet(pub_key_2, Decimal(1.5), b'txn5', 2),
            ],
            "outputs": [
                Wallet(pub_key_1, Decimal(10.5)),
                Wallet(pub_key_1, Decimal(15.5)),
                Wallet(pub_key_2, Decimal(1.5)),
            ],
            "stake_list": {
                pub_key_1: Decimal(100),
                pub_key_2: Decimal(200),
            },
            "nutxo": 5,
            "tstake": Decimal(1.099),
            "tcoins": Decimal(10.06),
            "miner": b'Miner1',
            "key": priv_key_0
        },
    ])
    def test_ckpt_data_serialization(self,
                                    state: CkptCreationState, origin: bytes, height: int, locktime: float, length: int,
                 utxos: List[Wallet], outputs: List[Wallet], stake_list: Dict,
                 nutxo: int, tstake: Decimal, tcoins: Decimal, miner: bytes, key=None):

        def creator(id_=None):
            ckpt_data = Checkpoint(origin, height, locktime, length,
                                   utxos, outputs, stake_list,
                                   nutxo, tstake, tcoins, miner)
            return CkptData(state, ckpt_data, id_)

        serialization_tester(creator, CkptItemType.CKPT_DATA, key)
