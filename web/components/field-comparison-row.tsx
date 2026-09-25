import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Pencil, Undo2 } from "lucide-react";
import type { FieldComparisonReport, FieldDecision, FieldValueReport, Verdict } from "@/lib/api";
import { cn } from "@/lib/utils";
import { VerdictBadge } from "@/components/status-badges";
import { FIELD_LABELS } from "@/lib/labels";

export type DocSideKey = "si" | "bl";

/**
 * One side of a field: the value Sentinel read, with the line it was read
 * from -- or, once a reviewer has corrected it, the value they typed with
 * Sentinel's reading kept underneath ("was …"). Decided directly: when the
 * shipper confirms what a document should say, the reviewer changes the
 * value right here and saves; the pair is compared again by the backend
 * with the same rules the run used, and the outcome follows.
 */
function Side({
  value,
  side,
  correction,
  onCorrect,
  busy,
}: {
  value: FieldValueReport;
  side: DocSideKey;
  /** The reviewer's value for this side, when they corrected it. */
  correction?: string;
  /** Save a corrected value, or `null` to go back to Sentinel's reading.
   *  Absent where the value cannot be edited (Sentinel's original view,
   *  /compare, a reviewed-as-a-whole case). */
  onCorrect?: (value: string | null) => void;
  busy?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const label = side.toUpperCase();
  const sentinelText = value.present ? value.raw : value.blank ? "blank / placeholder value" : "not found";
  const shown = correction ?? value.raw ?? "";

  function save(next: string) {
    const text = next.trim();
    setEditing(false);
    if (!onCorrect) return;
    // Back to exactly what Sentinel read is the same as no correction.
    if (text === (value.raw ?? "").trim() || (!text && correction === undefined)) {
      if (correction !== undefined) onCorrect(null);
      return;
    }
    if (text !== (correction ?? "").trim()) onCorrect(text || null);
  }

  return (
    <div
      className={cn(
        "flex-1 rounded-md border p-3",
        !value.present && !correction && "border-dashed text-muted-foreground",
        correction !== undefined && "border-primary/40",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
        {onCorrect && !editing && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            disabled={busy}
            title={
              correction !== undefined
                ? "Change the corrected value"
                : `Edit the ${label} value — what the document should read`
            }
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Pencil className="size-3" strokeWidth={2} />
            {/* "Edit", not "Correct": beside a value, "Correct" read as a
                verdict ("this one is correct") rather than as the action. */}
            {correction !== undefined || value.present ? "Edit" : "Enter value"}
          </button>
        )}
      </div>
      {editing ? (
        <form
          className="mt-1 flex flex-col gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            save((new FormData(e.currentTarget).get("value") as string) ?? "");
          }}
        >
          <input
            name="value"
            type="text"
            autoFocus
            defaultValue={shown}
            aria-label={`${label} value`}
            placeholder={`What the ${label} should read`}
            onKeyDown={(e) => {
              if (e.key === "Escape") setEditing(false);
            }}
            className="w-full rounded-md border bg-background px-2 py-1 text-sm font-semibold"
          />
          <div className="flex items-center gap-1.5 text-xs">
            <button type="submit" className="rounded-md bg-primary px-2.5 py-1 font-medium text-primary-foreground">
              Save
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded-md px-2 py-1 text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <span className="text-muted-foreground">Enter saves · Esc cancels</span>
          </div>
        </form>
      ) : (
        <>
          {/* Not font-mono: the source data is almost always an already-
              upper-case company name, and monospace on a long upper-case
              run is one of the harder combinations to read at a glance. The
              value is the one element on the card set larger and heavier
              than everything around it -- the field name above is a label,
              the evidence below is a citation. */}
          <div className={cn("mt-1 text-base font-semibold leading-snug", !value.present && !correction && "font-normal text-sm")}>
            {correction ?? sentinelText}
          </div>
          {correction !== undefined && (
            <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
              <span>
                was <span className="line-through decoration-muted-foreground/60">{sentinelText}</span> · corrected by reviewer
              </span>
              {onCorrect && (
                <button
                  type="button"
                  onClick={() => onCorrect(null)}
                  disabled={busy}
                  title="Back to what Sentinel read"
                  className="inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Undo2 className="size-3" strokeWidth={2} />
                  Undo
                </button>
              )}
            </div>
          )}
        </>
      )}
      {value.evidence && correction === undefined && !editing && (
        <div className="mt-2 border-t pt-2 text-xs text-muted-foreground">
          <div>
            {value.evidence.doc} &middot; {value.evidence.locator} &middot; label &quot;{value.evidence.label}&quot;
            {value.extractor !== "rule" && (
              <span className="ml-1 rounded bg-ai-bg px-1 py-0.5 text-ai">{value.extractor}</span>
            )}
          </div>
          {/* A left border reads as "this is a quote" on its own, so the
              snippet needs no distinct typeface to tell it apart from the
              value above. */}
          <div className="mt-1.5 border-l-2 border-muted-foreground/25 pl-2 italic">
            &ldquo;{value.evidence.snippet.trim()}&rdquo;
          </div>
        </div>
      )}
    </div>
  );
}

