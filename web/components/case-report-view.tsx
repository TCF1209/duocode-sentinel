import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import type { CaseReport, DocumentReport, FieldComparisonReport, FieldDecision, Verdict } from "@/lib/api";
import { CategoryBadge, DecidedByBadge, StatusBadge } from "@/components/status-badges";
import { FieldComparisonRow, formatReason, type DocSideKey, type ReviewerView } from "@/components/field-comparison-row";
import { EMPTY_DRAFT, ReviewPanel, type ReviewController } from "@/components/review-panel";
import { ReplyDraftPanel } from "@/components/reply-draft-panel";
import { replyDraftKey } from "@/lib/reply-draft";
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
    ? "Model off"
    : used
      ? "Model answered"
      : "Model asked, nothing adopted";
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

/** "697 B" / "12,480 B" -- a space before the unit, like every other
 *  figure on the page ("2.3 ms", "1.3 s"). */
function formatBytes(n: number): string {
  return `${n.toLocaleString()} B`;
}
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
            {doc.path} · {formatBytes(doc.n_bytes)}
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
 * out what, and what to do about it. Why it is here, which fields could
 * not be read, what to do (the pipeline's own suggested action, with the
 * reply draft) -- then, as their own blocks after it, re-sent documents
 * and deciding it yourself. The two document cards sit above this box,
 * on every case (CaseReportView).
 *
 * Nothing here is new data: review_reason, the "Suggested action:" note
 * and the per-field present/blank flags were all already on the page, as
 * one banner, a bullet among bullets, and a footer line.
 */
