# M.Tech Supervisor Allocation

A stateless supervisor-allocation app: FastAPI and Pandas process uploaded CSVs in memory, React provides the admin dashboard, and PostgreSQL stores only the faculty catalogue.

## Features

- Faculty catalogue synchronized with the 41 present faculty listed by the [official NIT Durgapur CSE directory](https://nitdgp.ac.in/department/computer-science-engineering/faculty-1). The directory's official name labels are used without titles.
- CSV validation and exact faculty-name-to-ID resolution (no fuzzy matching).
- Configurable merit total: choose GATE Score, GATE Marks, and any subset of the four subject columns. The same selected subject columns are summed for every student.
- Four preference rounds, ranking by total merit and then GATE Score.
- Phase-two allocation against capacity left by the uploaded phase-one allocation CSV.
- In-memory CSV downloads for allocations, pending students, and faculty status.
- No student, preference, or allocation tables; no upload or result files are persisted.

## Requirements

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+

## Local setup

1. Copy `.env.example` to `.env` and set `DATABASE_URL` to a PostgreSQL connection string.
2. To run the API locally, start PostgreSQL and configure `DATABASE_URL`, then start the API:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn backend.app.main:app --reload
   ```

3. In another terminal, start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

The Vite development server proxies `/api` requests to the deployed API at `https://mtech-allocation.vercel.app` by default, so the local preview works without a local database. Student CSV uploads from this preview are sent to the hosted API for in-memory processing. To use a local API instead, set `API_PROXY_TARGET=http://localhost:8000` before starting Vite and start the backend as above. The API creates only the `faculty` table and synchronizes its rows with the official present-faculty roster at startup. Existing IDs are preserved when an existing seed name is renamed to its official directory name; non-current seed rows are removed.

## CSV format

The input file must have these headers:

`Email, Roll Number, Name, GATE Score, GATE Marks, Subject 1, Subject 2, Subject 3, Subject 4, Choice 1, Choice 2, Choice 3, Choice 4`

Scores and marks must be numeric when present. Blank marks count as zero for selected score components. A blank or unrecognized faculty choice is skipped; choices are matched to faculty names exactly after trimming surrounding whitespace. Roll numbers must be unique within an upload.

For phase two, upload the pending students with their revised choices and the downloaded phase-one **Final Allocation List**. The allocation file includes faculty IDs so capacity can be recovered without saving phase-one state on the server. Students already in that file cannot be allocated again.

## Deployment

The root `vercel.json` builds the Vite frontend from `frontend/`, serves it from `frontend/dist`, and routes `/api/*` to the FastAPI function in `api/index.py`. Import the repository as a single Vercel project and set `DATABASE_URL` in the project environment variables. Use a hosted PostgreSQL service reachable from Vercel; do not point it at a local database.

Source repository: <https://github.com/Pranav-24006/Mtech_Allocation>. The Vercel GitHub App must have access to this repository before importing it. Add a hosted PostgreSQL connection as the Vercel `DATABASE_URL` environment variable before using the deployed API.

## Data handling

Student CSV contents are read into memory to validate, score, allocate, and build the response/download CSVs. They are not written to disk, logged, cached, or inserted into PostgreSQL. Only `faculty` rows are persisted.
