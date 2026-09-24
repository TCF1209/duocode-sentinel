/**
 * Typed client for the Sentinel FastAPI backend (backend/api).
 *
 * Shapes here mirror backend/sdoc/schema.py's `to_report()` / `to_submission()`
 * and backend/api/store.py exactly — this file has no independent opinion
 * about what a case or a run looks like. If the backend shape changes, this
 * is the one file that needs to change with it.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_SENTINEL_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type Category = "BL_COMPARISON" | "SI_REQUEST" | "INVOICE_QUERY" | "GENERAL" | "SPAM";
export type CaseStatus = "OK" | "MISMATCH" | "NEEDS_REVIEW";
export type ReviewReason = "wrong_doc_type" | "missing_attachment" | "unreadable" | "missing_value";
export type DecidedBy = "rule" | "llm";
export type Verdict = "MATCH" | "MISMATCH" | "UNCOMPARABLE";

export interface Evidence {
  doc: string;
  locator: string;
  label: string;
  snippet: string;
}

export interface FieldValueReport {
  raw: string | null;
  normalised: string | null;
  present: boolean;
  blank: boolean;
  extractor: "rule" | "llm" | "ocr";
  evidence: Evidence | null;
}

export interface FieldComparisonReport {
  field: string;
  verdict: Verdict;
  reason: string | null;
  si: FieldValueReport;
  bl: FieldValueReport;
}

export interface DocumentReport {
  path: string;
  ext: string;
  doc_type: string;
  readable: boolean;
  unreadable_reason: string | null;
  n_bytes: number;
  notes: string[];
}

export interface ReviewRecord {
  decision: "confirm" | "correct";
  status: CaseStatus;
  defect_fields: string[];
  note: string | null;
  reviewer: string | null;
  reviewed_at: number;
}

export interface CaseReport {
  email_id: string;
  /** The inbox record's own "from" address, empty on /compare (no email
   *  there — a direct upload). Never sent anywhere by Sentinel itself; a
   *  mailto: link is as far as this goes. */
  sender: string;
  category: Category;
  category_confidence: number;
  decided_by: DecidedBy;
  category_rationale: string[];
  status: CaseStatus;
  review_reason: ReviewReason | null;
  has_defect: boolean;
  defect_fields: string[];
  fields: FieldComparisonReport[];
  documents: { si: DocumentReport | null; bl: DocumentReport | null };
  notes: string[];
  errors: string[];
  duration_ms: number;
  llm_calls: number;
  review?: ReviewRecord | null;
  /** /compare only: whether the model tier was offered, and whether any field
   *  actually came back from it. */
  model_offered?: boolean;
  model_used?: boolean;
  /** What the case is NOW, after any human correction. The keys above stay
   *  the system's own answer, so a card can show both. */
  effective?: EffectiveOutcome | null;
  /** Re-checks on re-sent documents (POST /cases/{id}/recheck). `recheck` is
   *  null and `history` empty for a case whose documents were never re-sent
   *  -- the overwhelming majority -- and both are absent on /compare. */
  recheck?: RecheckInfo | null;
  history?: CaseVersion[];
}

export interface EffectiveOutcome {
  status: CaseStatus;
  review_reason: ReviewReason | null;
  has_defect: boolean;
  defect_fields: string[];
  /** "system" until a reviewer corrects it, then "review". */
  source: "system" | "review";
  reviewed: boolean;
  review_decision: "confirm" | "correct" | null;
}

export type DocSide = "si" | "bl";

/** Where each side of the case is currently read from: the run's own file on
 *  disk ("original"), a re-sent copy held by the API ("resent"), or nothing
 *  at all (the email never carried that document and none was re-sent). */
export interface RecheckInfo {
  count: number;
  /** Epoch seconds, as the backend's time.time() writes it. */
  last_at: number;
  last_resubmitted: DocSide[];
  sources: Record<DocSide, "original" | "resent" | null>;
}

/** One superseded answer, kept when a re-check replaced it. `version` 1 is
 *  what the run itself decided; the review is whatever stood against that
 *  version at the time (it is reset by the re-check), and `effective` is what
 *  the case was then, review included -- reported the same way the live
 *  case is, so "was X, now Y" compares like with like. */
export interface CaseVersion {
  version: number;
  /** Epoch seconds. */
  replaced_at: number;
  /** Which sides the re-check that replaced this version re-sent. */
  resubmitted: DocSide[];
  uploaded: Partial<Record<DocSide, string>>;
  report: CaseReport;
  review: ReviewRecord | null;
  effective: EffectiveOutcome;
}

export interface CaseSummary {
  case_id: string;
  email_id: string;
  /** The inbox record's own "from" address. See CaseReport.sender. */
  sender: string;
  category: Category;
  category_confidence: number;
  /** The effective status — a corrected case leaves the queue it was in. */
  status: CaseStatus;
  review_reason: ReviewReason | null;
  has_defect: boolean;
  defect_fields: string[];
  /** The shipper's name, read off whichever side of the comparison has it.
   *  `null` when the field was never extracted (e.g. an escalated case with
   *  no readable SI or BL). */
  shipper: string | null;
  decided_by: DecidedBy;
  reviewed: boolean;
  outcome_source: "system" | "review";
  /** What Sentinel itself said, kept beside the effective status so a row a
   *  person overrode does not look like a row we got right. */
  system_status: CaseStatus;
  /** How many times this case was re-checked on re-sent documents; 0 for
   *  almost every row. See CaseReport.recheck. */
  recheck_count: number;
}

