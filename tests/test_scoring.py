import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import PREREC_PENALTY
from parser import parse_time
from scoring import calculate_score
from model import is_adjacent_slot_pair


class ScoringTests(unittest.TestCase):
    def test_score_components_sum_to_total(self):
        solution = {
            "data": [
                {"race": 0, "slot": 0, "p1_prerec": False, "p2_prerec": False},
                {"race": 1, "slot": 1, "p1_prerec": True, "p2_prerec": False},
            ]
        }
        match_data = [
            {
                "runner1": "a",
                "runner2": "b",
                "r1_preferred": {0},
                "r2_preferred": {0},
            },
            {
                "runner1": "c",
                "runner2": "d",
                "r1_preferred": {0},
                "r2_preferred": {0},
            },
        ]
        runner_preferred_slots = {"a": {0}, "b": {0}, "c": {0}, "d": {0}}

        score = calculate_score(solution, match_data, runner_preferred_slots, 2, 1)

        self.assertEqual(
            score["score"],
            score["double_prerec"] * 1_000_000
            + score["prerec_count"] * PREREC_PENALTY
            + score["bonus_count"] * -1_000
            + score["isolated_count"] * 1_000
            + score["empty_days"] * 1
            + score["preferred_penalty"] * 1
            + score["center_slot_penalty"]
            + score["late_prerec_penalty"],
        )

    def test_hourly_utc_slots_are_mapped_across_weekdays(self):
        self.assertEqual(parse_time(0, "00:00 UTC"), 0)
        self.assertEqual(parse_time(0, "23:00 UTC"), 23)
        self.assertEqual(parse_time(1, "00:00 UTC"), 24)

    def test_nothing_is_not_an_availability_time(self):
        self.assertEqual(parse_time(0, "3:00 UTC"), 3)

    def test_adjacent_slot_helper_respects_day_boundaries(self):
        slot_values = [0, 1, 12, 13]
        self.assertTrue(is_adjacent_slot_pair(0, 1, slot_values, 12))
        self.assertFalse(is_adjacent_slot_pair(1, 2, slot_values, 12))
        self.assertFalse(is_adjacent_slot_pair(11, 12, slot_values, 12))


if __name__ == "__main__":
    unittest.main()