// Mirrors the ok/warn/danger language used everywhere else: a mismatch is
// danger, an uncomparable field is a warn (it's *why* a case needs review,
// not a dead end), and a clean match stays plain so problem fields are the
// ones that visually jump out while scanning down the list.
const CARD_STYLE: Record<Verdict, string> = {
  MATCH: "bg-card",
  MISMATCH: "border-danger/30 bg-danger-bg/60",
  UNCOMPARABLE: "border-warn/30 bg-warn-bg/60",
};

// Most uncomparable reasons are a state ("BL missing") and read fine as a
// label. This one is a claim about the two values, and "Ocr confusable" tells
// a reviewer nothing about what to do -- they need to know that both readings
// are there and that the difference is in glyphs a scanner mixes up.
const REASON_TEXT: Record<string, string> = {
  ocr_confusable:
    "Same length, differing only in characters OCR confuses (O/0, I/1, S/5, B/8) -- likely one value read two ways. Check both against the pages.",
};

// "bl_missing" -> "BL missing", not "Bl missing" -- si/bl are the document
// acronyms this whole app is built around, so a generic capitalize-first-
// letter reads like a typo of them.
export function formatReason(reason: string) {
  const override = REASON_TEXT[reason];
  if (override) return override;
  const words = reason.split("_").map((w) => (w === "si" || w === "bl" ? w.toUpperCase() : w));
  const joined = words.join(" ");
  return joined.charAt(0).toUpperCase() + joined.slice(1);
}

/** How a reviewer's correction bears on this one field, when it does at all.
 *  "cleared": Sentinel called it a mismatch, the reviewer took it off the
 *  defect list. "flagged": Sentinel passed it (or couldn't compare it), the
 *  reviewer added it. Absent for every field a correction didn't touch, for
 *  every field of an unreviewed or merely-confirmed case, and on /compare,
 *  where nothing can be reviewed at all -- so this row renders exactly as it
 *  always has unless a person actually changed something about this field. */
export type ReviewerView = "cleared" | "flagged";

const REVIEWER_BADGE: Record<ReviewerView, { label: string; className: string; fallbackTitle: string }> = {
  cleared: {
    label: "Cleared by reviewer",
    className: "border-ok/40 bg-ok-bg text-ok",
    fallbackTitle: "Sentinel flagged this field as a mismatch; a reviewer took it off the defect list.",
  },
  flagged: {
    label: "Flagged by reviewer",
    className: "border-danger/40 bg-danger-bg text-danger",
    fallbackTitle: "Sentinel did not flag this field; a reviewer added it to the defect list.",
  },
};

// The reviewer's note is written once per case, not per field, so it is
// surfaced as a hover on every reviewer badge rather than pretended to
// belong to one of them -- "why was this cleared when the two values are
// visibly different" is exactly the question a reader has at this spot.
function ReviewerBadge({ view, note }: { view: ReviewerView; note?: string | null }) {
  const spec = REVIEWER_BADGE[view];
  return (
    <span
      className={cn("whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium", spec.className)}
      title={note ? `Reviewer's note: ${note}` : spec.fallbackTitle}
    >
      {spec.label}
    </span>
  );
}

/** The one-click choices for one field, given what stands on it. A
 *  mismatch can be taken off the list without touching the values ("the
 *  two are the same party"); a match can be flagged; an uncomparable field
 *  can be called fine or flagged. Correcting a value is the other, more
 *  precise way and lives on the value boxes below. The active choice is
 *  toggled off by clicking it again. */
