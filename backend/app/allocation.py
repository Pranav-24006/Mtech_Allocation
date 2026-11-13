from __future__ import annotations

from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from fastapi import HTTPException


REQUIRED_COLUMNS = [
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
STUDENT_COLUMNS = ["Email", "Roll Number", "Name", "GATE Score", "GATE Marks"]
SUBJECT_COLUMNS = [f"Subject {number}" for number in range(1, 5)]
CHOICE_COLUMNS = [f"Choice {number}" for number in range(1, 5)]


def _read_csv(contents: bytes, filename: str, allow_empty: bool = False) -> pd.DataFrame:
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    try:
        frame = pd.read_csv(BytesIO(contents), dtype=str, keep_default_na=False)
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise HTTPException(status_code=400, detail="The uploaded CSV could not be read.") from error
    if frame.empty and not allow_empty:
        raise HTTPException(status_code=400, detail="The uploaded CSV has no student rows.")
    return frame


def _validate_students(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required CSV columns: {', '.join(missing)}.",
        )
    result = frame[REQUIRED_COLUMNS].copy()
    for column in ("Email", "Roll Number", "Name"):
        result[column] = result[column].astype(str).str.strip()
        if result[column].eq("").any():
            raise HTTPException(status_code=400, detail=f"{column} cannot be blank.")
    if result["Roll Number"].duplicated().any():
        raise HTTPException(status_code=400, detail="Roll Number values must be unique in the uploaded CSV.")

    for column in ["GATE Score", "GATE Marks", *SUBJECT_COLUMNS]:
        values = result[column].astype(str).str.strip().replace("", "0")
        numeric = pd.to_numeric(values, errors="coerce")
        if numeric.isna().any():
            raise HTTPException(status_code=400, detail=f"{column} must contain numeric values or be blank.")
        if (numeric < 0).any():
            raise HTTPException(status_code=400, detail=f"{column} cannot be negative.")
        maximum = 1000 if column == "GATE Score" else 100 if column == "GATE Marks" else 25
        if (numeric > maximum).any():
            raise HTTPException(status_code=400, detail=f"{column} cannot exceed {maximum}.")
        result[column] = numeric

    for column in CHOICE_COLUMNS:
        result[column] = result[column].astype(str).str.strip()
    return result


def _faculty_lookup(faculty: list[dict[str, Any]]) -> tuple[dict[str, int], dict[int, str]]:
    name_to_id = {str(item["name"]): int(item["faculty_id"]) for item in faculty}
    id_to_name = {int(item["faculty_id"]): str(item["name"]) for item in faculty}
    return name_to_id, id_to_name


def _build_score(
    students: pd.DataFrame,
    include_gate_score: bool,
    include_gate_marks: bool,
    selected_subjects: list[str],
) -> pd.Series:
    valid_subjects = set(SUBJECT_COLUMNS)
    if len(set(selected_subjects)) != len(selected_subjects) or not set(selected_subjects).issubset(valid_subjects):
        raise HTTPException(status_code=400, detail="Select valid subject columns without duplicates.")
    if not include_gate_score and not include_gate_marks and not selected_subjects:
        raise HTTPException(status_code=400, detail="Select at least one merit-score component.")

    score = pd.Series(0.0, index=students.index)
    if include_gate_score:
        score += students["GATE Score"]
    if include_gate_marks:
        score += students["GATE Marks"]
    for subject in selected_subjects:
        score += students[subject]
    return score


def _status_rows(
    faculty: list[dict[str, Any]],
    assigned_counts: dict[int, int],
) -> list[dict[str, Any]]:
    return [
        {
            "faculty_id": int(item["faculty_id"]),
            "Faculty": str(item["name"]),
            "Assigned Count": assigned_counts.get(int(item["faculty_id"]), 0),
            "Remaining Slots": max(
                int(item["max_capacity"]) - assigned_counts.get(int(item["faculty_id"]), 0),
                0,
            ),
        }
        for item in faculty
    ]


def _allocate(
    students: pd.DataFrame,
    faculty: list[dict[str, Any]],
    include_gate_score: bool,
    include_gate_marks: bool,
    selected_subjects: list[str],
    prior_allocations: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    name_to_id, id_to_name = _faculty_lookup(faculty)
    scored = _validate_students(students)
    scored["Total Score"] = _build_score(
        scored, include_gate_score, include_gate_marks, selected_subjects
    )
    scored["_source_order"] = range(len(scored))
    scored = scored.sort_values(
        ["Total Score", "GATE Score", "_source_order"],
        ascending=[False, False, True],
        kind="mergesort",
    )

    assigned_by_roll: dict[str, int] = {}
    counts: dict[int, int] = {}
    if prior_allocations is not None:
        required_prior = {"Roll Number", "faculty_id"}
        if not required_prior.issubset(prior_allocations.columns):
            raise HTTPException(
                status_code=400,
                detail="Phase-one allocation CSV must contain Roll Number and faculty_id columns.",
            )
        prior = prior_allocations[["Roll Number", "faculty_id"]].copy()
        prior["Roll Number"] = prior["Roll Number"].astype(str).str.strip()
        if prior["Roll Number"].duplicated().any():
            raise HTTPException(
                status_code=400,
                detail="Phase-one allocation CSV contains duplicate Roll Number values.",
            )
        for row in prior.itertuples(index=False):
            if pd.isna(row.faculty_id) or str(row.faculty_id).strip() == "":
                continue
            try:
                numeric_id = float(row.faculty_id)
            except (TypeError, ValueError) as error:
                raise HTTPException(status_code=400, detail="Phase-one faculty_id values must be integers.") from error
            if not numeric_id.is_integer():
                raise HTTPException(status_code=400, detail="Phase-one faculty_id values must be integers.")
            faculty_id = int(numeric_id)
            if faculty_id not in id_to_name:
                raise HTTPException(
                    status_code=400,
                    detail="Phase-one allocation CSV contains a faculty_id not present in the current catalogue.",
                )
            assigned_by_roll[str(row[0])] = faculty_id
            counts[faculty_id] = counts.get(faculty_id, 0) + 1
        if set(assigned_by_roll).intersection(set(scored["Roll Number"])):
            raise HTTPException(
                status_code=400,
                detail="Phase-two input includes students already allocated in phase one.",
            )
    for item in faculty:
        faculty_id = int(item["faculty_id"])
        if counts.get(faculty_id, 0) > int(item["max_capacity"]):
            raise HTTPException(
                status_code=400,
                detail="Phase-one allocations exceed a faculty member's current capacity.",
            )

    capacities = {
        int(item["faculty_id"]): int(item["max_capacity"])
        for item in faculty
    }
    for choice in CHOICE_COLUMNS:
        available = scored[~scored["Roll Number"].isin(assigned_by_roll)]
        for faculty_name, faculty_id in name_to_id.items():
            remaining = capacities[faculty_id] - counts.get(faculty_id, 0)
            if remaining <= 0:
                continue
            group = available[available[choice] == faculty_name]
            for roll_number in group["Roll Number"].head(remaining):
                assigned_by_roll[roll_number] = faculty_id
                counts[faculty_id] = counts.get(faculty_id, 0) + 1

    result = scored.drop(columns=["_source_order"]).copy()
    result["faculty_id"] = result["Roll Number"].map(assigned_by_roll).astype("Int64")
    result["Assigned Faculty"] = result["faculty_id"].map(
        lambda value: id_to_name.get(int(value), "") if not pd.isna(value) else ""
    )
    result["Status"] = result["faculty_id"].map(lambda value: "Allocated" if not pd.isna(value) else "Pending")
    ordered_columns = [
        "Email",
        "Roll Number",
        "Name",
        "GATE Score",
        "GATE Marks",
        *SUBJECT_COLUMNS,
        *CHOICE_COLUMNS,
        "Total Score",
        "faculty_id",
        "Assigned Faculty",
        "Status",
    ]
    result = result[ordered_columns]
    pending = result[result["Status"] == "Pending"].copy()

    status_counts = counts.copy()
    status = _status_rows(faculty, status_counts)
    if prior_allocations is not None:
        prior_assigned = prior_allocations[prior_allocations["faculty_id"].notna()].copy()
        prior_assigned["faculty_id"] = pd.to_numeric(prior_assigned["faculty_id"], errors="coerce")
        for row in prior_assigned.itertuples(index=False):
            faculty_id = int(row.faculty_id)
            status_counts[faculty_id] = max(status_counts.get(faculty_id, 0), counts.get(faculty_id, 0))
        status = _status_rows(faculty, status_counts)
    return result, pending, status


def _csv_text(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    output = StringIO()
    selected = frame if columns is None else frame[columns]
    selected.to_csv(output, index=False)
    return output.getvalue()


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        records.append(
            {
                key: (
                    ""
                    if pd.isna(value)
                    else value.item()
                    if hasattr(value, "item")
                    else value
                )
                for key, value in row.items()
            }
        )
    return records


def allocate_phase_one(
    contents: bytes,
    filename: str,
    faculty: list[dict[str, Any]],
    include_gate_score: bool,
    include_gate_marks: bool,
    selected_subjects: list[str],
) -> dict[str, Any]:
    students = _validate_students(_read_csv(contents, filename))
    allocations, pending, status = _allocate(
        students,
        faculty,
        include_gate_score,
        include_gate_marks,
        selected_subjects,
    )
    return _result_payload(allocations, pending, status, len(students))


def allocate_phase_two(
    pending_contents: bytes,
    pending_filename: str,
    phase_one_contents: bytes,
    phase_one_filename: str,
    faculty: list[dict[str, Any]],
    include_gate_score: bool,
    include_gate_marks: bool,
    selected_subjects: list[str],
) -> dict[str, Any]:
    pending_students = _validate_students(_read_csv(pending_contents, pending_filename))
    prior_frame = _read_csv(phase_one_contents, phase_one_filename, allow_empty=True)
    phase_two, pending, status = _allocate(
        pending_students,
        faculty,
        include_gate_score,
        include_gate_marks,
        selected_subjects,
        prior_frame,
    )
    prior_allocated = prior_frame.copy()
    if "faculty_id" not in prior_allocated.columns:
        raise HTTPException(
            status_code=400,
            detail="Phase-one allocation CSV must contain a faculty_id column.",
        )
    prior_allocated = prior_allocated[pd.to_numeric(prior_allocated["faculty_id"], errors="coerce").notna()]
    prior_allocated["Status"] = "Allocated"
    newly_allocated = phase_two[phase_two["Status"] == "Allocated"]
    if prior_allocated.empty:
        final = newly_allocated
    elif newly_allocated.empty:
        final = prior_allocated
    else:
        final = pd.concat([prior_allocated, newly_allocated], ignore_index=True)
    pending_columns = [column for column in pending.columns if column != "Status"]
    return _result_payload(final, pending, status, len(final) + len(pending), pending_columns)


def _result_payload(
    allocations: pd.DataFrame,
    pending: pd.DataFrame,
    status: list[dict[str, Any]],
    total_students: int,
    pending_columns: list[str] | None = None,
) -> dict[str, Any]:
    final_allocations = allocations[allocations["Status"] == "Allocated"].copy() if "Status" in allocations else allocations.copy()
    pending_data = pending.copy()
    if "Status" in pending_data:
        pending_data = pending_data.drop(columns=["Status"])
    if pending_columns:
        pending_data = pending_data[pending_columns]
    return {
        "metrics": {
            "total_students": total_students,
            "allocated": len(final_allocations),
            "pending": len(pending_data),
            "available_slots": sum(int(row["Remaining Slots"]) for row in status),
        },
        "allocations": _records(final_allocations),
        "pending": _records(pending_data),
        "faculty_status": status,
        "downloads": {
            "allocations": _csv_text(
                final_allocations,
                [column for column in ["Roll Number", "Name", "Total Score", "faculty_id", "Assigned Faculty"] if column in final_allocations],
            ),
            "pending": _csv_text(pending_data),
            "faculty_status": _csv_text(pd.DataFrame(status), ["Faculty", "Assigned Count", "Remaining Slots"]),
        },
    }