function NeedsReviewWorkspace({ report, suggestedAction }: { report: CaseReport; suggestedAction: string | null }) {
  // Only meaningful when both documents were actually read: a blank field
  // on a document that could not be read at all is the unreadability, not
  // a separate finding. Grouped by document -- "Unread on the SI: Shipper,
  // Consignee" -- so the line names the page to open and the fields to
  // look for, and nothing else.
  const bothReadable = Boolean(report.documents.si?.readable && report.documents.bl?.readable);
  const unread = bothReadable
    ? (["si", "bl"] as const)
        .map((side) => ({
          side,
          fields: report.fields.filter((f) => !f[side].present).map((f) => FIELD_LABELS[f.field] ?? f.field),
        }))
        .filter((g) => g.fields.length > 0)
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

      {unread.length > 0 && (
        <p className="text-sm">
          {unread.map((g, i) => (
            <span key={g.side}>
              {i > 0 && " · "}
              Unread on the {g.side.toUpperCase()}: <span className="font-medium">{g.fields.join(", ")}</span>
            </span>
          ))}
        </p>
      )}

      <div className="rounded-md border bg-background p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">What to do</div>
        <p className="mt-1 text-sm">{suggestedAction ?? "Ask the sender, or decide it below."}</p>
        {/* "Retry this case" used to sit here beside Re-check and read as
            the same thing twice; decided directly: only Re-check stays. A
            retry (re-reading the inbox files) is offered in the page header
            solely on a case the pipeline failed on (case-detail-page-view). */}
        <div className="mt-2" data-spotlight="reply">
          <ReplyDraftPanel key={replyDraftKey(report)} report={report} />
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
  review,
  priorDefectCounts,
  onRecheck,
  rechecking,
  spotlight,
}: {
  report: CaseReport;
  /** `<run_id>:<email_id>`, only when this report came from a run -- gates
   *  the "View original" links below. /compare has no persisted file to
   *  point at (its own docstring says it writes nothing), so it is left
   *  unset there and the links simply don't render, same as `review`. */
  caseId?: string;
  /** How a review is saved (review-panel.tsx's ReviewController, owned by
   *  case-detail-page-view.tsx). Absent on /compare, which has no case to
   *  review. */
  review?: ReviewController;
  /** Per field, how many other cases from this shipper in this run are
   *  flagged on it -- for the history badge on a mismatched field's card
   *  (field-comparison-row.tsx). */
  priorDefectCounts?: Record<string, number>;
  /** Re-check on re-sent documents (recheck-panel.tsx). Absent on /compare,
   *  which has no case to store the result against. */
  onRecheck?: (files: RecheckFiles) => Promise<void>;
  rechecking?: boolean;
  /** Name of a panel to scroll to and ring once the report is up -- the
   *  target of a home-page "See it live" tile (`?spotlight=` on the case
   *  page). Matched against the `data-spotlight` attributes below. */
  spotlight?: string;
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

  // A "See it live" tile on the home page (or a "Worth opening" chip on the
  // run page) lands on the panel it promised, not on the top of a long
  // report: the tagged panel is scrolled to the middle of the screen. No
  // highlight on top of that -- decided directly: the attention cue belongs
  // to the Compare page's first sample only; here the panel's own heading
  // says what it is. The short delay lets the report's own entrance finish
  // laying out first.
  useEffect(() => {
    if (!spotlight) return;
    const el = document.querySelector<HTMLElement>(`[data-spotlight="${spotlight}"]`);
    if (!el) return;
    const show = setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "center" }), 250);
    return () => clearTimeout(show);
  }, [spotlight, report.email_id]);

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

  // The first mismatched field this shipper has been flagged on before is
  // where a "shipper history" spotlight lands (home page tile).
  const historyField = report.fields.find(
    (f) => f.verdict === "MISMATCH" && (priorDefectCounts?.[f.field] ?? 0) > 0,
  )?.field;

  // In-place review: the reviewer decides each field on its own card, and
  // each choice is saved as it is made (case-detail-page-view.tsx owns the
  // requests; the panel at the top only holds the whole-case actions and,
  // once reviewed, the summary). Only where there are cards to decide on
  // -- a case whose documents were missing or unreadable has nothing
  // comparable, and picks its outcome in the panel directly -- and never
  // on /compare, which has no review at all. A case already reviewed keeps
  // its cards live: the saved review is the draft, and any choice on it is
  // changed the same way it was made.
  const inPlace = Boolean(review) && report.fields.length > 0 && !collapseFields;
  const draft = review?.draft ?? EMPTY_DRAFT;
  function decide(field: string, d: FieldDecision | null) {
    if (!review) return;
    if (d === null && !(field in draft.decisions)) return;
    const decisions = { ...draft.decisions };
    if (d === null) delete decisions[field];
    else decisions[field] = d;
    review.commit({ ...draft, decisions }, field);
  }
  // A corrected value on one side of a field, saved with the field's other
  // corrections; `null` puts that side back to Sentinel's reading. The
  // backend compares the corrected pair again and the outcome follows.
  function correct(field: string, side: DocSideKey, value: string | null) {
    if (!review) return;
    const corrections = { ...draft.corrections };
    const sides = { ...(corrections[field] ?? {}) };
    if (value === null) delete sides[side];
    else sides[side] = value;
    if (Object.keys(sides).length === 0) delete corrections[field];
    else corrections[field] = sides;
    review.commit({ ...draft, corrections }, field);
  }
  // The controls sit on the cards only in the live view: "Sentinel's
  // original" is a way of looking, not of editing.
  const decideOn = inPlace && !showOriginal;

  // What stands on each field for the reviewer's eye: the corrected pair's
  // verdict when there is one, the one-click choice on top of that -- or
  // Sentinel's own under "Sentinel's original". The fields that agree and
  // nobody has touched fold away under one line, so a mismatch case opens
  // on the fields that differ instead of five clean cards above them.
  function standsOn(f: FieldComparisonReport): Verdict {
    if (showOriginal) return f.verdict;
    const d = draft.decisions[f.field];
    if (d === "cleared" || d === "fine") return "MATCH";
    if (d === "flagged") return "MISMATCH";
    return report.review?.field_verdicts?.[f.field]?.verdict ?? f.verdict;
  }
  const isQuiet = (f: FieldComparisonReport) =>
    standsOn(f) === "MATCH" && (showOriginal || !(draft.decisions[f.field] || draft.corrections[f.field]));
  const loudFields = report.fields.filter((f) => !isQuiet(f));
  const quietFields = report.fields.filter(isQuiet);
  const renderCard = (f: FieldComparisonReport) => (
    <FieldComparisonRow
      comparison={f}
      // With live controls the active choice says what the reviewer did;
      // the badge is for the views without them.
      reviewerView={decideOn ? null : reviewerViewFor(f)}
      reviewerNote={report.review?.note}
      priorCount={priorDefectCounts?.[f.field] ?? 0}
      decision={decideOn ? (draft.decisions[f.field] ?? null) : undefined}
      onDecide={decideOn ? (d) => decide(f.field, d) : undefined}
      corrections={decideOn ? draft.corrections[f.field] : undefined}
      onCorrect={decideOn ? (side, v) => correct(f.field, side, v) : undefined}
      verdict={decideOn && draft.corrections[f.field] ? report.review?.field_verdicts?.[f.field]?.verdict : undefined}
      reason={decideOn && draft.corrections[f.field] ? report.review?.field_verdicts?.[f.field]?.reason : undefined}
      busy={review?.busy === f.field}
      justSaved={review?.flash === f.field}
    />
  );

  return (
    <motion.div
      key={report.email_id}
      className="flex flex-col gap-4"
      initial="hidden"
      animate="show"
      variants={stagger()}
    >
      <motion.div className="flex flex-wrap items-center gap-2" variants={fadeUp}>
        {/* An identifier, so monospace -- the same face the run page's own
            title and every id in the tables use. */}
        <h2 className="font-mono text-lg font-semibold">{report.email_id}</h2>
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
        <span className="text-xs text-muted-foreground tabular-nums">{report.duration_ms} ms</span>
        {report.llm_calls > 0 && (
          <span className="text-xs text-muted-foreground">
            {report.llm_calls} model call{report.llm_calls === 1 ? "" : "s"}
          </span>
        )}
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

      {/* The two documents first, on every case: what each was read as,
          whether it could be read, and the original a click away. Decided
          directly: the needs-review page had these cards at the top and the
          mismatch page had a footer line at the bottom, and the top is
          where a reader looks for them. */}
      <motion.div className="grid gap-2 sm:grid-cols-2" variants={fadeUp} data-spotlight="documents">
        <DocumentStatus side="si" doc={report.documents.si} caseId={caseId} />
        <DocumentStatus side="bl" doc={report.documents.bl} caseId={caseId} />
      </motion.div>

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
          <NeedsReviewWorkspace report={report} suggestedAction={suggestedAction} />
        </motion.div>
      )}

      {/* Re-sent documents straight after "what to do" when the case is
          escalated: for a missing or unreadable document that *is* the
          action, and it comes before deciding the case by hand. Its own
          block, not nested inside the workspace -- one border fewer. */}
      {showWorkspace && offerRecheck && onRecheck && (
        <motion.div variants={fadeUp} data-spotlight="recheck">
          <RecheckPanel report={report} onRecheck={onRecheck} rechecking={rechecking} defaultOpen={spotlight === "recheck"} />
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
      {review && (
        <motion.div variants={fadeUp} data-spotlight="review">
          <ReviewPanel report={report} control={review} inPlace={inPlace} />
        </motion.div>
      )}

      {/* On a mismatch the same panel sits under the review: "the shipper
          sent a corrected BL" is the other way a mismatch gets resolved,
          beside a reviewer deciding it. Inside the workspace's "what to do"
          when the case is escalated instead -- never both. */}
      {!showWorkspace && offerRecheck && onRecheck && (
        <motion.div variants={fadeUp} data-spotlight="recheck">
          <RecheckPanel report={report} onRecheck={onRecheck} rechecking={rechecking} defaultOpen={spotlight === "recheck"} />
        </motion.div>
      )}

      {/* Inside the workspace's "what to do" when the case is escalated;
          on its own here otherwise. Never both. */}
      {!showWorkspace && (
        <motion.div variants={fadeUp} data-spotlight="reply">
          <ReplyDraftPanel key={replyDraftKey(report)} report={report} />
        </motion.div>
      )}

      {(readableNotes.length > 0 ||
        signalNotes.length > 0 ||
        report.errors.length > 0 ||
        report.fields.length > 0) && <Separator />}

      {/* Sentinel's own notes and the classifier's signal ids, one
          disclosure line together. They used to be a bullet list on the
          page: on a needs-review case the bullet restated what the
          workspace above had just said, and on a clean case it was a line
          of reassurance under a report that already shows its evidence per
          value. Still one click away for whoever wants them. */}
      {(notesToShow.length > 0 || signalNotes.length > 0) && (
        <motion.details className="text-xs text-muted-foreground" variants={fadeUp}>
          <summary className="cursor-pointer select-none">
            {[
              notesToShow.length > 0 && `${notesToShow.length} note${notesToShow.length === 1 ? "" : "s"} from Sentinel`,
              signalNotes.length > 0 && `${signalNotes.length} classifier signal${signalNotes.length === 1 ? "" : "s"}`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </summary>
          {notesToShow.length > 0 && (
            <ul className="mt-1 list-inside list-disc">
              {notesToShow.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
          {signalNotes.length > 0 && (
            <ul className="mt-1 list-inside list-disc font-mono">
              {signalNotes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
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
                <FieldComparisonRow
                  key={f.field}
                  comparison={f}
                  reviewerView={reviewerViewFor(f)}
                  reviewerNote={report.review?.note}
                  priorCount={priorDefectCounts?.[f.field] ?? 0}
                />
              ))}
            </div>
          </motion.details>
        ) : (
          <motion.div className="flex flex-col gap-2" variants={stagger(0, 0.05)} data-spotlight="fields">
            {loudFields.map((f) => (
              <motion.div key={f.field} variants={fadeUp} data-spotlight={f.field === historyField ? "history" : undefined}>
                {renderCard(f)}
              </motion.div>
            ))}
            {quietFields.length > 0 && (
              <motion.details className="rounded-lg border bg-card text-sm" variants={fadeUp}>
                <summary className="cursor-pointer select-none p-3 text-muted-foreground">
                  {quietFields.length === report.fields.length
                    ? `All ${report.fields.length} fields agree`
                    : `${quietFields.length} field${quietFields.length === 1 ? "" : "s"} agree`}{" "}
                  — show {quietFields.length === 1 ? "it" : "them"}
                </summary>
                <div className="flex flex-col gap-2 border-t p-3">
                  {quietFields.map((f) => (
                    <div key={f.field} data-spotlight={f.field === historyField ? "history" : undefined}>
                      {renderCard(f)}
                    </div>
                  ))}
                </div>
              </motion.details>
            )}
          </motion.div>
        ))}

    </motion.div>
  );
}
