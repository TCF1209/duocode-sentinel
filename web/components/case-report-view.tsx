import { motion } from "motion/react";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { attachmentUrl, type CaseReport, type CaseStatus } from "@/lib/api";
import { CategoryBadge, DecidedByBadge, StatusBadge } from "@/components/status-badges";
import { FieldComparisonRow } from "@/components/field-comparison-row";
import { ReviewPanel } from "@/components/review-panel";
import { ReplyDraftPanel } from "@/components/reply-draft-panel";
import { Separator } from "@/components/ui/separator";
import { fadeUp, stagger } from "@/lib/motion";
import { FIELD_LABELS, REVIEW_REASON_TEXT } from "@/lib/labels";

// The backend computes `model_offered` and `model_used` so the page can say
// which tier answered instead of the reader inferring it from extractor tags.
// Nothing rendered them, which made the most interesting outcome invisible:
// "we asked the model and adopted nothing" looked exactly like "the model was
// switched off". That distinction is the product's own thesis -- the model is a
// fallback that has to earn each value -- so it belongs on screen, and on the
// /compare page it is the one place a judge can watch it happen.
function ModelTier({ offered, used }: { offered?: boolean; used?: boolean }) {
  if (offered === undefined) return null;
  const label = !offered
    ? "model off"
    : used
      ? "model answered"
      : "model asked, nothing adopted";
  return (
    <span
      className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground"
      title={
        !offered
          ? "No model was configured for this run; every value came from the deterministic readers."
          : used
            ? "At least one field was filled by the model and re-located in its source before being adopted."
            : "The model was available and was asked, but nothing it returned could be traced back to the document, so nothing was adopted."
      }
    >
      {label}
    </span>
  );
}

/** Opens the real file a run read off disk in a new tab -- backend/api/main.py
 *  serves it `inline`, so a .txt or .pdf (220 of the dataset's 250 attachments,
 *  docs/DATA_NOTES.md) renders right there instead of forcing a download the
 *  reviewer then has to go find. A .docx/.xlsx has no browser-native viewer
 *  either way and just downloads, same as it would have without this link. */
function AttachmentLink({ caseId, side }: { caseId: string; side: "si" | "bl" }) {
  return (
    <a
      href={attachmentUrl(caseId, side)}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-primary hover:underline"
    >
      <ExternalLink className="size-3" />
      View original
    </a>
  );
}

/**
 * The discrepancy report — "the screen the whole project exists to produce"
 * (docs/ROADMAP.md 3b). Shared by the run case-detail page and the judge
 * upload page (/compare), since both render the exact same CaseReport shape.
 */
export function CaseReportView({
  report,
  caseId,
  onReview,
}: {
  report: CaseReport;
  /** `<run_id>:<email_id>`, only when this report came from a run -- gates
   *  the "View original" links below. /compare has no persisted file to
   *  point at (its own docstring says it writes nothing), so it is left
   *  unset there and the links simply don't render, same as `onReview`. */
  caseId?: string;
  onReview?: (body: { decision: "confirm" | "correct"; status?: CaseStatus; defect_fields?: string[]; note?: string }) => Promise<void>;
}) {
  // classify/intent.py's signal ids (e.g. "attach.attached-are") ride in the
  // same `notes` list as human-written sentences. Every human sentence in
  // this codebase's notes.append() calls contains a space; no signal id
  // does — cheap, reliable split without needing the backend to tag them.
  const readableNotes = report.notes.filter((n) => n.includes(" "));
  const signalNotes = report.notes.filter((n) => !n.includes(" "));

  return (
    <motion.div
      key={report.email_id}
      className="flex flex-col gap-4"
      initial="hidden"
      animate="show"
      variants={stagger()}
    >
      <motion.div className="flex flex-wrap items-center gap-2" variants={fadeUp}>
        <h2 className="font-heading text-lg font-semibold">{report.email_id}</h2>
        <CategoryBadge category={report.category} />
        <StatusBadge status={report.status} />
        <DecidedByBadge decidedBy={report.decided_by} />
        <ModelTier offered={report.model_offered} used={report.model_used} />
        <span className="text-xs text-muted-foreground">{report.duration_ms}ms</span>
        {report.llm_calls > 0 && <span className="text-xs text-muted-foreground">{report.llm_calls} model call(s)</span>}
      </motion.div>

      {report.review_reason && (
        <motion.div
          className="flex items-start gap-2.5 rounded-md border border-warn/30 bg-warn-bg p-3 text-sm text-warn"
          variants={fadeUp}
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" strokeWidth={2} />
          <div>
            <div className="font-medium">{REVIEW_REASON_TEXT[report.review_reason]}</div>
            {report.defect_fields.length > 0 && (
              <div className="mt-0.5 text-warn/80">
                Flagged: {report.defect_fields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Right under the "why", not after every field — a reviewer landing
          here should see what to do before they see the evidence, not after
          scrolling past all of it. The reply draft is the same kind of
          thing for the same reason: on a real case with several fields,
          each carrying an SI card and a BL card, "draft a reply" used to
          sit below a long scroll of evidence a reviewer had often already
          decided not to read line by line -- easy to never notice it was
          there at all, not just easy to reach late. */}
      {onReview && (
        <motion.div variants={fadeUp}>
          <ReviewPanel report={report} onSubmit={onReview} />
        </motion.div>
      )}

      <motion.div variants={fadeUp}>
        <ReplyDraftPanel report={report} />
      </motion.div>

      {(readableNotes.length > 0 ||
        signalNotes.length > 0 ||
        report.errors.length > 0 ||
        report.fields.length > 0) && <Separator />}

      {readableNotes.length > 0 && (
        <motion.ul className="list-inside list-disc text-sm text-muted-foreground" variants={fadeUp}>
          {readableNotes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </motion.ul>
      )}

      {signalNotes.length > 0 && (
        <motion.details className="text-xs text-muted-foreground" variants={fadeUp}>
          <summary className="cursor-pointer select-none font-mono">
            {signalNotes.length} internal classifier signal{signalNotes.length > 1 ? "s" : ""}
          </summary>
          <ul className="mt-1 list-inside list-disc font-mono">
            {signalNotes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </motion.details>
      )}

      {report.errors.length > 0 && (
        <motion.div className="rounded-md border border-danger/30 bg-danger-bg p-3 text-sm text-danger" variants={fadeUp}>
          {report.errors.join(" · ")}
        </motion.div>
      )}

      {report.fields.length > 0 && (
        <motion.div className="flex flex-col gap-2" variants={stagger(0, 0.05)}>
          {report.fields.map((f) => (
            <motion.div key={f.field} variants={fadeUp}>
              <FieldComparisonRow comparison={f} />
            </motion.div>
          ))}
        </motion.div>
      )}

      <motion.div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2" variants={fadeUp}>
        {report.documents.si && (
          <div className="flex flex-wrap items-center gap-x-2">
            <span>
              SI: {report.documents.si.path} ({report.documents.si.doc_type}, {report.documents.si.n_bytes}b)
            </span>
            {caseId && <AttachmentLink caseId={caseId} side="si" />}
          </div>
        )}
        {report.documents.bl && (
          <div className="flex flex-wrap items-center gap-x-2">
            <span>
              BL: {report.documents.bl.path} ({report.documents.bl.doc_type}, {report.documents.bl.n_bytes}b)
            </span>
            {caseId && <AttachmentLink caseId={caseId} side="bl" />}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
