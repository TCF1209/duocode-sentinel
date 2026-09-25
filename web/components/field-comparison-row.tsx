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
                was <span className="line-through decoration-muted-foreground/60">{sentinelText}</span> · changed by you
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

// For the badge's hover when a person overrode Sentinel on this field.
const VERDICT_WORD: Record<Verdict, string> = { MATCH: "a match", MISMATCH: "a mismatch", UNCOMPARABLE: "uncomparable" };

/**
 * One field as a card: the name, one badge for what stands, both values
 * with the lines they were read from, and -- only where there is something
 * to correct -- Edit on a value. Decisions are not made here any more:
 * the review box above holds them (No mismatch, the field picker), and
 * the card only shows their effect. The user's reading of the old header
 * ("1 other case from this shipper · Flag as mismatch · Match · Mismatch"):
 * four things where one would do.
 */
export function FieldComparisonRow({
  comparison,
  priorCount = 0,
  decision,
  corrections,
  onCorrect,
  verdict,
  reason,
  busy,
  justSaved,
}: {
  comparison: FieldComparisonReport;
  /** Other cases from this case's shipper, in this run, already flagged on
   *  this same field. Named beside the field when it is a mismatch --
   *  "same shipper, same field, again". */
  priorCount?: number;
  /** The reviewer's call on this field, made in the review box: saved, or
   *  being saved. Absent under "Sentinel's original" and on /compare. */
  decision?: FieldDecision | null;
  /** The reviewer's corrected values on this field, per side. */
  corrections?: { si?: string; bl?: string };
  /** Save a corrected value on a side. Offered only where there is
   *  something to correct: a field that differs or could not be read, or
   *  one already corrected (so it can be undone) -- a pair that agrees has
   *  nothing to edit. */
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
  // What stands on this field: the reviewer's call, else the corrected
  // pair's verdict, else Sentinel's own. One badge says it; where a person
  // overrode Sentinel, the badge's hover says what Sentinel read -- the
  // review box keeps both answers in full, so the card stays quiet.
  const standing: Verdict =
    decision === "cleared" || decision === "fine" ? "MATCH" : decision === "flagged" ? "MISMATCH" : effectiveVerdict;
  const overridden = standing !== comparison.verdict;
  const editable = Boolean(onCorrect) && (comparison.verdict !== "MATCH" || corrected);
  const showHistory = comparison.verdict === "MISMATCH" && priorCount > 0;
  return (
    <div className={cn("rounded-lg border p-3 transition-colors", CARD_STYLE[standing])}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
          {/* A label, styled like the other section labels on this page,
              so the values under it are what the eye lands on. */}
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {FIELD_LABELS[comparison.field] ?? comparison.field}
          </div>
          {showHistory && (
            <span
              className="text-xs text-warn"
              title="Other cases from this shipper in this run with a mismatch on this same field -- this is not a one-off"
            >
              same shipper, same field: {priorCount} other case{priorCount === 1 ? "" : "s"} in this run
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {busy ? (
            <span className="text-xs text-muted-foreground">Saving…</span>
          ) : justSaved ? (
            <span className="text-xs font-medium text-ok">Saved</span>
          ) : null}
          <span title={overridden ? `Sentinel read this as ${VERDICT_WORD[comparison.verdict]}; what stands is your call` : undefined}>
            <VerdictBadge verdict={standing} />
          </span>
        </div>
      </div>
      {effectiveReason && <p className="mb-2 text-xs text-muted-foreground">{formatReason(effectiveReason)}</p>}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Side
          value={comparison.si}
          side="si"
          correction={corrections?.si}
          onCorrect={editable && onCorrect ? (v) => onCorrect("si", v) : undefined}
          busy={busy}
        />
        <Side
          value={comparison.bl}
          side="bl"
          correction={corrections?.bl}
          onCorrect={editable && onCorrect ? (v) => onCorrect("bl", v) : undefined}
          busy={busy}
        />
      </div>
    </div>
  );
}

/**
 * A field nobody has touched that is not a mismatch, as one line: the
 * field, what the documents carry, and its badge -- so all seven fields
 * stay on the page, in order, without clean cards pushing the ones that
 * differ down (the user's ask: "I only saw the ones I had to change"). A
 * field Sentinel could not compare is the same line in amber, with its
 * reason, instead of seven near-identical amber cards when a document
 * could not be read at all. A click opens the full card, evidence and
 * controls and all, right under the line; `children` is that card.
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
  const uncomparable = comparison.verdict === "UNCOMPARABLE";
  const si = (comparison.si.raw ?? "").trim();
  const bl = (comparison.bl.raw ?? "").trim();
  const sideText = (present: boolean, text: string) => (present && text ? text : "—");
  // The two readings agree once normalised; where they differ to the eye
  // (case, spacing, a trailing "LTD.") both are shown, so the line never
  // lets one stand in for the other.
  const differs = si !== bl;
  const value = uncomparable
    ? `SI: ${sideText(comparison.si.present, si)} · BL: ${sideText(comparison.bl.present, bl)}`
    : si || bl;
  const tail = uncomparable
    ? comparison.reason
      ? formatReason(comparison.reason)
      : null
    : differs
      ? `BL: ${bl}`
      : null;
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        title={open ? "Fold this field back to one line" : "Open this field: both readings, the lines they came from, and your choices"}
        className={cn(
          "flex w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-left transition-colors",
          uncomparable ? "border-warn/30 bg-warn-bg/40 hover:bg-warn-bg/70" : "bg-card hover:bg-muted/40",
        )}
      >
        <Chevron className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
        <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground sm:w-36">{label}</span>
        {/* On a phone the badge closes the first line and the value takes a
            line of its own under the label (a long label left the value a
            few characters wide); from `sm` up all four sit on one line and
            the value is truncated, the title holding all of it. */}
        <span className="ml-auto sm:order-last sm:ml-0">
          <VerdictBadge verdict={comparison.verdict} />
        </span>
        <span
          className="basis-full pl-7 text-sm font-medium break-words sm:min-w-0 sm:flex-1 sm:basis-auto sm:truncate sm:pl-0"
          title={tail ? `${value} · ${tail}` : value}
        >
          {value}
          {tail && <span className="font-normal text-muted-foreground"> · {tail}</span>}
        </span>
      </button>
      {open && children}
    </div>
  );
}
