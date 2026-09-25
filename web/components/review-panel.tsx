"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/status-badges";
import { FIELD_LABELS, STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { CaseReport, CaseStatus, FieldCorrection, FieldDecision, ReviewBody } from "@/lib/api";

const STATUS_OPTIONS: CaseStatus[] = ["OK", "MISMATCH", "NEEDS_REVIEW"];

/** "Mismatch on Container Count, Port of Discharge" / "No mismatch" -- one
 *  outcome as a phrase, for the before/after lines in the reviewed state
 *  (and the same lines in recheck-panel.tsx, which reuses it). */
export function describeOutcome(status: CaseStatus, defectFields: string[]): string {
  const label = STATUS_LABELS[status];
  if (status !== "MISMATCH" || defectFields.length === 0) return label;
  return `${label} on ${defectFields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}`;
}

/**
 * The review as the reviewer builds it, one change at a time on the field
 * cards (field-comparison-row.tsx): a value corrected on a side, a one-click
 * choice on a field, "I can't tell", and a note. Each change is saved as it
 * is made (case-detail-page-view.tsx), so this is also exactly what the
 * saved review holds -- `draftFromReview` reads one back into the other
 * shape without loss. The outcome is never computed here: the backend
 * compares a corrected pair with the run's own rules and derives it
 * (backend/api/review_outcome.py); the page shows what comes back.
 */
export interface CorrectionDraft {
  decisions: Record<string, FieldDecision>;
  corrections: Record<string, FieldCorrection>;
  /** "I can't tell" -- the whole case goes to Needs review regardless. */
  cantTell: boolean;
  note: string;
}

export const EMPTY_DRAFT: CorrectionDraft = { decisions: {}, corrections: {}, cantTell: false, note: "" };

/** True when the draft changes nothing about Sentinel's answer: no field
 *  decided, no value corrected, not "can't tell". A note alone is not a
 *  review. */
export function isEmptyDraft(draft: CorrectionDraft): boolean {
  return Object.keys(draft.decisions).length === 0 && Object.keys(draft.corrections).length === 0 && !draft.cantTell;
}

/** The saved review, as a draft to change. */
export function draftFromReview(report: CaseReport): CorrectionDraft {
  const r = report.review;
  if (!r) return EMPTY_DRAFT;
  if (r.decisions) {
    return {
      decisions: { ...r.decisions },
      corrections: { ...(r.corrections ?? {}) },
      cantTell: r.cant_tell ?? false,
      note: r.note ?? "",
    };
  }
  // A record from before per-field choices existed: read them back off the
  // outcome. A mismatch not on its list was cleared; a field on the list
  // Sentinel did not flag was flagged.
  const decisions: Record<string, FieldDecision> = {};
  if (r.decision === "correct") {
    for (const f of report.fields) {
      const listed = r.defect_fields.includes(f.field);
      if (f.verdict === "MISMATCH" && !listed) decisions[f.field] = "cleared";
      else if (f.verdict !== "MISMATCH" && listed) decisions[f.field] = "flagged";
    }
  }
  return { decisions, corrections: {}, cantTell: r.decision === "correct" && r.status === "NEEDS_REVIEW", note: r.note ?? "" };
}

/** The request that saves a draft: a whole-case confirmation when it changes
 *  nothing, a correction otherwise -- the choices and corrected values
 *  themselves, so the backend derives the outcome and the review reads back
 *  as it was made. */
export function reviewBody(draft: CorrectionDraft): ReviewBody {
  const note = draft.note.trim() || undefined;
  if (isEmptyDraft(draft)) {
    return { decision: "confirm", note, decisions: {}, corrections: {}, cant_tell: false };
  }
  return {
    decision: "correct",
    note,
    decisions: draft.decisions,
    corrections: draft.corrections,
    cant_tell: draft.cantTell,
  };
}

/**
 * How the case page saves a review, handed to the report and its field
 * cards (case-detail-page-view.tsx owns the requests). Every change is
 * saved as it is made: there is no draft waiting for a button.
 */
export interface ReviewController {
  /** The review as it stands: saved, or the change being saved right now. */
  draft: CorrectionDraft;
  /** What is being saved -- a field key, or "case" for a whole-case change
   *  -- and null when idle. */
  busy: string | null;
  /** What was saved a moment ago (same keys as `busy`), for a brief "Saved"
   *  where the change was made; null otherwise. */
  flash: string | null;
  /** Save a changed draft. Emptied, it withdraws the review instead. */
  commit: (next: CorrectionDraft, what: string) => void;
  /** Sign Sentinel's answer off as it stands. */
  confirm: () => void;
  /** Take the whole review back. */
  withdraw: () => void;
  /** The whole-case form, for a case with no field cards to decide on. */
  submitLegacy: (body: ReviewBody) => Promise<void>;
}

// How urgently this panel should read, keyed to the same status the rest of
// the app already colors by — an OK case can still be reviewed, but it
// hasn't earned a warn/danger-tinted card the way an actual problem has.
//
// The heading and description differ for OK on purpose, not just the color:
// "Human review" on a case that already matched on all 7 fields reads as
// "something might be wrong here", which is the opposite of what a clean
// case means. This panel exists on every case regardless of outcome — it is
// an operator sign-off with an audit trail, not an escalation flag — and
// only the MISMATCH/NEEDS_REVIEW copy is actually about a score not being
// trustworthy enough to skip a person.
//
// One sentence each, naming the buttons on the row under it, in two
// versions: `description` for the case with field cards (values are edited
// there), `whole` for a case with nothing comparable, where the outcome is
// picked in this panel. `recheck` says whether "Attach re-sent SI/BL" is on
// the row, so the sentence never promises a button that is not there.
// Decided directly: a first-time visitor should see what to do here at a
// glance, not read a paragraph about what confirming means.
const URGENCY: Record<
  CaseStatus,
  {
    container: string;
    icon: string;
    heading: string;
    description: (recheck: boolean) => string;
    whole: (recheck: boolean) => string;
  }
> = {
  OK: {
    container: "bg-card",
    icon: "",
    heading: "Confirm this outcome",
    // "No mismatch", not "matched": the same wording rule as STATUS_LABELS
    // (lib/labels.ts) -- judges read "matched" as a claim about the tool.
    description: () => "Nothing to fix. Confirm to sign off, or edit a value on its card below.",
    whole: () => "Nothing to fix. Confirm to sign off, or correct it.",
  },
  MISMATCH: {
    container: "border-danger/40 bg-danger-bg",
    icon: "text-danger",
    heading: "Review this mismatch",
    description: (recheck) =>
      recheck
        ? "Confirm it, say you can't tell, or attach the re-sent documents. To fix a value, edit it on its card below."
        : "Confirm it, or say you can't tell. To fix a value, edit it on its card below.",
    whole: (recheck) =>
      recheck ? "Confirm it, correct the outcome, or attach the re-sent documents." : "Confirm it, or correct the outcome.",
  },
  NEEDS_REVIEW: {
    container: "border-warn/40 bg-warn-bg",
    icon: "text-warn",
    // Third section of the needs-review workspace (case-report-view.tsx),
    // after "why this needs a person" and "what to do": the fallback for
    // a reviewer who has looked at the documents themselves.
    heading: "Decide it yourself",
    description: (recheck) =>
      recheck
        ? "Enter or edit the values on the cards, attach the re-sent documents, or confirm it couldn't be checked."
        : "Enter or edit the values on the cards, or confirm it couldn't be checked.",
    whole: (recheck) =>
      recheck
        ? "Can tell what the documents say? Correct it. Or attach the re-sent documents, or confirm it couldn't be checked."
        : "Can tell what the documents say? Correct it. Or confirm it couldn't be checked.",
  },
};

/** The note, saved when the reviewer clicks away -- there is no Save button
 *  anywhere in the in-place review, and the note is no exception. Uncontrolled
 *  on purpose: the value only leaves the box on blur, and the caller remounts
 *  it (key) when the saved note changes underneath. */
function NoteField({ value, onSave }: { value: string; onSave: (note: string) => void }) {
  return (
    <Textarea
      defaultValue={value}
      placeholder="Add a note (optional) — saved when you click away"
      aria-label="Review note"
      rows={1}
      className="mt-2 min-h-8 bg-background/60"
      onBlur={(e) => {
        const next = e.currentTarget.value;
        if (next.trim() !== value.trim()) onSave(next);
      }}
    />
  );
}

export function ReviewPanel({
  report,
  control,
  inPlace,
  canRecheck = false,
  actions,
  trailing,
  children,
}: {
  report: CaseReport;
  control: ReviewController;
  /** True when the case has field cards a reviewer can decide on; the
   *  panel is then the whole-case actions and, once reviewed, the summary
   *  of what stands. False for a case with nothing comparable (a missing
   *  or unreadable document), where the outcome is picked here directly. */
  inPlace: boolean;
  /** "Attach re-sent SI/BL" is among `actions`, so the sentence can say so. */
  canRecheck?: boolean;
  /** More buttons for the row of whole-case actions (case-report-view.tsx
   *  puts the re-sent documents button here). */
  actions?: ReactNode;
  /** What ends that row: the reply draft, whose trigger is a button and
   *  whose open panel is a card -- the wrapper gives the card a full line
   *  of its own. */
  trailing?: ReactNode;
  /** Rendered under the row, inside the box: the re-sent documents area
   *  while it is open. */
  children?: ReactNode;
}) {
  const [legacyMode, setLegacyMode] = useState<"confirm" | "correct" | null>(null);
  const [legacyStatus, setLegacyStatus] = useState<CaseStatus>(report.status);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { draft } = control;
  const saving = control.busy !== null;
  const savedCase = control.flash === "case";

  // The end of the actions row and what goes under it, the same on every
  // state of the panel. `data-spotlight="reply"` is the home tile's target
  // for the reply draft; an escalated case carries it in the workspace
  // instead, and the two are never both on the page. The `:has(>div)`
  // variant is the draft panel's open state (its trigger is a button, its
  // panel a div): open, it drops onto a full line under the buttons.
  const tail = (
    <>
      {actions}
      {trailing && (
        <div data-spotlight="reply" className="ml-auto max-w-full [&:has(>div)]:mt-1 [&:has(>div)]:basis-full">
          {trailing}
        </div>
      )}
    </>
  );
  const below = children ? <div className="mt-3">{children}</div> : null;

  if (report.review) {
    // What changed, in one glance, for a correction: Sentinel's own answer
    // on the left, what now stands on the right. The field cards below show
    // the same thing one field at a time; this is the whole case at once,
    // asked for as "keep the unchanged version visible to whoever changed it".
    const after = report.effective ?? {
      status: report.review.status,
      defect_fields: report.review.defect_fields,
    };
    const corrected = report.review.decision === "correct";
    // Each corrected value, with what Sentinel read: the audit line.
    const corrections = Object.entries(draft.corrections).flatMap(([f, sides]) =>
      (["si", "bl"] as const)
        .filter((side) => sides[side] !== undefined)
        .map((side) => {
          const original = report.fields.find((x) => x.field === f)?.[side];
          return { key: `${f}:${side}`, field: FIELD_LABELS[f] ?? f, side: side.toUpperCase(), was: original?.raw ?? "(not read)", now: sides[side]! };
        }),
    );
    return (
      <div className="rounded-lg border bg-muted/40 p-4 text-sm" data-testid="review-summary">
        <div className="flex flex-wrap items-center gap-2 font-medium">
          {!corrected ? (
            "Reviewed: confirmed as-is"
          ) : draft.cantTell ? (
            <>
              Reviewed: sent to <StatusBadge status="NEEDS_REVIEW" /> <span className="font-normal">— couldn&apos;t tell</span>
            </>
          ) : (
            <>
              Reviewed: corrected to <StatusBadge status={report.review.status} />
            </>
          )}
          {saving ? (
            <span className="text-xs font-normal text-muted-foreground">Saving…</span>
          ) : savedCase ? (
            <span className="text-xs font-normal text-ok">Saved</span>
          ) : null}
        </div>
        {corrected && (
          <div className="mt-2 grid gap-x-3 gap-y-0.5 text-xs sm:grid-cols-[auto_1fr]">
            <span className="text-muted-foreground">Sentinel said</span>
            <span>{describeOutcome(report.status, report.defect_fields)}</span>
            <span className="text-muted-foreground">Now</span>
            <span className="font-medium">{describeOutcome(after.status, after.defect_fields)}</span>
          </div>
        )}
        {corrections.length > 0 && (
          <ul className="mt-1 text-xs text-muted-foreground">
            {corrections.map((c) => (
              <li key={c.key}>
                {c.field} · {c.side}: <span className="line-through">{c.was}</span> →{" "}
                <span className="font-medium text-foreground">{c.now}</span>
              </li>
            ))}
          </ul>
        )}
        {report.review.reviewer && <div className="mt-1 text-muted-foreground">by {report.review.reviewer}</div>}
        {inPlace ? (
          <>
            <NoteField key={draft.note} value={draft.note} onSave={(n) => control.commit({ ...draft, note: n }, "case")} />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant={draft.cantTell ? "default" : "outline"}
                onClick={() => control.commit({ ...draft, cantTell: !draft.cantTell }, "case")}
                title={
                  draft.cantTell
                    ? "Take back \"I can't tell\": the outcome goes back to what the field choices say"
                    : "Send the whole case to Needs review: you looked and could not decide"
                }
              >
                {draft.cantTell ? "Needs review — undo" : "I can't tell"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={control.withdraw}
                title="Take this review back altogether: Sentinel's answer stands and nobody has signed it off"
              >
                <Undo2 className="size-3.5" />
                Undo review
              </Button>
              {tail}
            </div>
            {below}
          </>
        ) : (
          <>
            {report.review.note && (
              <div className="mt-1 whitespace-pre-line text-muted-foreground">&ldquo;{report.review.note}&rdquo;</div>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={control.withdraw}
                title="Take this review back: Sentinel's answer stands and nobody has signed it off"
              >
                <Undo2 className="size-3.5" />
                Undo review
              </Button>
              {tail}
            </div>
            {below}
          </>
        )}
      </div>
    );
  }

  const urgency = URGENCY[report.status];

  async function submit(body: ReviewBody) {
    setBusy(true);
    setError(null);
    try {
      await control.submitLegacy(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!inPlace) {
    // A case with nothing to decide field by field: pick the outcome here.
    return (
      <div className={cn("rounded-lg border p-4", urgency.container)}>
        <div className="mb-3 flex items-center gap-2">
          {report.status !== "OK" && <AlertTriangle className={cn("size-4", urgency.icon)} strokeWidth={2} />}
          <div className={cn("text-sm font-semibold", urgency.icon)}>{urgency.heading}</div>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">{urgency.whole(canRecheck)}</p>
        {legacyMode === "correct" ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              {STATUS_OPTIONS.map((s) => (
                <Button key={s} size="sm" variant={s === legacyStatus ? "default" : "outline"} onClick={() => setLegacyStatus(s)}>
                  {STATUS_LABELS[s]}
                </Button>
              ))}
            </div>
            <Textarea placeholder="Why? (optional)" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={busy}
                onClick={() =>
                  submit({
                    decision: "correct",
                    status: legacyStatus,
                    // MISMATCH needs its fields; a case with nothing comparable
                    // has none to name, so it keeps Sentinel's list.
                    defect_fields: legacyStatus === "MISMATCH" ? report.defect_fields : [],
                    note: note || undefined,
                  })
                }
              >
                {busy ? "Saving…" : "Save correction"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setLegacyMode(null)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy} onClick={() => submit({ decision: "confirm", note: note || undefined })}>
              {busy ? "Saving…" : "Confirm outcome"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setLegacyMode("correct")}>
              Correct it
            </Button>
            {tail}
          </div>
        )}
        {below}
        {error && <p className="mt-2 text-xs text-danger">{error}</p>}
      </div>
    );
  }

  // In place, nothing saved yet: the whole-case actions. The field choices
  // are made and saved on the cards themselves -- this block does not follow
  // the reviewer down the page, and there is nothing here to come back up
  // for. Decided directly: "put the correction where the mismatch is".
  return (
    <div className={cn("rounded-lg border p-4", urgency.container)} data-testid="review-actions">
      <div className="flex flex-wrap items-center gap-2">
        {report.status !== "OK" && <AlertTriangle className={cn("size-4", urgency.icon)} strokeWidth={2} />}
        <div className={cn("text-sm font-semibold", urgency.icon)}>{urgency.heading}</div>
        {saving && <span className="text-xs text-muted-foreground">Saving…</span>}
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">{urgency.description(canRecheck)}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={saving} onClick={control.confirm} title="Record that you looked and agree with Sentinel's answer as it stands">
          Confirm outcome
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={saving}
          onClick={() => control.commit({ ...draft, cantTell: true }, "case")}
          title="Send the whole case to Needs review: you looked and could not decide"
        >
          I can&apos;t tell
        </Button>
        {tail}
      </div>
      {below}
    </div>
  );
}
