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
  /** What the case is NOW, after any human correction. The keys above stay
   *  the system's own answer, so a card can show both. */
  effective?: EffectiveOutcome | null;
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

export interface CaseSummary {
  case_id: string;
  email_id: string;
  category: Category;
  category_confidence: number;
  /** The effective status — a corrected case leaves the queue it was in. */
  status: CaseStatus;
  review_reason: ReviewReason | null;
  has_defect: boolean;
  defect_fields: string[];
  decided_by: DecidedBy;
  reviewed: boolean;
  outcome_source: "system" | "review";
  /** What Sentinel itself said, kept beside the effective status so a row a
   *  person overrode does not look like a row we got right. */
  system_status: CaseStatus;
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
