import type { CaseReport, CaseStatus } from "@/lib/api";
import { CategoryBadge, DecidedByBadge, StatusBadge } from "@/components/status-badges";
import { FieldComparisonRow } from "@/components/field-comparison-row";
import { ReviewPanel } from "@/components/review-panel";
import { ReplyDraftPanel } from "@/components/reply-draft-panel";
import { Separator } from "@/components/ui/separator";

/**
 * The discrepancy report — "the screen the whole project exists to produce"
 * (docs/ROADMAP.md 3b). Shared by the run case-detail page and the judge
 * upload page (/compare), since both render the exact same CaseReport shape.
 */
export function CaseReportView({
  report,
  onReview,
}: {
  report: CaseReport;
  onReview?: (body: { decision: "confirm" | "correct"; status?: CaseStatus; defect_fields?: string[]; note?: string }) => Promise<void>;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{report.email_id}</h2>
        <CategoryBadge category={report.category} />
        <StatusBadge status={report.status} />
        <DecidedByBadge decidedBy={report.decided_by} />
        <span className="text-xs text-muted-foreground">{report.duration_ms}ms</span>
        {report.llm_calls > 0 && <span className="text-xs text-muted-foreground">{report.llm_calls} model call(s)</span>}
      </div>

      {report.review_reason && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <span className="font-medium">Needs review:</span> {report.review_reason.replaceAll("_", " ")}
        </div>
      )}

      {report.notes.length > 0 && (
        <ul className="list-inside list-disc text-sm text-muted-foreground">
          {report.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}

      {report.errors.length > 0 && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {report.errors.join(" · ")}
        </div>
      )}

      {report.fields.length > 0 && (
        <div className="flex flex-col gap-2">
          {report.fields.map((f) => (
            <FieldComparisonRow key={f.field} comparison={f} />
          ))}
        </div>
      )}

      <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        {report.documents.si && (
          <div>
            SI: {report.documents.si.path} ({report.documents.si.doc_type}, {report.documents.si.n_bytes}b)
          </div>
        )}
        {report.documents.bl && (
          <div>
            BL: {report.documents.bl.path} ({report.documents.bl.doc_type}, {report.documents.bl.n_bytes}b)
          </div>
        )}
      </div>

      <Separator />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        {onReview ? <ReviewPanel report={report} onSubmit={onReview} /> : <div />}
        <ReplyDraftPanel report={report} />
      </div>
    </div>
  );
}
