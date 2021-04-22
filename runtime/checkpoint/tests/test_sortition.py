from decimal import Decimal

import math
import unittest
import scipy.stats
import time

from abcckpt import fast_vrf
from abcckpt import sortition

# Binomial parameters
from abcckpt.ckpt_creation_state import CkptCreationState

p = 0.5
n = 1000
# Normal distribution parameters
mean = n * p
var = n * p * (1.0 - p)


class TestSortition(unittest.TestCase):

    def test_scipy_binom_runtime_efficiency(self):
        bd = scipy.stats.binom(n=n, p=p)
        start_time = time.time()
        for i in range(n):
            bd.cdf(i)
        run_time = time.time() - start_time
        print(f"Runtime scipy.stats.binom was: {run_time}")

    def test_scipy_normal_runtime_efficiency(self):
        nd = scipy.stats.norm(loc=n, scale=n)
        start_time = time.time()
        counter = 0
        for i in range(0, n*2, int(n / 50)):
            nd.cdf(i)
            counter += 1
        run_time = time.time() - start_time
        print(f"Average runtime time of scipy.stats.norm.cdf was: {run_time/counter: 0.5f}")

    def test_scipy_poisson_runtime_efficiency(self):
        start_time = time.time()
        pd = scipy.stats.poisson(mean)
        run_time = time.time() - start_time
        print(f"Runtime scipy.stats.poisson() was: {run_time}")
        start_time = time.time()
        counter = 0
        for i in range(0, n, int(n / 100)):
            pd.cdf(i)
            counter += 1
        run_time = time.time() - start_time
        print(f"Runtime scipy.stats.poisson.cdf was: {run_time}")

    def test_sortition_speed_samples(self):
        stake = 20
        # self.calc_and_print('n', 0.85, 1000)
        start_time = time.time()
        for i in range(1000):
            sample = i * 0.001
            # self.calc_and_print('p', sample, stake)
            sortition.vote_calc_normal(sample, stake)
        print(f"Performed sortition {1000} times in {time.time() - start_time: 0.3f} seconds.")

    def test_sortition_speed_high_stake(self):
        # High stake count:
        start_time = time.time()
        stake = 100000
        sortition.vote_calc_normal(0.999, stake)
        print(f"Performed sortition for stake={stake} in {time.time() - start_time: 0.3f} seconds.")


    def assert_votes_match(self, sample, stake):
        votes = sortition.vote_calc_normal(sample, stake)
        distrib = scipy.stats.norm(stake, stake)
        cdf_votes = distrib.cdf(votes)
        cdf_next = distrib.cdf(votes + 1)
        if distrib.cdf(0) >= sample:
            self.assertEqual(votes,  0, "Votes must be zero if sample is below 16%.")
            return
        print(f"Asserting: norm.cdf({votes})={cdf_votes} <= votes({sample},{stake})={votes} < norm.cdf({votes + 1})={cdf_next}")
        self.assertLessEqual(cdf_votes, sample, "The cdf of calculated vote "
                                                "must be less equal than the sample.")
        self.assertGreater(cdf_next, sample, "The cdf of the next higher number of the calculated vote "
                                             "must be greater than sample.")

    def assert_matches_multiplication(self, sample, stake):
        if sample < 0.16:
            return
        votes = sortition.vote_calc_normal(sample, stake)
        multiplication = math.floor((stake*2) * sample)
        print(f"Asserting {stake} * 2 * {sample} = {multiplication} == votes={votes}")
        # assert votes == multiplication

    def test_normal_sortititon(self):
        assert sortition.vote_calc_normal(0.0, 10) == 0
        sample = 0.15
        for stake_pow in range(1, 5):
            stake = 10 ** stake_pow
            assert sortition.vote_calc_normal(sample, stake) == 0

        for stake_pow in range(1, 5):
            stake = 10 ** stake_pow
            self.assert_votes_match(0.5, stake)
            self.assert_votes_match(0.9, stake)
            self.assert_votes_match(0.999, stake)
            self.assert_votes_match(0.99999, stake)
            self.assert_votes_match(0.3, stake)
            self.assert_votes_match(0.16, stake)

        import random
        r = random.Random(2)
        for i in range(100):
            stake = r.randint(0, 1000)
            for j in range(10):
                sample = r.random()
                self.assert_votes_match(sample, stake)
                self.assert_matches_multiplication(sample, stake)


    def assert_sort_unequal(self, sort1: sortition.SortitionProperties, sort2: sortition.SortitionProperties):
        self.assertNotEqual(sort1.votes, sort2.votes, "Votes must not be equal.")


    def assert_sort_unequal_sample(self, sort1: sortition.SortitionProperties, sort2: sortition.SortitionProperties):
        self.assertNotEqual(sort1.proof, sort2.proof, "Proofs must not be equal.")
        self.assertNotEqual(sort1.sample, sort2.sample, "Sample must not be equal.")
        self.assert_sort_unequal(sort1, sort2)


    def test_stake_sortition(self):
        state = CkptCreationState(b'common_string')
        key1 = fast_vrf.gen_key()
        key2 = fast_vrf.gen_key()

        calc = sortition.SortitionProperties.calculate
        props = calc(state.get_current_common_str(), key1, Decimal(100.0))
        assert props.seed == state.get_current_common_str()
        self.assert_sort_unequal_sample(calc(state.get_current_common_str(), key1, Decimal(100.0)),
                                 calc(state.get_current_common_str(), key2, Decimal(100.0)))


        self.assert_sort_unequal(calc(state.get_current_common_str(), key1, Decimal(100.0)),
                                 calc(state.get_current_common_str(), key1, Decimal(200.0)))

        self.assert_sort_unequal(calc(state.get_current_common_str(), key1, Decimal(1000.0)),
                                 calc(state.get_current_common_str(), key1, Decimal(2000.0)))

        state2 = CkptCreationState.copy(state, next_round=True)

        self.assert_sort_unequal_sample(calc(state.get_current_common_str(), key1, Decimal(1000.0)),
                                 calc(state2.get_current_common_str(), key1, Decimal(2000.0)))
        assert calc(state2.get_current_common_str(), key1, Decimal(2000.0)).seed == state2.current_common_str

