import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.app.allocation import allocate_phase_one, allocate_phase_two
from backend.app.database import engine, fetch_faculty, initialize_faculty_table


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_faculty_table()
    yield
    engine.dispose()


app = FastAPI(title="M.Tech Supervisor Allocation API", version="1.0.0", lifespan=lifespan)

origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _faculty_or_error() -> list[dict[str, object]]:
    try:
        faculty = fetch_faculty()
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Faculty database is unavailable.") from error
    if not faculty:
        raise HTTPException(status_code=503, detail="Faculty catalogue is empty.")
    return faculty


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/faculty")
def faculty_catalogue() -> dict[str, list[dict[str, object]]]:
    return {"faculty": _faculty_or_error()}


@app.post("/api/allocate")
async def allocate(
    file: Annotated[UploadFile, File()],
    include_gate_score: Annotated[bool, Form()],
    include_gate_marks: Annotated[bool, Form()],
    selected_subjects: Annotated[list[str], Form()] = [],
) -> dict[str, object]:
    faculty = _faculty_or_error()
    contents = await file.read()
    return allocate_phase_one(
        contents,
        file.filename or "",
        faculty,
        include_gate_score,
        include_gate_marks,
        selected_subjects,
    )


@app.post("/api/allocate/phase-two")
async def allocate_again(
    pending_file: Annotated[UploadFile, File()],
    phase_one_file: Annotated[UploadFile, File()],
    include_gate_score: Annotated[bool, Form()],
    include_gate_marks: Annotated[bool, Form()],
    selected_subjects: Annotated[list[str], Form()] = [],
) -> dict[str, object]:
    faculty = _faculty_or_error()
    pending_contents = await pending_file.read()
    phase_one_contents = await phase_one_file.read()
    return allocate_phase_two(
        pending_contents,
        pending_file.filename or "",
        phase_one_contents,
        phase_one_file.filename or "",
        faculty,
        include_gate_score,
        include_gate_marks,
        selected_subjects,
    )
