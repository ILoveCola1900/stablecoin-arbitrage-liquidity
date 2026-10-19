"""Meaningful accounting, threshold, FIFO, timing and boundary checks."""
import random
import unittest
from simulator import rolling_threshold, simulate


class SimulationTests(unittest.TestCase):
    def test_hand_calculations(self):
        for delay,cash,expected,clear in [(1,.98,6,6),(3,1.96,4,8),(3,.98,2,16)]:
            s,_,_=simulate([1]*6,delay,cash)
            self.assertAlmostEqual(s['purchased_by_day6_million'],expected)
            self.assertEqual(s['last_purchase_day'],clear)

    def test_equal_totals_different_timing(self):
        for path,peak in [([1]*6,0),([3,0,0,3,0,0],0),([0,0,3,3,0,0],3)]:
            s,_,_=simulate(path,3,2.94)
            self.assertAlmostEqual(s['peak_backlog_million'],peak)

    def test_fifo_and_wait_identity(self):
        s,_,fills=simulate([2,1],2,.98)
        self.assertEqual([(f['arrival_day'],f['purchase_day']) for f in fills],[(1,1),(1,3),(2,5)])
        self.assertAlmostEqual(s['average_wait_days'],5/3)

    def test_profit_reinvestment_boundary(self):
        path=[1,1.01]
        self.assertGreater(rolling_threshold(path,1),.98)
        baseline,_,_=simulate(path,1,.98)
        reinvest,_,_=simulate(path,1,.98,reinvest=True)
        self.assertGreater(baseline['peak_backlog_million'],0)
        self.assertAlmostEqual(reinvest['peak_backlog_million'],0)

    def test_time_shift_preserves_main_metrics(self):
        a,_,_=simulate([1,2,0,3],3,.98)
        b,_,_=simulate([0,0,1,2,0,3],3,.98)
        for k in ['peak_backlog_million','average_wait_days','cleanup_days_after_last_arrival']:
            self.assertAlmostEqual(a[k],b[k])

    def test_empty_and_invalid(self):
        s,_,_=simulate([0,0],3,.98)
        self.assertEqual(s['average_wait_days'],0)
        for args in [([1],0,.98),([-1],1,.98),([1],1,0)]:
            with self.assertRaises(ValueError): simulate(*args)

    def test_random_threshold_and_baseline_accounting(self):
        rng=random.Random(20261019)
        for _ in range(2000):
            path=[rng.choice([0,0,.1,.5,1,2,5]) for _ in range(rng.randint(1,40))]
            delay=rng.randint(1,10)
            threshold=rolling_threshold(path,delay)
            if threshold < 1e-8: continue
            at,_,_=simulate(path,delay,threshold)
            below,_,_=simulate(path,delay,threshold*.9999)
            self.assertLess(at['peak_backlog_million'],1e-7)
            self.assertGreater(below['peak_backlog_million'],1e-8)


if __name__=='__main__':
    unittest.main()
