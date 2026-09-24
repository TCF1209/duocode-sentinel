import { useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle, CheckCircle2, RotateCw, XCircle } from "lucide-react";
import type { CaseReport, CaseStatus, DocumentReport, FieldComparisonReport } from "@/lib/api";
import { CategoryBadge, DecidedByBadge, StatusBadge } from "@/components/status-badges";
import { FieldComparisonRow, formatReason, type ReviewerView } from "@/components/field-comparison-row";
import { Button } from "@/components/ui/button";
import { ReviewPanel } from "@/components/review-panel";
import { ReplyDraftPanel } from "@/components/reply-draft-panel";
import { AttachmentAction } from "@/components/attachment-action";
import { RecheckHistory, RecheckPanel, type RecheckFiles } from "@/components/recheck-panel";
import { Separator } from "@/components/ui/separator";
import { fadeUp, stagger } from "@/lib/motion";
import { FIELD_LABELS, REVIEW_REASON_TEXT, STATUS_LABELS } from "@/lib/labels";
import { ScanTranscriptCard, transcriptOf } from "@/components/scan-transcript-card";
import { cn } from "@/lib/utils";

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

// AttachmentAction (the "View original" dialog / download link) lives in
// attachment-action.tsx: the re-check panel needs it for a case's superseded
// versions too, and that panel is rendered from here.

// The reader codes a document can fail with (readers/*, direct_compare.py's
// read_upload), in words a person can act on. Anything not listed falls
// back to the code with its underscores removed rather than to nothing.
const UNREADABLE_TEXT: Record<string, string> = {
  corrupt: "the file is corrupt and will not open",
  no_text_layer: "a scanned image with no text layer to read",
  empty_file: "the file is empty",
  unsupported: "an unsupported file type",
};

const EXPECTED_DOC_TYPE = { si: "SHIPPING_INSTRUCTION", bl: "BILL_OF_LADING" } as const;
const SIDE_NAME = { si: "shipping instruction", bl: "draft bill of lading" } as const;
const SIDE_LABEL = { si: "Shipping Instruction (SI)", bl: "Draft Bill of Lading (BL)" } as const;
const TONE_TEXT = { ok: "text-ok", warn: "text-warn", danger: "text-danger" } as const;

/** One document's state, as the thing a reviewer needs to know first:
 *  not attached / could not be read (and why) / read as the wrong kind of
 *  document / fine. Everything here is already in `report.documents`; it was
 *  only ever shown as a one-line "SI: path (TYPE, 621b)" at the bottom. */
function DocumentStatus({ side, doc, caseId }: { side: "si" | "bl"; doc: DocumentReport | null; caseId?: string }) {
  let tone: keyof typeof TONE_TEXT;
  let text: string;
  if (!doc) {
    tone = "danger";
    text = "Not attached to this email";
  } else if (!doc.readable) {
    tone = "danger";
    text = `Could not be read — ${UNREADABLE_TEXT[doc.unreadable_reason ?? ""] ?? (doc.unreadable_reason ?? "unknown reason").replace(/_/g, " ")}`;
  } else if (doc.doc_type !== EXPECTED_DOC_TYPE[side]) {
    tone = "warn";
    text = `Read as a ${doc.doc_type.replace(/_/g, " ").toLowerCase()} — not a ${SIDE_NAME[side]}`;
  } else {
    tone = "ok";
    text = `Read as a ${SIDE_NAME[side]}`;
  }
  const Icon = tone === "ok" ? CheckCircle2 : tone === "warn" ? AlertTriangle : XCircle;
  const transcript = transcriptOf(doc);
  return (
    <div className="flex flex-wrap items-start gap-x-2 gap-y-1 rounded-md border bg-background p-2.5 text-sm">
      <Icon className={cn("mt-0.5 size-4 shrink-0", TONE_TEXT[tone])} strokeWidth={2} />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{SIDE_LABEL[side]}</div>
        <div className={cn("text-xs", TONE_TEXT[tone])}>{text}</div>
        {doc && (
          <div className="text-xs text-muted-foreground">
            {doc.path} · {doc.n_bytes}b
          </div>
        )}
        {/* An image-only scan that a vision model was allowed to read arrives
            with the page already read out for the reviewer. It sits under the
            "could not be read" line on purpose: the document is still
            unreadable to the pipeline and the case is still here, the card
            only saves the reviewer from starting at zero. */}
        {transcript && (
          <div className="mt-2">
            <ScanTranscriptCard role={side === "si" ? "SI" : "BL"} transcript={transcript} />
          </div>
        )}
      </div>
      {doc && caseId && <AttachmentAction caseId={caseId} side={side} ext={doc.ext} path={doc.path} />}
    </div>
  );
}

