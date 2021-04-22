import unittest

from abcckpt import fast_vrf


class TestHashVRF(unittest.TestCase):

    def test_prove_main_mechanics(self):
        sk = fast_vrf.gen_key()
        skb = fast_vrf.encode_sec_key(sk)
        status, proof = fast_vrf.hash_vrf_prove(skb, b"12345", True)
        assert status == 'VALID'

        status, sample = fast_vrf.hash_vrf_proof_to_hash(proof, True)
        assert status == 'VALID'
        assert 0 <= sample < 1
        status, sample2 = fast_vrf.hash_vrf_verify(fast_vrf.encode_pub_key(sk.public_key()), proof, b'12345', True)

        assert status == 'VALID'
        assert sample2 == sample

        status, sample2 = fast_vrf.hash_vrf_verify(fast_vrf.encode_pub_key(sk.public_key()), proof,
                                                   b'different_alpha_string')
        assert status == 'INVALID'
        assert sample2 == 0.0

