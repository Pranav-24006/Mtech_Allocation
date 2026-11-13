import unittest
from io import StringIO

import pandas as pd
from fastapi import HTTPException

from backend.app.allocation import allocate_phase_one, allocate_phase_two


FACULTY = [
    {"faculty_id": 1, "name": "Faculty A", "specialization": "Not specified", "max_capacity": 2},
    {"faculty_id": 2, "name": "Faculty B", "specialization": "Not specified", "max_capacity": 2},
]
CSV_COLUMNS = [
    "Email",
    "Roll Number",
    "Name",
    "GATE Score",
    "GATE Marks",
    "Subject 1",
    "Subject 2",
    "Subject 3",
    "Subject 4",
    "Choice 1",
    "Choice 2",
    "Choice 3",
    "Choice 4",
]


def student(roll, gate_score, gate_marks, choices, name=None):
    return {
        "Email": f"{roll.lower()}@example.test",
        "Roll Number": roll,
        "Name": name or roll,
        "GATE Score": gate_score,
        "GATE Marks": gate_marks,
        "Subject 1": 10,
        "Subject 2": 10,
        "Subject 3": 10,
        "Subject 4": 10,
        **{f"Choice {index + 1}": choices[index] if index < len(choices) else "" for index in range(4)},
    }


def csv_bytes(rows):
    output = StringIO()
    pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


class AllocationTests(unittest.TestCase):
    def test_four_rounds_fill_capacity_in_merit_order_and_ignore_unknown_names(self):
        rows = [
            student("S1", 900, 90, ["Faculty A"]),
            student("S2", 800, 90, ["Faculty A"]),
            student("S3", 700, 90, ["Faculty A", "Faculty B"]),
            student("S4", 600, 90, ["Faculty A", "Faculty A", "Faculty B"]),
            student("S5", 500, 90, ["Unknown Faculty"]),
        ]

        result = allocate_phase_one(
            csv_bytes(rows),
            "students.csv",
            FACULTY,
            True,
            False,
            [],
        )

        assigned = {row["Roll Number"]: row["Assigned Faculty"] for row in result["allocations"]}
        self.assertEqual(assigned, {"S1": "Faculty A", "S2": "Faculty A", "S3": "Faculty B", "S4": "Faculty B"})
        self.assertEqual([row["Roll Number"] for row in result["pending"]], ["S5"])
        self.assertEqual(result["faculty_status"][0]["Remaining Slots"], 0)
        self.assertEqual(result["faculty_status"][1]["Remaining Slots"], 0)

    def test_gate_score_breaks_ties_and_selected_subjects_contribute(self):
        rows = [
            student("LOW", 700, 80, ["Faculty A"]),
            student("HIGH", 800, 90, ["Faculty A"]),
        ]
        rows[0]["Subject 1"] = 20
        rows[1]["Subject 1"] = 10
        result = allocate_phase_one(
            csv_bytes(rows),
            "students.csv",
            FACULTY,
            False,
            True,
            ["Subject 1"],
        )

        scores = {row["Roll Number"]: row["Total Score"] for row in result["allocations"]}
        self.assertEqual(scores, {"LOW": 100, "HIGH": 100})
        self.assertEqual(result["allocations"][0]["Roll Number"], "HIGH")

    def test_phase_two_subtracts_phase_one_capacity_and_merges_allocations(self):
        phase_one = allocate_phase_one(
            csv_bytes([
                student("FIRST-A", 900, 80, ["Faculty A"]),
                student("FIRST-B", 850, 80, ["Faculty A"]),
                student("FIRST-C", 800, 80, ["Faculty B"]),
            ]),
            "students.csv",
            FACULTY,
            True,
            False,
            [],
        )
        phase_one_bytes = phase_one["downloads"]["allocations"].encode("utf-8")
        phase_two = allocate_phase_two(
            csv_bytes([
                student("NEXT", 800, 80, ["Faculty A", "Faculty B"]),
                student("LAST", 700, 80, ["Faculty A"]),
            ]),
            "pending.csv",
            phase_one_bytes,
            "phase-one.csv",
            FACULTY,
            True,
            False,
            [],
        )

        self.assertEqual(phase_two["metrics"]["allocated"], 4)
        self.assertEqual(phase_two["metrics"]["pending"], 1)
        self.assertEqual(
            {row["Roll Number"] for row in phase_two["allocations"]},
            {"FIRST-A", "FIRST-B", "FIRST-C", "NEXT"},
        )
        self.assertEqual(phase_two["faculty_status"][0]["Assigned Count"], 2)
        self.assertEqual(phase_two["faculty_status"][1]["Assigned Count"], 2)

    def test_duplicate_roll_numbers_are_rejected(self):
        rows = [student("DUP", 800, 80, ["Faculty A"]), student("DUP", 700, 70, ["Faculty B"])]
        with self.assertRaises(HTTPException):
            allocate_phase_one(csv_bytes(rows), "students.csv", FACULTY, True, True, [])

    def test_phase_two_accepts_a_header_only_phase_one_allocation_csv(self):
        first_run = allocate_phase_one(
            csv_bytes([student("WAITING", 800, 80, ["Unlisted Faculty"])]),
            "students.csv",
            FACULTY,
            True,
            False,
            [],
        )
        result = allocate_phase_two(
            csv_bytes([student("WAITING", 800, 80, ["Faculty A"])]),
            "pending.csv",
            first_run["downloads"]["allocations"].encode("utf-8"),
            "empty-phase-one.csv",
            FACULTY,
            True,
            False,
            [],
        )

        self.assertEqual(result["metrics"]["allocated"], 1)
        self.assertEqual(result["allocations"][0]["Roll Number"], "WAITING")


if __name__ == "__main__":
    unittest.main()
