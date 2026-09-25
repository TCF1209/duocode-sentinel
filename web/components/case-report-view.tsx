import { useEffect, useState, type ReactNode } from "react";
import { motion } from "motion/react";
import { AlertTriangle, CheckCircle2, Sparkles, Upload, XCircle } from "lucide-react";
import type { CaseReport, DocumentReport, FieldComparisonReport, Verdict } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CategoryBadge, DecidedByBadge, StatusBadge } from "@/components/status-badges";
import { FieldComparisonRow, QuietFieldRow, type DocSideKey } from "@/components/field-comparison-row";
import {
  EMPTY_DRAFT,
  FieldPicker,
  ReviewBox,
  ReviewSummary,
  RowEnd,
  ScanAdoptPanel,
  type ReadOutRow,
  type ReviewController,
} from "@/components/review-panel";
import { ReplyDraftPanel } from "@/components/reply-draft-panel";
import { replyDraftKey } from "@/lib/reply-draft";
import { AttachmentAction } from "@/components/attachment-action";
import { RecheckHistory, RecheckPanel, type RecheckFiles } from "@/components/recheck-panel";
import { Separator } from "@/components/ui/separator";
import { fadeUp, stagger } from "@/lib/motion";
import { CATEGORY_BADGE_LABELS, FIELD_LABELS, REVIEW_REASON_TEXT, STATUS_LABELS } from "@/lib/labels";
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

  // The re-sent documents area lives inside the review box, under its row
  // of actions, behind the "Attach re-sent SI/BL" button there. It starts
  // open in two cases, both the user's rule: a page opened at it
  // (?spotlight=recheck, the home tile) and a case with nothing on file --
  // there the sample pair is the only way to watch a re-check, and a folded
  // area would hide it. The grey one-line bar it used to fold into is gone.
  const [recheckOpen, setRecheckOpen] = useState(
    spotlight === "recheck" || (!report.documents.si && !report.documents.bl),
  );
  const recheckButton =
    offerRecheck && onRecheck ? (
      <Button
        size="sm"
        // On a case with nothing on file, attaching the documents *is* the
        // action, so the button leads.
        variant={showWorkspace && report.fields.length === 0 ? "default" : "outline"}
        aria-expanded={recheckOpen}
        onClick={() => setRecheckOpen((o) => !o)}
        title="Got a corrected SI or BL back from the sender? Attach it and the same check runs again"
      >
        <Upload className="size-4" />
        Attach re-sent SI/BL
      </Button>
    ) : null;

  // A "See it live" tile on the home page lands on the panel it promised,
  // not on the top of a long
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

  // A document that could not be read at all leaves seven UNCOMPARABLE
  // fields; they render as seven one-line rows below (QuietFieldRow), each
  // with its reason, instead of seven near-identical amber cards.

  // The first mismatched field this shipper has been flagged on before is
  // where a "shipper history" spotlight lands (home page tile).
  const historyField = report.fields.find(
    (f) => f.verdict === "MISMATCH" && (priorDefectCounts?.[f.field] ?? 0) > 0,
  )?.field;

  // In-place review: the reviewer decides each field on its own card, and
  // each choice is saved as it is made (case-detail-page-view.tsx owns the
  // requests; the box at the top holds the whole-case findings and, once
  // reviewed, the summary). Only a document check is reviewed at all: the
  // other categories have nothing to compare, so their page says so in one
  // line instead of a box. Never on /compare, which has no review. A case
  // already reviewed keeps its cards live: the saved review is the draft,
  // and any choice on it is changed the same way it was made.
  const comparison = report.category === "BL_COMPARISON";
  const inPlace = Boolean(review) && comparison && report.fields.length > 0;
  const draft = review?.draft ?? EMPTY_DRAFT;
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
  // Sentinel's own under "Sentinel's original". All seven fields stay on
  // the page in the documents' order (the user's ask: "I only saw the ones
  // I had to change"): a field that differs, or that the reviewer touched,
  // is a full card; a field that agrees, or that Sentinel could not
  // compare, and nobody touched is one line (QuietFieldRow, amber with its
  // reason when uncomparable) that opens into its card on a click.
  function standsOn(f: FieldComparisonReport): Verdict {
    if (showOriginal) return f.verdict;
    const d = draft.decisions[f.field];
    if (d === "cleared" || d === "fine") return "MATCH";
    if (d === "flagged") return "MISMATCH";
    return report.review?.field_verdicts?.[f.field]?.verdict ?? f.verdict;
  }
  const isQuiet = (f: FieldComparisonReport) =>
    standsOn(f) !== "MISMATCH" && (showOriginal || !(draft.decisions[f.field] || draft.corrections[f.field]));
  const [openQuiet, setOpenQuiet] = useState<Record<string, boolean>>({});
  const renderCard = (f: FieldComparisonReport) => (
    <FieldComparisonRow
      comparison={f}
      priorCount={priorDefectCounts?.[f.field] ?? 0}
      decision={decideOn ? (draft.decisions[f.field] ?? null) : undefined}
      corrections={decideOn ? draft.corrections[f.field] : undefined}
      onCorrect={decideOn ? (side, v) => correct(f.field, side, v) : undefined}
      verdict={decideOn && draft.corrections[f.field] ? report.review?.field_verdicts?.[f.field]?.verdict : undefined}
      reason={decideOn && draft.corrections[f.field] ? report.review?.field_verdicts?.[f.field]?.reason : undefined}
      busy={review?.busy === f.field}
      justSaved={review?.flash === f.field}
    />
  );

  // -- the whole-case findings ---------------------------------------------
  //
  // The review box asks one question, "do the SI and the BL match?", and
  // every button is a finding in plain words; Sentinel's own answer comes
  // first so agreeing is one click. Each finding is one of the draft's own
  // operations (the same choices the field cards make, for several fields
  // at once); the backend derives the outcome, never the page.
  const [panel, setPanel] = useState<"picker" | "adopt" | null>(null);
  const saving = review ? review.busy !== null : false;
  const standingDefects = report.fields.filter((f) => standsOn(f) === "MISMATCH").map((f) => f.field);
  function noMismatch() {
    if (!review) return;
    const decisions = { ...draft.decisions };
    for (const f of report.fields) {
      if (f.verdict === "MISMATCH") decisions[f.field] = "cleared";
      else if (f.verdict === "UNCOMPARABLE") decisions[f.field] = "fine";
      else delete decisions[f.field];
    }
    setPanel(null);
    review.commit({ ...draft, decisions, cantTell: false }, "case");
  }
  function mismatchOn(chosen: string[]) {
    if (!review) return;
    const picked = new Set(chosen);
    const decisions = { ...draft.decisions };
    for (const f of report.fields) {
      if (picked.has(f.field)) {
        if (f.verdict === "MISMATCH") delete decisions[f.field];
        else decisions[f.field] = "flagged";
      } else if (f.verdict === "MISMATCH") decisions[f.field] = "cleared";
      else if (decisions[f.field] === "flagged") delete decisions[f.field];
    }
    setPanel(null);
    review.commit({ ...draft, decisions, cantTell: false }, "case");
  }
  function cantTell() {
    if (!review) return;
    setPanel(null);
    review.commit({ ...draft, cantTell: true }, "case");
  }
  // The scan read-out (scan-transcript-card.tsx): what the model read on an
  // image-only page, per side, for the fields Sentinel itself could not
  // read. Evidence for a person, never a decision -- readers/scan.py's own
  // rule -- so the button opens a list the reviewer ticks after checking
  // each value against the image, and only their click saves anything;
  // illegible fields are left blank, never guessed. What they adopt is
  // saved as their own corrections and compared by the run's rules.
  const transcripts = { si: transcriptOf(report.documents.si), bl: transcriptOf(report.documents.bl) };
  const readOutRows: ReadOutRow[] = report.fields.map((f) => {
    const read = (side: "si" | "bl") => {
      if (f[side].present) return null;
      const t = transcripts[side]?.fields.find((x) => x.field === f.field);
      return t && t.legible && t.value.trim() ? t.value.trim() : null;
    };
    return { field: f.field, si: read("si"), bl: read("bl") };
  });
  const hasReadOut = readOutRows.some((r) => r.si || r.bl);
  const readOutModel = Array.from(new Set([transcripts.si?.model, transcripts.bl?.model].filter(Boolean))).join(" / ");
  function adoptReadOut(chosen: string[]) {
    if (!review) return;
    const corrections = { ...draft.corrections };
    for (const r of readOutRows) {
      if (!chosen.includes(r.field)) continue;
      const sides = { ...(corrections[r.field] ?? {}) };
      if (r.si) sides.si = r.si;
      if (r.bl) sides.bl = r.bl;
      corrections[r.field] = sides;
    }
    const provenance = `Values adopted from the scan read-out (${readOutModel}) by the reviewer after checking them against the scan.`;
    setPanel(null);
    review.commit({ ...draft, corrections, cantTell: false, note: draft.note.trim() ? draft.note : provenance }, "case");
  }
  const listNames = (names: string[]) =>
    names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  const defectNames = report.defect_fields.map((f) => FIELD_LABELS[f] ?? f);
  const legibleSummary = (["si", "bl"] as const)
    .filter((s) => transcripts[s])
    .map((s) => `${transcripts[s]!.legible_count} of ${transcripts[s]!.fields.length} on the ${s.toUpperCase()}`)
    .join(", ");
  const togglePanel = (which: "picker" | "adopt") => setPanel(panel === which ? null : which);
  const findingButton = (label: string, onClick: () => void, title: string, primary = false, expanded?: boolean) => (
    <Button
      size="sm"
      variant={primary ? "default" : "outline"}
      disabled={saving}
      onClick={onClick}
      title={title}
      aria-expanded={expanded}
    >
      {label}
    </Button>
  );
  const finding: { heading: string; line: string; buttons: ReactNode } | null =
    !review || !comparison
      ? null
      : report.status === "MISMATCH"
        ? {
            heading: "Sentinel found a mismatch",
            line: `${listNames(defectNames)} differ${defectNames.length === 1 ? "s" : ""} between the SI and the BL — each value below carries the line it was read from.`,
            buttons: (
              <>
                {findingButton(
                  "Agree — it's a mismatch",
                  review.confirm,
                  "You checked the cards and the documents really differ there: record that you agree with Sentinel",
                  true,
                )}
                {findingButton(
                  "Change the fields…",
                  () => togglePanel("picker"),
                  "Adjust which fields differ: untick one Sentinel flagged, tick one it missed",
                  false,
                  panel === "picker",
                )}
                {findingButton(
                  "No mismatch",
                  noMismatch,
                  "The flagged values are the same thing written two ways: take them all off the list; Sentinel's reading stays on the record",
                )}
                {findingButton("Can't tell", cantTell, "Send the whole case to Needs review: you looked and could not decide")}
              </>
            ),
          }
        : report.status === "OK"
          ? {
              heading: "No mismatch found",
              line: `All ${report.fields.length} fields agree, each with the line it was read from. Agree to sign it off, or say what Sentinel missed.`,
              buttons: (
                <>
                  {findingButton("Agree — no mismatch", review.confirm, "You looked and nothing is wrong: sign the case off", true)}
                  {findingButton(
                    "Mismatch…",
                    () => togglePanel("picker"),
                    "Pick the fields that differ; Sentinel's evidence stays beside your call",
                    false,
                    panel === "picker",
                  )}
                  {findingButton("Can't tell", cantTell, "Send the whole case to Needs review: you looked and could not decide")}
                </>
              ),
            }
          : report.fields.length > 0
            ? {
                heading: "Decide it yourself",
                line: hasReadOut
                  ? `The model read the scans for you (${legibleSummary}). Adopt what you have checked against the image and the rules compare the pair — or decide it below.`
                  : "Look at the documents, then say what you found. Values can be entered on the cards below.",
                buttons: (
                  <>
                    {hasReadOut && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={saving}
                        aria-expanded={panel === "adopt"}
                        onClick={() => togglePanel("adopt")}
                        title="The model's reading of each scan, for you to adopt field by field after checking it against the image; the rules then compare the pair"
                      >
                        <Sparkles className="size-4 text-ai" />
                        Use the scan read-out
                      </Button>
                    )}
                    {findingButton("No mismatch", noMismatch, "You read both documents: the fields Sentinel could not compare are fine")}
                    {findingButton(
                      "Mismatch…",
                      () => togglePanel("picker"),
                      "Pick the fields that differ; Sentinel's evidence stays beside your call",
                      false,
                      panel === "picker",
                    )}
                    {findingButton("Still can't tell", cantTell, "Leave it in review: you looked and could not decide either")}
                  </>
                ),
              }
            : {
                heading: "Decide it yourself",
                line: "Nothing could be compared. Attach the re-sent documents, or leave it in review.",
                buttons: findingButton("Still can't tell", cantTell, "Leave it in review: you looked and could not decide either"),
              };
  const rowEnd = !showWorkspace ? (
    <RowEnd>
      <ReplyDraftPanel key={replyDraftKey(report)} report={report} />
    </RowEnd>
  ) : null;
  const recheckArea =
    recheckOpen && offerRecheck && onRecheck ? (
      <div data-spotlight="recheck">
        <RecheckPanel report={report} onRecheck={onRecheck} rechecking={rechecking} onClose={() => setRecheckOpen(false)} />
      </div>
    ) : null;
  const belowRow =
    review && (panel !== null || recheckArea) ? (
      <div className="flex flex-col gap-3">
        {panel === "picker" && (
          <FieldPicker fields={report.fields} initial={standingDefects} busy={saving} onSave={mismatchOn} onCancel={() => setPanel(null)} />
        )}
        {panel === "adopt" && (
          <ScanAdoptPanel rows={readOutRows} model={readOutModel} busy={saving} onSave={adoptReadOut} onCancel={() => setPanel(null)} />
        )}
        {recheckArea}
      </div>
    ) : null;

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
        <h2 className="text-lg font-semibold">{report.email_id}</h2>
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

      {/* A comparison request gets the review box; anything else has no
          documents to compare, and says so in one line instead of offering
          a sign-off with nothing behind it. */}
      {review && !comparison && (
        <motion.p className="text-sm text-muted-foreground" variants={fadeUp} data-testid="nothing-to-review">
          Sorted as {CATEGORY_BADGE_LABELS[report.category]} — not a document check, so there is nothing to review.
        </motion.p>
      )}

      {/* Right under the "why", not after every field — a reviewer landing
          here should see what to do before they see the evidence, not after
          scrolling past all of it. One row holds everything a reviewer can
          do with the whole case: the findings (Sentinel's own first, so
          agreeing is one click), the re-sent SI/BL (the area opens under
          the row) and, on a case that is not escalated, the reply draft at
          the row's end. On an escalated case the draft sits in the
          workspace's "what to do" above -- never in both places. */}
      {review && comparison && finding && (
        <motion.div variants={fadeUp} data-spotlight="review">
          {report.review ? (
            <ReviewSummary report={report} control={review} below={belowRow}>
              {recheckButton}
              {rowEnd}
            </ReviewSummary>
          ) : (
            <ReviewBox status={report.status} heading={finding.heading} line={finding.line} saving={saving} below={belowRow}>
              {finding.buttons}
              {recheckButton}
              {rowEnd}
            </ReviewBox>
          )}
        </motion.div>
      )}

      {/* /compare has no review box to hold it, so there the reply draft
          stands on its own. */}
      {!review && !showWorkspace && (
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
            <ul className="mt-1 list-inside list-disc">
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
      {report.fields.length > 0 && (
        <motion.div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground" variants={fadeUp}>
          {report.fields.length} fields compared
        </motion.div>
      )}

      {report.fields.length > 0 && (
        <motion.div className="flex flex-col gap-2" variants={stagger(0, 0.05)} data-spotlight="fields">
          {report.fields.map((f) => {
            const quiet = isQuiet(f);
            const open = quiet && Boolean(openQuiet[f.field]);
            return (
              <motion.div key={f.field} variants={fadeUp} data-spotlight={f.field === historyField ? "history" : undefined}>
                {quiet ? (
                  <QuietFieldRow
                    comparison={f}
                    open={open}
                    onToggle={() => setOpenQuiet((s) => ({ ...s, [f.field]: !s[f.field] }))}
                  >
                    {open && renderCard(f)}
                  </QuietFieldRow>
                ) : (
                  renderCard(f)
                )}
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </motion.div>
  );
}
