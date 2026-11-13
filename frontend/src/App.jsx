import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  Check,
  ChevronDown,
  CircleHelp,
  FileSpreadsheet,
  GraduationCap,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
  Users,
} from "lucide-react";

const SUBJECTS = ["Subject 1", "Subject 2", "Subject 3", "Subject 4"];

function downloadCsv(filename, contents) {
  const blob = new Blob([contents], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function appendScoring(form, scoring) {
  form.append("include_gate_score", String(scoring.gateScore));
  form.append("include_gate_marks", String(scoring.gateMarks));
  scoring.subjects.forEach((subject) => form.append("selected_subjects", subject));
}

async function readApiResponse(response, fallbackMessage) {
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(`${fallbackMessage} (HTTP ${response.status}).`);
  }
  if (!response.ok) throw new Error(body.detail || fallbackMessage);
  return body;
}

function formatScore(value) {
  const score = Number(value);
  return Number.isFinite(score) ? score.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—";
}

function UploadCard({ title, description, file, onChange, inputId }) {
  return (
    <label htmlFor={inputId} className="upload-zone group">
      <input
        id={inputId}
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <span className="upload-icon"><FileSpreadsheet size={20} /></span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-muted">
          {file ? file.name : description}
        </span>
      </span>
      <span className="shrink-0 rounded-lg border border-line bg-white px-3 py-2 text-xs font-semibold text-brand transition group-hover:border-brand">
        {file ? "Change" : "Choose CSV"}
      </span>
    </label>
  );
}

function MetricCard({ label, value, caption, icon: Icon, tone = "green" }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={19} /></div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-muted">{label}</p>
        <p className="mt-1 text-2xl font-bold tracking-tight text-ink">{value ?? "—"}</p>
        <p className="mt-1 text-xs text-muted">{caption}</p>
      </div>
    </div>
  );
}

function CsvButton({ label, filename, contents }) {
  return (
    <button
      type="button"
      className="button-secondary"
      disabled={!contents}
      onClick={() => downloadCsv(filename, contents)}
    >
      <ArrowDownToLine size={16} />
      {label}
    </button>
  );
}

