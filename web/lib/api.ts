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

/** A reviewer's choice on one field, relative to what Sentinel said about
 *  it: a mismatch Sentinel flagged that the reviewer takes off the list
 *  ("cleared"), a field Sentinel passed or could not compare that the
 *  reviewer flags ("flagged"), or an uncomparable field the reviewer has
 *  looked at and is satisfied with ("fine"). */
export type FieldDecision = "flagged" | "cleared" | "fine";

export interface ReviewRecord {
  decision: "confirm" | "correct";
  status: CaseStatus;
  defect_fields: string[];
  note: string | null;
  reviewer: string | null;
  reviewed_at: number;
  /** The per-field choices and corrected values `status` / `defect_fields`
   *  were built from, so the case page can show a saved review as it was
   *  made and change it one choice at a time. Empty (not absent) on a
   *  whole-case review; absent only on a record from before they existed. */
  decisions?: Record<string, FieldDecision>;
  cant_tell?: boolean;
  corrections?: Record<string, FieldCorrection>;
  /** Per corrected field, what the corrected pair got from the same
   *  comparison the run used (backend/api/review_outcome.py). */
  field_verdicts?: Record<string, FieldVerdictReport>;
}

/** The reviewer's value for one or both sides of a field. */
export interface FieldCorrection {
  si?: string;
  bl?: string;
}

export interface FieldVerdictReport {
  verdict: Verdict;
  reason: string | null;
  /** The verdict once the reviewer's one-click choice is applied on top. */
  stands: Verdict;
  si: { raw: string | null; normalised: string | null; corrected: boolean };
  bl: { raw: string | null; normalised: string | null; corrected: boolean };
}

export interface ReviewBody {
  decision: "confirm" | "correct";
  /** The whole-case form sends these; the in-place review sends the
   *  choices and corrections below and the backend derives them. */
  status?: CaseStatus;
  defect_fields?: string[];
  note?: string;
  reviewer?: string;
  decisions?: Record<string, FieldDecision>;
  cant_tell?: boolean;
  corrections?: Record<string, FieldCorrection>;
}

export interface CaseReport {
  email_id: string;
  /** The inbox record's own "from" address, empty on /compare (no email
   *  there — a direct upload). Never sent anywhere by Sentinel itself; a
   *  mailto: link is as far as this goes. */
  sender: string;
  /** The inbox record's subject, so a reply draft threads under it. Empty
   *  on /compare; absent from an API older than the field. */
  subject?: string;
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
  /** The email as it arrived (see CaseSummary.subject). Absent on /compare. */
  inbox?: { subject: string; attachments: string[] };
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
  /** The email as it arrived -- subject line and attachment file names --
   *  for the "Before Sentinel" view. Not pipeline outputs; the API keeps
   *  them beside the case (store.py's inbox_of). */
  subject: string;
  attachments: string[];
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
  /** Sentinel's own discrepant fields. Optional: an API from before the
   *  field leaves it out. */
  system_defect_fields?: string[];
  /** How many times this case was re-checked on re-sent documents; 0 for
   *  almost every row. See CaseReport.recheck. */
  recheck_count: number;
  /** A document is an image-only scan -- not the same as `review_reason`
   *  "unreadable", which a corrupt file also gets. Optional: an API from
   *  before these two fields leaves them out. */
  scanned?: boolean;
  /** A vision model read one of those scans out for the reviewer. Never true
   *  in a run made without the model, such as the API's own startup run. */
  scan_transcribed?: boolean;
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
  review?: { reviewed: number; confirmed: number; corrected: number; unresolved?: number };
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

export function reviewCase(runId: string, emailId: string, body: ReviewBody) {
  return request<ReviewRecord>(`/cases/${encodeURIComponent(runId)}:${encodeURIComponent(emailId)}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Take a review back: the case is unreviewed again and Sentinel's own answer
 *  stands. Returns the fresh case report. 404 when there is no review. */
export function withdrawReview(runId: string, emailId: string) {
  return request<CaseReport>(`/cases/${encodeURIComponent(runId)}:${encodeURIComponent(emailId)}/review`, {
    method: "DELETE",
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

/** One run read sideways — see `backend/api/patterns.py`. */
export interface RunPatterns {
  run_id: string;
  run_status: string;
  cases_counted: number;
  total_emails: number;
  totals: { emails: number; comparisons: number; with_defect: number; escalated: number };
  baseline_defect_rate: number;
  defect_fields_total: number;
  fields: { field: string; count: number; share: number }[];
  senders: {
    sender: string;
    emails: number;
    comparisons: number;
    defects: number;
    escalated: number;
    rate: number | null;
    /** 95% Wilson interval. Null when the sender sent no comparison requests. */
    ci_low: number | null;
    ci_high: number | null;
    /** True only when the interval's lower bound clears the run's baseline. */
    above_baseline: boolean;
    /** False when the interval straddles the baseline — i.e. too few to tell. */
    conclusive: boolean;
    top_fields: { field: string; count: number }[];
  }[];
  escalation_reasons: { reason: string; count: number }[];
}

export function getPatterns(runId: string) {
  return request<RunPatterns>(`/runs/${encodeURIComponent(runId)}/patterns`);
}

export function getSubmission(runId?: string) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<Record<string, { category: string; status: string; review_reason: string | null; defect_fields: string[]; has_defect: boolean; decided_by: string }>>(
    `/submission${qs}`,
  );
}

export type ReplyTone = "formal" | "warm" | "brief";

/** POST /reply-drafts/polish. `adopted` is false when the backend refused the
 *  model's wording (it read as a value or a claim) and sent the template's
 *  own wording back with the reason. */
export interface ReplyPolishResult {
  greeting: string;
  closing: string;
  adopted: boolean;
  rejected_reason: string | null;
  model: string | null;
}

/** Only the two courtesy lines are sent. The draft's context, facts and
 *  request never leave the page, so the model is not shown a case value or a
 *  claim. `attempt` counts presses, so each one is a fresh prompt rather than
 *  a cached copy of the last answer. */
export function polishReplyWording(input: {
  situation: string;
  tone: ReplyTone;
  greeting: string;
  closing: string;
  attempt: number;
}) {
  return request<ReplyPolishResult>("/reply-drafts/polish", { method: "POST", body: JSON.stringify(input) });
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
