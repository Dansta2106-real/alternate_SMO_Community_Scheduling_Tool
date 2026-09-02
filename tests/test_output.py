import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from output import display_solutions


class OutputTests(unittest.TestCase):
    def test_empty_warning_cell_is_written_as_nothing(self):
        solutions = [
            {
                "data": [
                    {
                        "race": 0,
                        "slot": 0,
                        "p1_prerec": False,
                        "p2_prerec": False,
                    }
                ]
            }
        ]

        match_data = [
            {
                "runner1": "RunnerOne",
                "runner2": "RunnerTwo",
                "r1_slots": {0},
                "r2_slots": {0},
                "r1_preferred": {0},
                "r2_preferred": {0},
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "schedule.csv"

            with redirect_stdout(io.StringIO()):
                display_solutions(
                    solutions,
                    match_data,
                    [0],
                    lambda slot: f"Slot {slot}",
                    slots_per_day=1,
                    output_file=str(output_path),
                    runner_preferred_slots={"RunnerOne": {0}, "RunnerTwo": {0}},
                )

            saved = pd.read_csv(output_path)

        self.assertEqual(saved.loc[0, "warning"], "Nothing")

    def test_flags_missing_runner_availability_in_warning_column(self):
        solutions = [
            {
                "data": [
                    {
                        "race": 0,
                        "slot": 0,
                        "p1_prerec": False,
                        "p2_prerec": False,
                    }
                ]
            }
        ]

        match_data = [
            {
                "runner1": "MissingRunner",
                "runner2": "RunnerTwo",
                "r1_slots": set(),
                "r2_slots": {0},
                "r1_preferred": set(),
                "r2_preferred": {0},
                "missing_availability_runners": ["MissingRunner"],
            }
        ]

        all_slots = [0]

        def fake_display_time(slot_value):
            return f"Slot {slot_value}"

        runner_preferred_slots = {
            "MissingRunner": set(),
            "RunnerTwo": {0},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "schedule.csv"

            with redirect_stdout(io.StringIO()):
                display_solutions(
                    solutions,
                    match_data,
                    all_slots,
                    fake_display_time,
                    slots_per_day=1,
                    output_file=str(output_path),
                    runner_preferred_slots=runner_preferred_slots,
                )

            saved = pd.read_csv(output_path)

        self.assertEqual(
            saved.loc[0, "warning"],
            "MissingRunner has not submitted availabilities",
        )

    def test_flags_prerecord_at_or_before_first_available_slot(self):
        solutions = [
            {
                "data": [
                    {
                        "race": 0,
                        "slot": 1,
                        "p1_prerec": True,
                        "p2_prerec": False,
                    }
                ]
            }
        ]

        match_data = [
            {
                "runner1": "RunnerOne",
                "runner2": "RunnerTwo",
                "r1_slots": {2},
                "r2_slots": {0, 1},
                "r1_preferred": {2},
                "r2_preferred": {0},
            }
        ]

        all_slots = [0, 1, 2]

        def fake_display_time(slot_value):
            return f"Slot {slot_value}"

        runner_preferred_slots = {
            "RunnerOne": {0},
            "RunnerTwo": {0},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "schedule.csv"

            stdout = io.StringIO()

            with redirect_stdout(stdout):
                display_solutions(
                    solutions,
                    match_data,
                    all_slots,
                    fake_display_time,
                    slots_per_day=1,
                    output_file=str(output_path),
                    runner_preferred_slots=runner_preferred_slots,
                )

            saved = pd.read_csv(output_path)

        text = stdout.getvalue()

        self.assertIn("FIRST-SLOT PRERECORD VIOLATION", text)
        self.assertIn("RunnerOne", text)
        self.assertIn("warning", saved.columns)
        self.assertEqual(saved.loc[0, "warning"], "Prerecord before first available slot")


if __name__ == "__main__":
    unittest.main()
