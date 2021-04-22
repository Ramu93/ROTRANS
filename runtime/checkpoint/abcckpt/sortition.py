import math
from typing import Union, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abcckpt import fast_vrf
import logging
from decimal import *

from scipy.stats import binom
import scipy.stats

logger = logging.getLogger("sortition")


def binomial_calc(k: int, stake: int, prob_value):
    """Binomial distribution calculation.

    :param k: try value
    :param stake: stake of validator
    :param prob_value: probability value"""
    return (math.factorial(stake) / (math.factorial(k) * math.factorial(stake - k))) * pow(prob_value, k) * pow(
        1 - prob_value, (stake - k))


def __parse_vote_calc_inputs(sample: Union[Decimal, float], stake: Union[Decimal, int]) -> Tuple[float, int]:
    """
    Parses and checks the inputs values for sortition calculation.

    :param sample:  sample value must be within 0.0 and 1.0
    :param stake: The stake value
    :return: parsed sample and stake
    """
    if isinstance(stake, Decimal):
        stake = int(stake.quantize(Decimal('1.'), rounding=ROUND_DOWN))
    if not isinstance(stake, int):
        raise ValueError("Unrecognized stake type: " + str(stake))
    if stake < 0:
        raise ValueError("Stake cannot be negative: " + str(stake))

    if isinstance(sample, Decimal):
        sample = float(sample.quantize(Decimal('1.00000'), rounding=ROUND_DOWN))
    if isinstance(sample, int):
        sample = float(sample)
    if not isinstance(sample, float):
        raise ValueError("Unrecognized sample type: " + str(sample))
    if sample < 0 or sample >= 1:
        raise ValueError("Sample is expected to be in [0, 1). Given sample is out of range: " + str(sample))
    return sample, stake


def sortition_distribution(stake: int) -> scipy.stats.norm:
    """
    Returns the distribution that we use for vote calculation.
    Through experimentation we have found that norm(stake, stake) is a fast distribution that still allows small stake
    players to win over high stake validators.
    It still proportionally given validators votes proportionally to the amount of stake.
    """
    return scipy.stats.norm(stake, stake)


def vote_calc_normal(sample: Union[Decimal, float], stake: Union[Decimal, int]) -> int:
    """
    Returns priority value.
    Performs inverse transform sampling onto normal(stake, stake) using binary search.
    Runs in O(log(stake))

    :param sample: The VRF drawn random sample. It is a uniformly random number between 0 and 1 (exclusive).
    :param stake: stake of validator.
    :return: The priority of the stake and sample.
    """
    if stake == 0:
        return 0
    sample, stake = __parse_vote_calc_inputs(sample, stake)

    # Normal distribution with a mean of stake (50% probability to get exactly stake amount of votes)
    # and variance of stake too. (High probability that small stakeholders get high vote count)
    distribution = sortition_distribution(stake)

    # Edge case: sample is smaller that cdf(0), negative tosses are converted to zero:
    if distribution.cdf(0) >= sample:
        return 0

    # Perform binary search on x to find the right probability value x with: cdf(x) <= sample < cdf(x+1)
    cursor = stake

    # Search boundaries
    min_cursor = None
    max_cursor = None

    while True:
        # step_size = int(math.ceil(step_size / 2)) # half the step size in each round
        cursor_cdf = distribution.cdf(cursor)
        if cursor_cdf > sample:
            max_cursor = cursor
        elif cursor_cdf < sample:
            min_cursor = cursor
        else:
            return cursor

        if min_cursor is not None and max_cursor is not None:
            if max_cursor - min_cursor < 4:
                break
            cursor = int(math.ceil((min_cursor + max_cursor) / 2))
        else:
            # min or max was not found yet.
            # At this point either min or max must be defined.
            assert min_cursor is not None or max_cursor is not None

            # Now just move the cursor towards the undefined area by variance amount
            if min_cursor is not None:
                cursor += stake
            elif max_cursor is not None:
                cursor -= stake
    # Min and max are now very close together.
    # Iterate over the remaining number of candidates starting from min.
    for cursor in range(min_cursor, max_cursor+1):
        # Increase cdf one by one until we cross sample.
        cursor_cdf = distribution.cdf(cursor)
        if sample < cursor_cdf:
            if cursor == min_cursor:
                raise ValueError("Not correct cursor found")
            # We have crossed the sample value with the current cursor.
            # The previous cursor value is the last value that is behind the sample threshold.
            votes = cursor - 1
            # Recheck:
            assert verify_votes_match_sample(sample, stake, votes)
            return votes
    raise ValueError(f"Cursor should have been found for stake={stake} sample={sample}")


def verify_votes_match_sample(sample: Union[Decimal, float], stake: Union[Decimal, int], votes: int) -> bool:
    """
    Verifies that the given votes based on the sample and stake.
    It must be true that sample is greater equal cdf(votes) but sample < cdf(votes+1).
    Runs in O(1).
    """
    sample, stake = __parse_vote_calc_inputs(sample=sample, stake=stake)
    distribution = sortition_distribution(stake)
    if votes == 0:
        return sample < distribution.cdf(1)
    return distribution.cdf(votes) <= sample < distribution.cdf(votes+1)


def verify_sortition(validator: "ValidatorProperties") -> bool:
    """Sortition verification: verifies votes j based on the stake and the public key.
    It is not verified if the stated stake amount belongs to the given public key.
     returns True if successful else False.

    :param validator: received validator properties
    """
    p_status, given_sample = fast_vrf.hash_vrf_verify(validator.public_key, validator.sortition.proof,
                                                         validator.sortition.seed)
    if p_status != 'VALID' or given_sample != validator.sortition.sample:
        return False

    return verify_votes_match_sample(sample=validator.sortition.sample,
                                     stake=validator.stake,
                                     votes=validator.sortition.votes)


class SortitionProperties:
    """Calculation of VRF proof pi, proof hash and votes j"""

    def __init__(self, proof: bytes, sample: Decimal, seed: bytes, votes: int):
        """Creates sortition properties.
        """
        self.seed: bytes = seed
        self.proof: bytes = proof
        self.sample: Decimal = sample
        self.votes: int = votes

    @classmethod
    def calculate(cls, seed: bytes, sk_bytes: Union[bytes, Ed25519PrivateKey], stake: Decimal) -> "SortitionProperties":
        """Calculates VRF proof(proof) and proof hash(proof_hash) and creates.

        :param seed: common string for VRF calculation
        """
        p_status, proof = fast_vrf.hash_vrf_prove(sk_bytes, seed)
        if p_status != 'VALID':
            raise ValueError("Cannot create proof for seed: " )
        vrf_status, sample = fast_vrf.hash_vrf_proof_to_hash(proof)
        assert vrf_status == 'VALID'
        votes = vote_calc_normal(sample = sample, stake=stake)
        return SortitionProperties(proof, sample, seed, votes)

    def __eq__(self, other: "SortitionProperties"):
        return self.votes == other.votes \
                and self.proof == other.proof \
                and self.seed == other.seed \
                and self.sample == other.sample


class ValidatorProperties:
    """
    Data class for storing validator details that needs to be sent across network.
    """
    def __init__(self, public_key, step: bytes, common_string: bytes,
                 stake: Decimal = None, sortition: SortitionProperties = None):

        self.sortition: SortitionProperties = sortition
        self.common_string: bytes = common_string
        self.stake = stake
        self.public_key = public_key
        self.step = step

    def __eq__(self, other: "ValidatorProperties"):
        return self.stake == other.stake \
                and self.public_key == other.public_key \
                and self.sortition == other.sortition \
                and self.common_string == other.common_string \
                and self.step == other.step