function DecisionControls({
  verdict,
  decision,
  onDecide,
}: {
  verdict: Verdict;
  decision: FieldDecision | null;
  onDecide: (d: FieldDecision | null) => void;
}) {
  const options: { d: FieldDecision; label: string; title: string }[] =
    verdict === "MISMATCH"
      ? [{ d: "cleared", label: "Not a mismatch", title: "The two values are the same thing: take this field off the list" }]
      : verdict === "MATCH"
        ? [{ d: "flagged", label: "Flag as mismatch", title: "Sentinel missed it: these values do not agree" }]
        : [
            { d: "fine", label: "It's fine", title: "You read both documents: nothing wrong here" },
            { d: "flagged", label: "Flag as mismatch", title: "You read both documents: the values differ" },
          ];
  return (
    <div className="flex items-center rounded-full border bg-background p-0.5 text-xs" role="group" aria-label="Your decision on this field">
      {options.map((o) => {
        const active = decision === o.d;
        return (
          <button
            key={o.d}
            type="button"
            aria-pressed={active}
            title={active ? "Take this choice back" : o.title}
            onClick={() => onDecide(active ? null : o.d)}
            className={cn(
              "rounded-full px-2 py-0.5 transition-colors",
              active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function FieldComparisonRow({
  comparison,
  reviewerView = null,
  reviewerNote,
  priorCount = 0,
  decision,
  onDecide,
  corrections,
  onCorrect,
  verdict,
  reason,
  busy,
  justSaved,
}: {
  comparison: FieldComparisonReport;
  reviewerView?: ReviewerView | null;
  reviewerNote?: string | null;
  /** Other cases from this case's shipper, in this run, already flagged on
   *  this same field. Shown on the card itself when this field is a
   *  mismatch -- "same shipper, same field, again". */
  priorCount?: number;
  /** In-place review (review-panel.tsx): the reviewer's one-click choice on
   *  this field -- saved, or being saved -- and the handler to change it.
   *  Each change is saved as it is made. Absent under "Sentinel's original"
   *  and on /compare. */
  decision?: FieldDecision | null;
  onDecide?: (d: FieldDecision | null) => void;
  /** The reviewer's corrected values on this field, per side. */
  corrections?: { si?: string; bl?: string };
  onCorrect?: (side: DocSideKey, value: string | null) => void;
  /** The verdict and reason the corrected pair got from the backend
   *  (review.field_verdicts); Sentinel's own when absent. */
  verdict?: Verdict;
  reason?: string | null;
  /** This field's change is being saved right now / was saved a moment ago. */
  busy?: boolean;
  justSaved?: boolean;
}) {
  const corrected = Boolean(corrections?.si !== undefined || corrections?.bl !== undefined);
  const effectiveVerdict = verdict ?? comparison.verdict;
  const effectiveReason = corrected ? (reason ?? null) : comparison.reason;
  const showHistory = comparison.verdict === "MISMATCH" && priorCount > 0;
  const historyBadge = showHistory ? (
    <span
      className="whitespace-nowrap rounded-full border border-warn/40 bg-warn-bg px-2 py-0.5 text-xs font-medium text-warn"
      title="Other cases from this shipper in this run with a mismatch on this same field -- this is not a one-off"
    >
      {priorCount} other case{priorCount === 1 ? "" : "s"} from this shipper
    </span>
  ) : null;
  // The card's colour follows whichever judgement currently stands --
  // a corrected pair's new verdict, or the reviewer's one-click choice --
  // but Sentinel's own badge is never removed: dimmed, still legible,
  // still titled. "The system said X, a person said Y, here is what both
  // were looking at" is the whole point; hiding X would turn an audit
  // trail into a silent overwrite.
  const pendingView: ReviewerView | null =
    decision === "cleared" || decision === "fine" ? "cleared" : decision === "flagged" ? "flagged" : null;
  const effectiveView = reviewerView ?? pendingView;
  const cardStyle =
    effectiveView === "cleared"
      ? CARD_STYLE.MATCH
      : effectiveView === "flagged"
        ? CARD_STYLE.MISMATCH
        : CARD_STYLE[effectiveVerdict];
  const touched = Boolean(decision) || corrected;
  const overridden = Boolean(pendingView) || (corrected && effectiveVerdict !== comparison.verdict);
  return (
    <div className={cn("rounded-lg border p-3 transition-colors", cardStyle, touched && "ring-1 ring-primary/50")}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        {/* A label, styled like the other section labels on this page
            ("What to do", "Re-sent documents"), so the values under it are
            what the eye lands on. */}
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {FIELD_LABELS[comparison.field] ?? comparison.field}
        </div>
        {reviewerView ? (
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            {historyBadge}
            <span className="opacity-40" title="What Sentinel itself said">
              <VerdictBadge verdict={comparison.verdict} />
            </span>
            <ReviewerBadge view={reviewerView} note={reviewerNote} />
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            {historyBadge}
            {/* Where the click happened is where the answer shows: saving,
                then saved, beside the control itself. */}
            {onDecide && busy ? (
              <span className="text-xs text-muted-foreground">Saving…</span>
            ) : onDecide && justSaved ? (
              <span className="text-xs font-medium text-ok">Saved</span>
            ) : null}
            {onDecide && <DecisionControls verdict={effectiveVerdict} decision={decision ?? null} onDecide={onDecide} />}
            {/* After a correction the pair's new verdict leads and Sentinel's
                own reading stays beside it, dimmed. */}
            {corrected && effectiveVerdict !== comparison.verdict && <VerdictBadge verdict={effectiveVerdict} />}
            <span className={cn(overridden && "opacity-40")} title={overridden ? "What Sentinel itself read" : undefined}>
              <VerdictBadge verdict={comparison.verdict} />
            </span>
          </div>
        )}
      </div>
      {effectiveReason && <p className="mb-2 text-xs text-muted-foreground">{formatReason(effectiveReason)}</p>}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Side
          value={comparison.si}
          side="si"
          correction={corrections?.si}
          onCorrect={onCorrect ? (v) => onCorrect("si", v) : undefined}
          busy={busy}
        />
        <Side
          value={comparison.bl}
          side="bl"
          correction={corrections?.bl}
          onCorrect={onCorrect ? (v) => onCorrect("bl", v) : undefined}
          busy={busy}
        />
      </div>
    </div>
  );
}

/**
 * A field that agrees and nobody has touched, as one line: the field, the
 * value both documents carry, and the Match badge -- so all seven fields
 * stay on the page, in order, without five clean cards pushing the ones
 * that differ down (the user's ask: "I only saw the ones I had to
 * change"). A click opens the full card, evidence and all, right under
 * the line; `children` is that card.
 */
export function QuietFieldRow({
  comparison,
  open,
  onToggle,
  children,
}: {
  comparison: FieldComparisonReport;
  open: boolean;
  onToggle: () => void;
  children?: ReactNode;
}) {
  const label = FIELD_LABELS[comparison.field] ?? comparison.field;
  const si = (comparison.si.raw ?? "").trim();
  const bl = (comparison.bl.raw ?? "").trim();
  // The two readings agree once normalised; where they differ to the eye
  // (case, spacing, a trailing "LTD.") both are shown, so the line never
  // lets one stand in for the other.
  const differs = si !== bl;
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        title={open ? "Fold this field back to one line" : "Open this field: both readings and the lines they came from"}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border bg-card px-3 py-2 text-left transition-colors hover:bg-muted/40"
      >
        <Chevron className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
        <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground sm:w-36">{label}</span>
        {/* On a phone the badge closes the first line and the value takes a
            line of its own under the label (a long label left the value a
            few characters wide); from `sm` up all four sit on one line and
            the value is truncated, the title holding all of it. */}
        <span className="ml-auto sm:order-last sm:ml-0">
          <VerdictBadge verdict="MATCH" />
        </span>
        <span
          className="basis-full pl-7 text-sm font-medium break-words sm:min-w-0 sm:flex-1 sm:basis-auto sm:truncate sm:pl-0"
          title={differs ? `SI: ${si} · BL: ${bl}` : si}
        >
          {si || bl}
          {differs && <span className="font-normal text-muted-foreground"> · BL: {bl}</span>}
        </span>
      </button>
      {open && children}
    </div>
  );
}
