# M.Tech Supervisor Allocation

A stateless supervisor-allocation app: FastAPI and Pandas process uploaded CSVs in memory, React provides the admin dashboard, and PostgreSQL stores only the faculty catalogue.

## Features

- Faculty catalogue seeded with the 18 supplied CSE faculty choices.
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
2. Start PostgreSQL, then start the API:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn backend.app.main:app --reload
   ```

3. In another terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

The Vite development server proxies `/api` requests to `http://localhost:8000`. The API creates only the `faculty` table and idempotently seeds the supplied faculty names at startup.

## CSV format

The input file must have these headers:

`Email, Roll Number, Name, GATE Score, GATE Marks, Subject 1, Subject 2, Subject 3, Subject 4, Choice 1, Choice 2, Choice 3, Choice 4`

Scores and marks must be numeric when present. Blank marks count as zero for selected score components. A blank or unrecognized faculty choice is skipped; choices are matched to faculty names exactly after trimming surrounding whitespace. Roll numbers must be unique within an upload.

For phase two, upload the pending students with their revised choices and the downloaded phase-one **Final Allocation List**. The allocation file includes faculty IDs so capacity can be recovered without saving phase-one state on the server. Students already in that file cannot be allocated again.

## Deployment

The root `vercel.json` is configured to build the Vite frontend and route `/api/*` to the FastAPI function in `api/index.py`. Deploy the repository as a Vercel project and set the `DATABASE_URL` environment variable in the Vercel project settings. Use a hosted PostgreSQL service reachable from Vercel; do not point it at a local database.

The GitHub repository and Vercel project must be created under an account with the appropriate access. This workspace has no configured remote or deployment credentials; after implementation, connect the repository to GitHub and import it into Vercel.

## Data handling

Student CSV contents are read into memory to validate, score, allocate, and build the response/download CSVs. They are not written to disk, logged, cached, or inserted into PostgreSQL. Only `faculty` rows are persisted.
