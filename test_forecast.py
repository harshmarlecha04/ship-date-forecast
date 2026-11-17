"""Run with:  python -m unittest"""

import os
import tempfile
import unittest
from datetime import date

import forecast


class SimulateTests(unittest.TestCase):
    def test_steady_team_has_one_answer(self):
        # 5 a week, every week, 60 items: always exactly 12 weeks
        results = forecast.simulate(60, [5, 5, 5, 5], runs=200, seed=1)
        self.assertEqual(set(results), {12})

    def test_partial_week_rounds_up(self):
        results = forecast.simulate(61, [5, 5, 5, 5], runs=50, seed=1)
        self.assertEqual(set(results), {13})

    def test_same_seed_same_answer(self):
        history = [5, 7, 3, 6, 8, 4]
        self.assertEqual(forecast.simulate(60, history, seed=7), forecast.simulate(60, history, seed=7))

    def test_stays_between_best_and_worst_case(self):
        history = [3, 4, 9, 6]
        results = forecast.simulate(60, history, runs=500, seed=3)
        self.assertGreaterEqual(results[0], 7)    # 60 / 9, rounded up
        self.assertLessEqual(results[-1], 20)     # 60 / 3

    def test_zero_weeks_slow_things_down_but_finish(self):
        results = forecast.simulate(10, [0, 0, 5, 5], runs=300, seed=2)
        self.assertGreaterEqual(results[0], 2)
        self.assertLess(results[-1], forecast.MAX_WEEKS)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            forecast.simulate(0, [5, 5, 5, 5])
        with self.assertRaises(ValueError):
            forecast.simulate(10, [0, 0, 0, 0])
        with self.assertRaises(ValueError):
            forecast.simulate(10, [5, 5])


class PercentileTests(unittest.TestCase):
    def test_known_values(self):
        results = list(range(1, 101))  # 1..100
        self.assertEqual(forecast.percentile(results, 50), 50)
        self.assertEqual(forecast.percentile(results, 85), 85)
        self.assertEqual(forecast.percentile(results, 100), 100)

    def test_higher_confidence_is_never_sooner(self):
        results = forecast.simulate(80, [2, 5, 9, 4, 6], runs=1000, seed=11)
        self.assertLessEqual(forecast.percentile(results, 50), forecast.percentile(results, 85))
        self.assertLessEqual(forecast.percentile(results, 85), forecast.percentile(results, 95))


class FileTests(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return handle.name

    def test_reads_sample_file(self):
        history = forecast.load_history(os.path.join(os.path.dirname(__file__), "sample_history.csv"))
        self.assertEqual(len(history), 16)
        self.assertEqual(history[:3], [5, 7, 3])

    def test_skips_blank_rows(self):
        path = self.write("week_ending,completed\n2026-01-02,4\n2026-01-09,\n2026-01-16,6\n2026-01-23,5\n2026-01-30,3\n")
        self.assertEqual(forecast.load_history(path), [4, 6, 5, 3])

    def test_missing_column(self):
        path = self.write("week,done\n1,4\n2,5\n")
        with self.assertRaises(ValueError):
            forecast.load_history(path)

    def test_not_a_number(self):
        path = self.write("week_ending,completed\n2026-01-02,four\n")
        with self.assertRaises(ValueError):
            forecast.load_history(path)


class DateTests(unittest.TestCase):
    def test_finish_date(self):
        self.assertEqual(forecast.finish_date(date(2026, 11, 16), 10), date(2027, 1, 25))


if __name__ == "__main__":
    unittest.main()