function StudentTable({ rows, pending = false }) {
  if (!rows?.length) {
    return (
      <div className="empty-state">
        {pending ? "No students are pending." : "Run an allocation to see student results."}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Roll number</th>
            <th>Student</th>
            <th className="text-right">Total score</th>
            {!pending && <th>Assigned faculty</th>}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 8).map((student, index) => (
            <tr key={`${student["Roll Number"]}-${index}`}>
              <td className="font-medium text-ink">{student["Roll Number"]}</td>
              <td>{student.Name}</td>
              <td className="text-right font-semibold text-ink">{formatScore(student["Total Score"])}</td>
              {!pending && (
                <td>
                  {student["Assigned Faculty"] ? (
                    <span className="faculty-pill">{student["Assigned Faculty"]}</span>
                  ) : <span className="text-muted">Pending</span>}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 8 && (
        <p className="border-t border-line px-5 py-3 text-xs text-muted">
          Showing 8 of {rows.length}. Download the CSV for the complete list.
        </p>
      )}
    </div>
  );
}

export default function App() {
  const [faculty, setFaculty] = useState([]);
  const [facultyError, setFacultyError] = useState("");
  const [studentFile, setStudentFile] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [phaseOneFile, setPhaseOneFile] = useState(null);
  const [scoring, setScoring] = useState({ gateScore: true, gateMarks: true, subjects: [] });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [activeTab, setActiveTab] = useState("allocations");

  useEffect(() => {
    fetch("/api/faculty")
      .then(async (response) => {
        const body = await readApiResponse(response, "Could not load faculty catalogue.");
        setFaculty(body.faculty);
      })
      .catch((cause) => setFacultyError(cause.message));
  }, []);

  const selectedSubjectLabel = useMemo(
    () => scoring.subjects.length ? scoring.subjects.join(", ") : "No subject marks",
    [scoring.subjects],
  );

  function toggleSubject(subject) {
    setScoring((current) => ({
      ...current,
      subjects: current.subjects.includes(subject)
        ? current.subjects.filter((item) => item !== subject)
        : [...current.subjects, subject],
    }));
  }

  async function submitAllocation(event) {
    event.preventDefault();
    if (!studentFile) {
      setError("Choose the student CSV before running allocation.");
      return;
    }
    setBusy("phase-one");
    setError("");
    try {
      const form = new FormData();
      form.append("file", studentFile);
      appendScoring(form, scoring);
      const response = await fetch("/api/allocate", { method: "POST", body: form });
      const body = await readApiResponse(response, "Allocation failed.");
      setResult(body);
      setActiveTab("allocations");
    } catch (cause) {
      setError(cause.message || "Allocation failed. Please try again.");
    } finally {
      setBusy("");
    }
  }

  async function submitPhaseTwo(event) {
    event.preventDefault();
    if (!pendingFile || !phaseOneFile) {
      setError("Choose both the revised pending-student CSV and the phase-one allocation CSV.");
      return;
    }
    setBusy("phase-two");
    setError("");
    try {
      const form = new FormData();
      form.append("pending_file", pendingFile);
      form.append("phase_one_file", phaseOneFile);
      appendScoring(form, scoring);
      const response = await fetch("/api/allocate/phase-two", { method: "POST", body: form });
      const body = await readApiResponse(response, "Phase-two allocation failed.");
      setResult(body);
      setActiveTab("allocations");
    } catch (cause) {
      setError(cause.message || "Phase-two allocation failed. Please try again.");
    } finally {
      setBusy("");
    }
  }

  function resetResults() {
    setResult(null);
    setError("");
    setStudentFile(null);
    setPendingFile(null);
    setPhaseOneFile(null);
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
          <a className="flex items-center gap-3" href="/" aria-label="Supervisor Allocation home">
            <span className="brand-mark"><GraduationCap size={23} strokeWidth={2.2} /></span>
            <span>
              <span className="block text-sm font-bold tracking-tight text-ink">Supervisor Allocation</span>
              <span className="mt-0.5 block text-[11px] font-medium text-muted">NIT Durgapur · CSE</span>
            </span>
          </a>
          <div className="hidden items-center gap-2 rounded-full bg-mint px-3 py-1.5 text-xs font-semibold text-brand sm:flex">
            <ShieldCheck size={14} />
            Student data is not stored
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-10">
        <section className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p className="eyebrow">ADMIN WORKSPACE <span className="eyebrow-dot" /></p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-ink sm:text-[38px]">M.Tech allocation</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Match students to supervisors by merit and preference. Uploads and allocation results are processed in memory.
            </p>
          </div>
          {result && (
            <button type="button" className="button-secondary self-start md:self-auto" onClick={resetResults}>
              <RotateCcw size={15} /> Start over
            </button>
          )}
        </section>

        <div className="mb-7 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className="step-chip active"><span>1</span> Merit criteria</span>
          <span className="step-line" />
          <span className={`step-chip ${result ? "active" : ""}`}><span>2</span> Allocation</span>
          <span className="step-line" />
          <span className="step-chip"><span>3</span> Export results</span>
        </div>

        {facultyError && (
          <div className="alert-error mb-6" role="alert">
            <AlertCircle size={18} />
            <span><strong>Faculty catalogue unavailable.</strong> {facultyError} Check the API and PostgreSQL connection.</span>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">PHASE 1</p>
                <h2 className="mt-1 text-lg font-bold text-ink">Upload student records</h2>
                <p className="mt-1 text-sm text-muted">Set the merit score, then allocate across four preferences.</p>
              </div>
              <span className="round-icon"><FileSpreadsheet size={19} /></span>
            </div>
            <form onSubmit={submitAllocation}>
              <div className="space-y-5 p-5 sm:p-6">
                <div>
                  <p className="field-label">Merit score includes</p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <label className="check-card">
                      <input
                        type="checkbox"
                        checked={scoring.gateScore}
                        onChange={(event) => setScoring({ ...scoring, gateScore: event.target.checked })}
                      />
                      <span className="check-box"><Check size={13} /></span>
                      <span className="flex-1 text-sm font-medium">GATE Score <small className="block text-xs font-normal text-muted">out of 1000</small></span>
                    </label>
                    <label className="check-card">
                      <input
                        type="checkbox"
                        checked={scoring.gateMarks}
                        onChange={(event) => setScoring({ ...scoring, gateMarks: event.target.checked })}
                      />
                      <span className="check-box"><Check size={13} /></span>
                      <span className="flex-1 text-sm font-medium">GATE Marks <small className="block text-xs font-normal text-muted">out of 100</small></span>
                    </label>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <p className="field-label">Subject marks to sum</p>
                    <span className="text-xs text-muted">{selectedSubjectLabel}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {SUBJECTS.map((subject) => (
                      <label key={subject} className="subject-choice">
                        <input
                          type="checkbox"
                          checked={scoring.subjects.includes(subject)}
                          onChange={() => toggleSubject(subject)}
                        />
                        <span className="check-box"><Check size={13} /></span>
                        <span>{subject}</span>
                      </label>
                    ))}
                  </div>
                  <p className="mt-2 flex gap-1.5 text-xs leading-5 text-muted">
                    <CircleHelp className="mt-0.5 shrink-0" size={14} />
                    Only selected columns contribute, equally for every student. Blank marks count as zero.
                  </p>
                </div>
                <UploadCard
                  title="Student preferences"
                  description="CSV with student details, marks, and Choice 1–4"
                  file={studentFile}
                  onChange={setStudentFile}
                  inputId="students-csv"
                />
                {error && <div className="inline-error" role="alert"><AlertCircle size={15} />{error}</div>}
                <button className="button-primary w-full" type="submit" disabled={Boolean(busy) || Boolean(facultyError)}>
                  {busy === "phase-one" ? <LoaderCircle className="animate-spin" size={17} /> : <Check size={17} />}
                  {busy === "phase-one" ? "Allocating students…" : "Run phase-one allocation"}
                </button>
              </div>
            </form>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">PHASE 2</p>
                <h2 className="mt-1 text-lg font-bold text-ink">Re-allocate pending students</h2>
                <p className="mt-1 text-sm text-muted">Continue with new preferences and phase-one capacity.</p>
              </div>
              <span className="round-icon amber"><RotateCcw size={18} /></span>
            </div>
            <form onSubmit={submitPhaseTwo}>
              <div className="space-y-4 p-5 sm:p-6">
                <UploadCard
                  title="Revised pending-student CSV"
                  description="Pending students with their new Choice 1–4"
                  file={pendingFile}
                  onChange={setPendingFile}
                  inputId="pending-csv"
                />
                <UploadCard
                  title="Phase-one allocation CSV"
                  description="The Final Allocation List export, including faculty_id"
                  file={phaseOneFile}
                  onChange={setPhaseOneFile}
                  inputId="phase-one-csv"
                />
                <div className="info-note">
                  <CircleHelp size={16} />
                  <p>Phase two uses the same merit criteria above and subtracts phase-one assignments from faculty capacity.</p>
                </div>
                <button className="button-secondary w-full justify-center" type="submit" disabled={Boolean(busy) || Boolean(facultyError)}>
                  {busy === "phase-two" ? <LoaderCircle className="animate-spin" size={17} /> : <RotateCcw size={16} />}
                  {busy === "phase-two" ? "Re-allocating…" : "Run phase-two allocation"}
                </button>
              </div>
            </form>
          </section>
        </div>

        <section className="mt-6 panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">FACULTY CATALOGUE</p>
              <h2 className="mt-1 text-lg font-bold text-ink">Supervisors &amp; capacity</h2>
              <p className="mt-1 text-sm text-muted">{faculty.length} faculty members · default capacity of 2 each</p>
            </div>
            <span className="round-icon"><Users size={19} /></span>
          </div>
          {faculty.length > 0 ? (
            <details className="faculty-details">
              <summary>
                <span>View faculty list</span>
                <ChevronDown size={16} />
              </summary>
              <div className="faculty-grid">
                {faculty.map((person) => (
                  <div className="faculty-item" key={person.faculty_id}>
                    <span className="faculty-number">{String(person.faculty_id).padStart(2, "0")}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-ink">{person.name}</span>
                      <span className="block text-xs text-muted">{person.specialization}</span>
                    </span>
                    <span className="capacity-tag">{person.max_capacity} slots</span>
                  </div>
                ))}
              </div>
            </details>
          ) : !facultyError ? <div className="px-6 pb-6 text-sm text-muted">Loading faculty catalogue…</div> : null}
        </section>

        <section className="mt-8" aria-live="polite">
          <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
            <div>
              <p className="section-kicker">ALLOCATION RESULTS</p>
              <h2 className="mt-1 text-xl font-bold text-ink">Dashboard</h2>
            </div>
            {result && (
              <div className="flex flex-wrap gap-2">
                <CsvButton label="Allocations CSV" filename="final-allocation-list.csv" contents={result.downloads.allocations} />
                <CsvButton label="Pending CSV" filename="pending-students.csv" contents={result.downloads.pending} />
                <CsvButton label="Faculty status CSV" filename="faculty-status.csv" contents={result.downloads.faculty_status} />
              </div>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Students processed" value={result?.metrics.total_students} caption="In this allocation run" icon={Users} />
            <MetricCard label="Allocated" value={result?.metrics.allocated} caption="Assigned to a supervisor" icon={Check} />
            <MetricCard label="Pending" value={result?.metrics.pending} caption="No available choice matched" icon={CircleHelp} tone="amber" />
            <MetricCard label="Available slots" value={result?.metrics.available_slots} caption="Remaining faculty capacity" icon={GraduationCap} tone="blue" />
          </div>
          <div className="mt-5 panel">
            <div className="results-toolbar">
              <div className="tab-list" role="tablist" aria-label="Allocation result views">
                <button className={`result-tab ${activeTab === "allocations" ? "selected" : ""}`} onClick={() => setActiveTab("allocations")} role="tab">
                  Final allocations <span>{result?.metrics.allocated ?? 0}</span>
                </button>
                <button className={`result-tab ${activeTab === "pending" ? "selected" : ""}`} onClick={() => setActiveTab("pending")} role="tab">
                  Pending <span>{result?.metrics.pending ?? 0}</span>
                </button>
                <button className={`result-tab ${activeTab === "faculty" ? "selected" : ""}`} onClick={() => setActiveTab("faculty")} role="tab">
                  Faculty status
                </button>
              </div>
            </div>
            {activeTab === "faculty" ? (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr><th>Faculty</th><th className="text-right">Assigned</th><th className="text-right">Remaining slots</th></tr></thead>
                  <tbody>
                    {(result?.faculty_status ?? []).map((person) => (
                      <tr key={person.faculty_id}>
                        <td className="font-medium text-ink">{person.Faculty}</td>
                        <td className="text-right">{person["Assigned Count"]}</td>
                        <td className="text-right font-semibold text-brand">{person["Remaining Slots"]}</td>
                      </tr>
                    ))}
                    {!result && <tr><td colSpan="3" className="py-12 text-center text-muted">Run an allocation to view faculty capacity.</td></tr>}
                  </tbody>
                </table>
              </div>
            ) : (
              <StudentTable rows={activeTab === "pending" ? result?.pending : result?.allocations} pending={activeTab === "pending"} />
            )}
          </div>
        </section>

        <footer className="mt-8 flex flex-col gap-2 border-t border-line py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-1.5"><ShieldCheck size={14} className="text-brand" />Student records are processed in memory and not saved.</span>
          <span>Merit order: Total Score, then GATE Score.</span>
        </footer>
      </main>
    </div>
  );
}