export interface RunStatus {
  run_id: string;
  status: "running" | "done" | "failed";
  total_emails: number;
  processed: number;
  llm_enabled: boolean;
  error: string | null;
  metrics: PipelineMetrics | null;
}

export interface PipelineMetrics {
  emails: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  by_review_reason: Record<string, number>;
  decided_by_rule: number;
  decided_by_llm: number;
  rule_share: number;
  documents_read: number;
  documents_unreadable: number;
  llm_calls: number;
  total_ms: number;
  mean_ms_per_email: number;
  llm?: { available: boolean; [k: string]: unknown };
  /** What humans did to this run, reported beside what Sentinel did rather
   *  than folded into it (backend/api/main.py's /metrics): a person
   *  confirming a case afterwards must not retro-improve the pipeline's own
   *  numbers. Present on GET /metrics for a run; absent in the bare pipeline
   *  metrics shape. */
  review?: { reviewed: number; confirmed: number; corrected: number };
  /** Cases re-checked on re-sent documents, and how many re-checks in all --
   *  the other thing a person can do to a run after it finished. */
  recheck?: { cases: number; rechecks: number };
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.body ? { "content-type": "application/json" } : {}), ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {
      // body was not JSON; use it verbatim
    }
    throw new ApiError(res.status, detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

export { ApiError };

export function createRun(opts: { limit?: number; use_llm?: boolean } = {}) {
  return request<{ run_id: string }>("/runs", {
    method: "POST",
    body: JSON.stringify({ limit: opts.limit ?? null, use_llm: opts.use_llm ?? true }),
  });
}

export function listRuns() {
  return request<RunStatus[]>("/runs");
}

export function getRun(runId: string) {
  return request<RunStatus>(`/runs/${encodeURIComponent(runId)}`);
}

export function listCases(
  runId: string,
  filters: { category?: string; status?: string; decided_by?: string } = {},
) {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.status) params.set("status", filters.status);
  if (filters.decided_by) params.set("decided_by", filters.decided_by);
  const qs = params.toString();
  return request<{ run_id: string; count: number; cases: CaseSummary[] }>(
    `/runs/${encodeURIComponent(runId)}/cases${qs ? `?${qs}` : ""}`,
  );
}

export function getCase(runId: string, emailId: string) {
  return request<CaseReport>(`/cases/${encodeURIComponent(runId)}:${encodeURIComponent(emailId)}`);
}

/** A direct link to the original SI or BL file a run read off disk, for an
 *  `<a href>` -- never fetched with `request()`, since the point is letting
 *  the browser open or download the raw bytes itself, not JSON. Only ever
 *  valid for a case that came from a run (`caseId` is `<run_id>:<email_id>`);
 *  /compare holds its upload in memory and writes nothing, so there is
 *  nothing this could point at there (backend/api/main.py's own docstring
 *  on this route says the same). */
export function attachmentUrl(caseId: string, side: DocSide, version?: number): string {
  const base = `${API_BASE}/cases/${encodeURIComponent(caseId)}/attachments/${side}`;
  // `version` names a superseded answer (CaseVersion.version): the file that
  // side was read from back then, which after a re-check is not the file the
  // case is read from now. Omitted, the current one.
  return version === undefined ? base : `${base}?version=${version}`;
}

export function reviewCase(
  runId: string,
  emailId: string,
  body: { decision: "confirm" | "correct"; status?: CaseStatus; defect_fields?: string[]; note?: string; reviewer?: string },
) {
  return request<ReviewRecord>(`/cases/${encodeURIComponent(runId)}:${encodeURIComponent(emailId)}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Re-process one email in place. The case keeps its position in the run and
 *  any review recorded against it is left alone — whether the new result still
 *  needs that correction is the reviewer's call. */
export function retryCase(runId: string, emailId: string) {
  return request<CaseReport>(
    `/cases/${encodeURIComponent(runId)}:${encodeURIComponent(emailId)}/retry`,
    { method: "POST" },
  );
}

/** Run the same check again on documents the sender re-sent -- one side or
 *  both; a side not attached keeps the file the case has now. The answer this
 *  replaces goes into the case's `history`, review and all, and the review is
 *  reset (it was about the old documents). Multipart, so not `request()`,
 *  which would stamp a JSON content-type on the body; the error detail is
 *  still unwrapped the same way, because the backend's refusals here are
 *  written for the person reading them ("attach the re-sent SI, the re-sent
 *  BL, or both"). */
export async function recheckCase(runId: string, emailId: string, files: { si?: File; bl?: File }): Promise<CaseReport> {
  const form = new FormData();
  if (files.si) form.set("si", files.si);
  if (files.bl) form.set("bl", files.bl);
  const res = await fetch(
    `${API_BASE}/cases/${encodeURIComponent(runId)}:${encodeURIComponent(emailId)}/recheck`,
    { method: "POST", body: form },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {
      // body was not JSON; use it verbatim
    }
    throw new ApiError(res.status, detail || res.statusText);
  }
  return res.json();
}

export function getMetrics(runId?: string) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<PipelineMetrics & { run_id: string }>(`/metrics${qs}`);
}

export function getSubmission(runId?: string) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<Record<string, { category: string; status: string; review_reason: string | null; defect_fields: string[]; has_defect: boolean; decided_by: string }>>(
    `/submission${qs}`,
  );
}

export async function compareUploads(si: File, bl: File, useLlm = false): Promise<CaseReport> {
  const form = new FormData();
  form.set("si", si);
  form.set("bl", bl);
  const res = await fetch(`${API_BASE}/compare?use_llm=${useLlm}`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json();
}
