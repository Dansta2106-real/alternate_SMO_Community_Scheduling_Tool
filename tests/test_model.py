import sys
import unittest
from pathlib import Path

from ortools.sat.python import cp_model

sys.path.append(str(Path(__file__).resolve().parents[1]))

from model import build_model


class ModelTests(unittest.TestCase):
    def test_center_slots_are_preferred_over_edges(self):
        match_data = [
            {
                "runner1": "RunnerA",
                "runner2": "RunnerB",
                "r1_slots": {0, 1, 2},
                "r2_slots": {0, 1, 2},
                "r1_preferred": {0, 1, 2},
                "r2_preferred": {0, 1, 2},
                "possible_slots": [0, 1, 2],
            }
        ]

        runner_preferred_slots = {
            "RunnerA": {0, 1, 2},
            "RunnerB": {0, 1, 2},
        }

        model_data = build_model(
            match_data=match_data,
            num_slots=12,
            slots_per_day=3,
            preferred_slots=runner_preferred_slots,
            slot_values=list(range(12)),
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model_data["model"])

        self.assertIn(status, (cp_model.OPTIMAL, cp_model.FEASIBLE))

        race_slot = model_data["race_slot"]
        self.assertEqual(solver.Value(race_slot[0]), 1)

    def test_conflicting_last_slot_availability_stays_feasible(self):
        # Two different races each include a runner only available
        # at slot 14. One race should take slot 14,
        # and the other should fall back to the latest remaining slot.
        match_data = [
            {
                "runner1": "RunnerA",
                "runner2": "RunnerB",
                "r1_slots": {14},
                "r2_slots": {10, 14},
                "r1_preferred": {14},
                "r2_preferred": {10},
                "possible_slots": [10, 14],
            },
            {
                "runner1": "RunnerC",
                "runner2": "RunnerD",
                "r1_slots": {14},
                "r2_slots": {9, 14},
                "r1_preferred": {14},
                "r2_preferred": {9},
                "possible_slots": [9, 14],
            },
        ]

        runner_preferred_slots = {
            "RunnerA": {11},
            "RunnerB": {10},
            "RunnerC": {11},
            "RunnerD": {9},
        }

        model_data = build_model(
            match_data=match_data,
            num_slots=24,
            slots_per_day=24,
            preferred_slots=runner_preferred_slots,
            slot_values=list(range(24)),
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model_data["model"])

        self.assertIn(status, (cp_model.OPTIMAL, cp_model.FEASIBLE))

        race_slot = model_data["race_slot"]
        prerec_flags = model_data["prerec_flags"]

        assigned_slots = {
            solver.Value(race_slot[0]),
            solver.Value(race_slot[1]),
        }

        # The two starts must be at least four hours apart.
        self.assertEqual(assigned_slots, {10, 14})

        # Exactly one of the two "only slot 11" runners should become prerecorded.
        first_only_runner_prerec = solver.Value(prerec_flags[0])
        second_only_runner_prerec = solver.Value(prerec_flags[2])
        self.assertEqual(first_only_runner_prerec + second_only_runner_prerec, 1)

    def test_zero_availability_match_is_scheduled_late(self):
        match_data = [
            {
                "runner1": "NoAvailA",
                "runner2": "NoAvailB",
                "r1_slots": set(),
                "r2_slots": set(),
                "r1_preferred": set(),
                "r2_preferred": set(),
                "possible_slots": [0, 10, 14],
            },
            {
                "runner1": "FixedA",
                "runner2": "FixedB",
                "r1_slots": {14},
                "r2_slots": {14},
                "r1_preferred": {14},
                "r2_preferred": {14},
                "possible_slots": [14],
            },
        ]

        runner_preferred_slots = {
            "NoAvailA": set(),
            "NoAvailB": set(),
            "FixedA": {11},
            "FixedB": {11},
        }

        model_data = build_model(
            match_data=match_data,
            num_slots=24,
            slots_per_day=24,
            preferred_slots=runner_preferred_slots,
            slot_values=list(range(24)),
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model_data["model"])

        self.assertIn(status, (cp_model.OPTIMAL, cp_model.FEASIBLE))

        race_slot = model_data["race_slot"]
        prerec_flags = model_data["prerec_flags"]

        # Slot 14 is occupied by the fixed race; zero-availability race
        # should be placed at the latest remaining compatible slot (10).
        self.assertEqual(solver.Value(race_slot[0]), 10)

        # Zero-availability race is necessarily prerecorded for both runners.
        self.assertEqual(solver.Value(prerec_flags[0]), 1)
        self.assertEqual(solver.Value(prerec_flags[1]), 1)

        # The fixed race stays non-prerecorded; no extra prerecords added.
        self.assertEqual(solver.Value(prerec_flags[2]), 0)
        self.assertEqual(solver.Value(prerec_flags[3]), 0)


if __name__ == "__main__":
    unittest.main()