/**
 * The NEEDS_REVIEW case page as a place to work, not a mismatch page with a
 * different colour. Raised directly: "human review isn't a simple thing,
 * and this page looked bare and nearly identical to a mismatch" -- a
 * mismatch is a few clicks, a needs-review case means Sentinel could not
 * read or find what it needed, and the person picking it up has to find
 * out what, and what to do about it. Three sections, in the order those
 * questions get asked: why it is here (with the state of each document),
 * what to do (the pipeline's own suggested action, and the actions that
 * exist), and -- in ReviewPanel right after -- deciding it yourself.
 *
 * Nothing here is new data: review_reason, documents.*.readable /
 * unreadable_reason / doc_type, the "Suggested action:" note, and the
 * per-field present/blank flags were all already on the page, as one
 * banner, a bullet among bullets, and a footer line.
 */
function NeedsReviewWorkspace({
  report,
  caseId,
  suggestedAction,
  onRetry,
  retrying,
  onRecheck,
  rechecking,
}: {
  report: CaseReport;
  caseId?: string;
  suggestedAction: string | null;
  onRetry?: () => Promise<void>;
  retrying?: boolean;
  onRecheck?: (files: RecheckFiles) => Promise<void>;
  rechecking?: boolean;
}) {
  // Only meaningful when both documents were actually read: a blank field
  // on a document that could not be read at all is the unreadability, not
  // a separate finding.
  const bothReadable = Boolean(report.documents.si?.readable && report.documents.bl?.readable);
  const blankFields = bothReadable
    ? report.fields
        .filter((f) => !f.si.present || !f.bl.present)
        .map((f) => {
          const sides = [!f.si.present && "SI", !f.bl.present && "BL"].filter(Boolean).join(" & ");
          return `${FIELD_LABELS[f.field] ?? f.field} (${sides})`;
        })
    : [];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-warn/40 bg-warn-bg/40 p-4">
      <div>
        <div className="flex items-center gap-2 text-sm font-semibold text-warn">
          <AlertTriangle className="size-4" strokeWidth={2} />
          Why this needs a person
        </div>
        <p className="mt-1 text-sm">
          {report.review_reason ? REVIEW_REASON_TEXT[report.review_reason] : "Sentinel could not decide this one automatically."}
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <DocumentStatus side="si" doc={report.documents.si} caseId={caseId} />
        <DocumentStatus side="bl" doc={report.documents.bl} caseId={caseId} />
      </div>

      {blankFields.length > 0 && (
        <p className="text-sm">
          Blank where a value was expected: <span className="font-medium">{blankFields.join(", ")}</span>
        </p>
      )}

      <div className="rounded-md border bg-background p-3">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">What to do</div>
        <p className="mt-1 text-sm">{suggestedAction ?? "Ask the sender for what is missing, or decide it yourself below."}</p>
        {onRetry && (
          <div className="mt-2">
            <Button
              size="sm"
              variant="outline"
              onClick={onRetry}
              disabled={retrying}
              title="Read the attachments again and re-decide this one case -- the thing to press once the sender has re-sent them"
            >
              <RotateCw className={retrying ? "animate-spin" : undefined} />
              {retrying ? "Re-processing…" : "Retry this case"}
            </Button>
          </div>
        )}
        {/* The action that actually resolves most of these: the sender
            re-sends the document and the same check runs on it. Sits with
            the other actions, not in a section of its own. */}
        {onRecheck && (
          <RecheckPanel report={report} onRecheck={onRecheck} rechecking={rechecking} className="mt-2" />
        )}
        <div className="mt-2">
          <ReplyDraftPanel report={report} />
        </div>
      </div>
    </div>
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
  priorDefectCounts,
  onRetry,
  retrying,
  onRecheck,
  rechecking,
}: {
  report: CaseReport;
  /** `<run_id>:<email_id>`, only when this report came from a run -- gates
   *  the "View original" links below. /compare has no persisted file to
   *  point at (its own docstring says it writes nothing), so it is left
   *  unset there and the links simply don't render, same as `onReview`. */
  caseId?: string;
  onReview?: (body: { decision: "confirm" | "correct"; status?: CaseStatus; defect_fields?: string[]; note?: string }) => Promise<void>;
  /** Passed straight through to ReviewPanel -- see its own prop comment. */
  priorDefectCounts?: Record<string, number>;
  /** "Retry this case", rendered inside the NEEDS_REVIEW workspace as one of
   *  its actions rather than in the page header -- it belongs next to "what
   *  to do", not above the report. Absent on /compare (nothing to re-read). */
  onRetry?: () => Promise<void>;
  retrying?: boolean;
  /** Re-check on re-sent documents (recheck-panel.tsx). Absent on /compare,
   *  which has no case to store the result against. */
  onRecheck?: (files: RecheckFiles) => Promise<void>;
  rechecking?: boolean;
}) {
  // classify/intent.py's signal ids (e.g. "attach.attached-are") ride in the
  // same `notes` list as human-written sentences. Every human sentence in
  // this codebase's notes.append() calls contains a space; no signal id
  // does — cheap, reliable split without needing the backend to tag them.
  const readableNotes = report.notes.filter((n) => n.includes(" "));
  const signalNotes = report.notes.filter((n) => !n.includes(" "));

  // The reviewer's correction, when there is one that can differ from
  // Sentinel's own answer. Only a "correct" decision produces one:
  // "confirm" leaves `effective` identical to the system keys (store.py's
  // effective_outcome, source stays "system"), and /compare never has an
  // `effective` at all. Everything below that reads `correction` renders
  // exactly as it always did when this is null -- the system's answer is
  // never replaced, only joined by the person's where they differ.
  const liveCorrection = report.effective?.source === "review" ? report.effective : null;
  // "Sentinel's original" view: the whole page rendered exactly as Sentinel
  // produced it, correction set aside -- asked for as "let me see the
  // unchanged version too". Everything below keys off `correction`, so
  // flipping this one value flips the header, the banner and every field
  // card together; nothing is re-fetched and nothing is written.
  const [showOriginal, setShowOriginal] = useState(false);
  const correction = showOriginal ? null : liveCorrection;

  // Per field. NEEDS_REVIEW as a corrected status is "couldn't tell", which
  // is not a claim about any one field in either direction, so it gets no
  // per-field overlay -- only the header badge changes for it.
  function reviewerViewFor(f: FieldComparisonReport): ReviewerView | null {
    if (!correction || correction.status === "NEEDS_REVIEW") return null;
    const flagged = correction.defect_fields.includes(f.field);
    if (f.verdict === "MISMATCH" && !flagged) return "cleared";
    if (f.verdict !== "MISMATCH" && flagged) return "flagged";
    return null;
  }

  // Sentinel's review-reason banner, once a reviewer has moved the case off
  // NEEDS_REVIEW (effective_outcome nulls the reason for any other status).
  const reasonResolved = Boolean(report.review_reason && correction && correction.review_reason === null);

  // The workspace replaces the banner while the case still genuinely needs a
  // person: Sentinel escalated it and no reviewer has moved it anywhere
  // else (a correction *to* NEEDS_REVIEW keeps it). Once corrected to
  // OK/MISMATCH the muted banner above says so and the workspace would be
  // stale advice. Under "Sentinel's original" `correction` is null, so the
  // workspace comes back with the rest of the original view -- consistent.
  const showWorkspace = report.status === "NEEDS_REVIEW" && (!correction || correction.status === "NEEDS_REVIEW");

  // Where re-sent documents can be dropped in: a comparison request whose
  // standing outcome is still a problem -- Sentinel's, or a reviewer's
  // correction to one. Not on an OK case (nothing to resolve), and never on
  // an email with no SI/BL pair to compare (the backend refuses those with
  // the same reasoning). The view toggle above does not move this: it is
  // about what the case *is*, so it follows the live correction, not the
  // one being displayed.
  const standingStatus = (liveCorrection ?? report).status;
  const recheckable = Boolean(onRecheck) && report.category === "BL_COMPARISON";
  const offerRecheck = recheckable && (standingStatus === "MISMATCH" || standingStatus === "NEEDS_REVIEW");
  // A retry re-reads the run's inbox from disk -- once a re-sent file has
  // replaced that, the backend refuses it (409), so it is not offered.
  const retry = report.recheck ? undefined : onRetry;

  // The pipeline already writes one "Suggested action: ..." sentence per
  // escalation reason (pipeline.py's notes); the workspace promotes it to a
  // heading and drops it from the bullet list so it isn't said twice.
  const suggestedNote = readableNotes.find((n) => n.startsWith("Suggested action:"));
  const suggestedAction = suggestedNote ? suggestedNote.replace(/^Suggested action:\s*/, "") : null;
  const notesToShow = showWorkspace && suggestedNote ? readableNotes.filter((n) => n !== suggestedNote) : readableNotes;

  // Seven near-identical amber "UNCOMPARABLE" cards say one thing seven
  // times when a document could not be read at all; one line says it once,
  // and the cards stay a click away for anyone who wants them.
  const collapseFields =
    showWorkspace && report.fields.length > 0 && report.fields.every((f) => f.verdict === "UNCOMPARABLE");
  const uncomparableReasons = Array.from(new Set(report.fields.map((f) => f.reason ?? "")));
  const uncomparableReason =
    uncomparableReasons.length === 1 && uncomparableReasons[0] ? formatReason(uncomparableReasons[0]) : "see each field";

  return (
    <motion.div
      key={report.email_id}
      className="flex flex-col gap-4"
      initial="hidden"
      animate="show"
      variants={stagger()}
    >
      <motion.div className="flex flex-wrap items-center gap-2" variants={fadeUp}>
        <h2 className="font-heading text-xl font-semibold">{report.email_id}</h2>
        <CategoryBadge category={report.category} />
        {/* The outcome that currently stands leads; Sentinel's own is kept
            beside it in words when the two differ. Same status corrected
            (e.g. a mismatch trimmed to fewer fields) shows one badge --
            "Sentinel said Mismatch" next to a Mismatch badge would only
            be noise, and the review panel below already says "corrected". */}
        {correction && correction.status !== report.status ? (
          <>
            <StatusBadge status={correction.status} />
            <span className="text-xs text-muted-foreground" title="Sentinel's own outcome, before a reviewer corrected it">
              Sentinel said {STATUS_LABELS[report.status]}
            </span>
          </>
        ) : (
          <StatusBadge status={report.status} />
        )}
        <DecidedByBadge decidedBy={report.decided_by} />
        <ModelTier offered={report.model_offered} used={report.model_used} />
        <span className="text-xs text-muted-foreground">{report.duration_ms}ms</span>
        {report.llm_calls > 0 && <span className="text-xs text-muted-foreground">{report.llm_calls} model call(s)</span>}
        {liveCorrection && (
          <div
            className="ml-auto flex items-center rounded-full border p-0.5 text-xs"
            role="group"
            aria-label="Which view of this case to show"
          >
            <button
              type="button"
              onClick={() => setShowOriginal(false)}
              aria-pressed={!showOriginal}
              className={cn(
                "rounded-full px-2.5 py-0.5 transition-colors",
                !showOriginal ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              With correction
            </button>
            <button
              type="button"
              onClick={() => setShowOriginal(true)}
              aria-pressed={showOriginal}
              className={cn(
                "rounded-full px-2.5 py-0.5 transition-colors",
                showOriginal ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              Sentinel&apos;s original
            </button>
          </div>
        )}
      </motion.div>

      {/* Leads once the case has been re-checked: the answer below was
          reached on re-sent documents, and what it replaced is one
          disclosure away. */}
      {report.recheck && (
        <motion.div variants={fadeUp}>
          <RecheckHistory report={report} caseId={caseId} />
        </motion.div>
      )}

      {!showWorkspace && report.review_reason && (
        <motion.div
          className={cn(
            "flex items-start gap-2.5 rounded-md border p-3 text-sm",
            // Kept, not removed, once a reviewer resolves it: what Sentinel
            // flagged is still part of the record, it just no longer leads.
            reasonResolved ? "border-border bg-muted/40 text-muted-foreground" : "border-warn/30 bg-warn-bg text-warn",
          )}
          variants={fadeUp}
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" strokeWidth={2} />
          <div>
            <div className="font-medium">
              {reasonResolved && <span className="font-normal">Sentinel had flagged: </span>}
              {REVIEW_REASON_TEXT[report.review_reason]}
            </div>
            {report.defect_fields.length > 0 && (
              <div className={cn("mt-0.5", !reasonResolved && "text-warn/80")}>
                Flagged: {report.defect_fields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}
              </div>
            )}
            {reasonResolved && correction && (
              <div className="mt-0.5">Resolved by a reviewer — corrected to {STATUS_LABELS[correction.status]}.</div>
            )}
          </div>
        </motion.div>
      )}

      {showWorkspace && (
        <motion.div variants={fadeUp}>
          <NeedsReviewWorkspace
            report={report}
            caseId={caseId}
            suggestedAction={suggestedAction}
            onRetry={retry}
            retrying={retrying}
            onRecheck={offerRecheck ? onRecheck : undefined}
            rechecking={rechecking}
          />
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
          <ReviewPanel report={report} onSubmit={onReview} priorDefectCounts={priorDefectCounts} />
        </motion.div>
      )}

      {/* On a mismatch the same panel sits under the review: "the shipper
          sent a corrected BL" is the other way a mismatch gets resolved,
          beside a reviewer deciding it. Inside the workspace's "what to do"
          when the case is escalated instead -- never both. */}
      {!showWorkspace && offerRecheck && onRecheck && (
        <motion.div variants={fadeUp}>
          <RecheckPanel report={report} onRecheck={onRecheck} rechecking={rechecking} />
        </motion.div>
      )}

      {/* Inside the workspace's "what to do" when the case is escalated;
          on its own here otherwise. Never both. */}
      {!showWorkspace && (
        <motion.div variants={fadeUp}>
          <ReplyDraftPanel report={report} />
        </motion.div>
      )}

      {(readableNotes.length > 0 ||
        signalNotes.length > 0 ||
        report.errors.length > 0 ||
        report.fields.length > 0) && <Separator />}

      {notesToShow.length > 0 && (
        <motion.ul className="list-inside list-disc text-sm text-muted-foreground" variants={fadeUp}>
          {notesToShow.map((n, i) => (
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

      {/* A section label over the field cards, in the same small-caps style
          as the other section labels on this page, so the list of cards
          reads as one section with a boundary rather than more of the
          same-sized text (the collapsed variant below has its own line). */}
      {report.fields.length > 0 && !collapseFields && (
        <motion.div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground" variants={fadeUp}>
          {report.fields.length} fields compared
        </motion.div>
      )}

      {report.fields.length > 0 &&
        (collapseFields ? (
          <motion.details className="rounded-lg border bg-card text-sm" variants={fadeUp}>
            <summary className="cursor-pointer select-none p-3 text-muted-foreground">
              All {report.fields.length} fields uncomparable — {uncomparableReason}. Show the fields anyway
            </summary>
            <div className="flex flex-col gap-2 border-t p-3">
              {report.fields.map((f) => (
                <FieldComparisonRow key={f.field} comparison={f} reviewerView={reviewerViewFor(f)} reviewerNote={report.review?.note} />
              ))}
            </div>
          </motion.details>
        ) : (
          <motion.div className="flex flex-col gap-2" variants={stagger(0, 0.05)}>
            {report.fields.map((f) => (
              <motion.div key={f.field} variants={fadeUp}>
                <FieldComparisonRow comparison={f} reviewerView={reviewerViewFor(f)} reviewerNote={report.review?.note} />
              </motion.div>
            ))}
          </motion.div>
        ))}

      {/* The workspace's document cards above carry path, size and "View
          original" already; showing this line as well said it all twice. */}
      {!showWorkspace && (
      <motion.div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2" variants={fadeUp}>
        {report.documents.si && (
          <div className="flex flex-wrap items-center gap-x-2">
            <span>
              SI: {report.documents.si.path} ({report.documents.si.doc_type}, {report.documents.si.n_bytes}b)
            </span>
            {caseId && (
              <AttachmentAction caseId={caseId} side="si" ext={report.documents.si.ext} path={report.documents.si.path} />
            )}
          </div>
        )}
        {report.documents.bl && (
          <div className="flex flex-wrap items-center gap-x-2">
            <span>
              BL: {report.documents.bl.path} ({report.documents.bl.doc_type}, {report.documents.bl.n_bytes}b)
            </span>
            {caseId && (
              <AttachmentAction caseId={caseId} side="bl" ext={report.documents.bl.ext} path={report.documents.bl.path} />
            )}
          </div>
        )}
      </motion.div>
      )}
    </motion.div>
  );
}
