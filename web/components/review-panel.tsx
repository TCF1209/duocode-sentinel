"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Sparkles, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge, VerdictBadge } from "@/components/status-badges";
import { FIELD_LABELS, REVIEW_REASON_TEXT, STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { CaseReport, CaseStatus, FieldComparisonReport, FieldCorrection, FieldDecision, ReviewBody } from "@/lib/api";

/** "Discrepancy (Container Count, Port of Discharge)" / "No discrepancy" --
 *  one outcome as a phrase, for the before/after lines in the reviewed state
 *  (and the same lines in recheck-panel.tsx, which reuses it). Parentheses,
 *  not a colon: its callers already put it after "previous result:". */
export function describeOutcome(status: CaseStatus, defectFields: string[]): string {
  const label = STATUS_LABELS[status];
  if (status !== "MISMATCH" || defectFields.length === 0) return label;
  return `${label} (${defectFields.map((f) => FIELD_LABELS[f] ?? f).join(", ")})`;
}

/** Why Sentinel escalated a case, as a sentence. The gate files a pound
 *  figure and an OCR-confusable value under "unreadable" (the organisers'
 *  four reasons are fixed), and with both documents read "A document could
 *  not be read." would be false -- so there it says what is actually left. */
export function escalationText(report: CaseReport): string | null {
  if (!report.review_reason) return null;
  const bothRead = Boolean(report.documents.si?.readable && report.documents.bl?.readable);
  const valueToCheck = report.fields.some((f) => f.reason === "unit_differs" || f.reason === "ocr_confusable");
  if (report.review_reason === "unreadable" && bothRead && valueToCheck) return "A value needs a manual check.";
  return REVIEW_REASON_TEXT[report.review_reason];
}

/**
 * The review as the reviewer builds it, one change at a time: a finding on
 * the whole case (no discrepancy / discrepancy on these fields / escalate), a
 * one-click choice on a field card, a value corrected on a side, and a
 * note. Each change is saved as it is made (case-detail-page-view.tsx), so
 * this is also exactly what the saved review holds -- `draftFromReview`
 * reads one back into the other shape without loss. The outcome is never
 * computed here: the backend compares a corrected pair with the run's own
 * rules and derives it (backend/api/review_outcome.py); the page shows what
 * comes back.
 */
export interface CorrectionDraft {
  decisions: Record<string, FieldDecision>;
  corrections: Record<string, FieldCorrection>;
  /** "Escalate" (Unresolved) -- the whole case is Escalated regardless. */
  cantTell: boolean;
  note: string;
}

export const EMPTY_DRAFT: CorrectionDraft = { decisions: {}, corrections: {}, cantTell: false, note: "" };

/** True when the draft changes nothing about Sentinel's answer: no field
 *  decided, no value corrected, not Unresolved. A note alone is not a
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

/** The saved review is corrected values and nothing else: no call on any
 *  field, not Escalate / Keep escalated. The outcome then follows from the
 *  values alone, so the page says "After corrections" and offers "Record a
 *  decision" instead of "Reviewer decision" / "Change decision" (a first-time
 *  reviewer read those as a decision they had not made). One rule, read from
 *  the saved review, for the record, the header toggle and the button alike.
 *  A record from before per-field choices existed never counts. */
export function isValuesOnly(report: CaseReport): boolean {
  const saved = draftFromReview(report);
  return Object.keys(saved.corrections).length > 0 && Object.keys(saved.decisions).length === 0 && !saved.cantTell;
}

/** The request that saves a draft: a whole-case agreement when it changes
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
  /** Agree with Sentinel's answer as it stands. */
  confirm: () => void;
  /** Take the whole review back. */
  withdraw: () => void;
}

// The box follows the status the case stands at, in the same three tones
// the rest of the app colours by: green for a clean pair, red for a
// mismatch, amber for a case that needs a person -- the same colour its
// badge and its field cards carry (the user's ask: every status with its
// own colour, none left white).
const TONE: Record<CaseStatus, { container: string; icon: string }> = {
  OK: { container: "border-ok/40 bg-ok-bg", icon: "text-ok" },
  MISMATCH: { container: "border-danger/40 bg-danger-bg", icon: "text-danger" },
  NEEDS_REVIEW: { container: "border-warn/40 bg-warn-bg", icon: "text-warn" },
};
// Grey, for a case with nothing to compare yet: green there would claim a
// check that never ran.
const NEUTRAL_TONE = { container: "bg-muted/40", icon: "text-foreground" };

/**
 * The box a reviewer decides a case in: what Sentinel found, as a heading
 * and one line the page writes for the status the case stands at; one row
 * of findings (`children`), the first of them Sentinel's own answer so
 * agreeing is one click; and under the row whatever a button opened
 * (`below`: the field picker, the amended documents area). The user's
 * reading of the old box: "Confirm outcome" confirmed an abstract word, and
 * a first-time reviewer took it for "I confirm this email is wrong" -- so
 * every button here says the finding in plain words instead.
 */
export function ReviewBox({
  status,
  heading,
  line,
  saving,
  neutral,
  record,
  children,
  below,
}: {
  status: CaseStatus;
  heading: string;
  /** One or two short lines under the heading: what Sentinel found, and on
   *  an escalated case why it stopped and what to do about it. */
  line: ReactNode;
  saving?: boolean;
  /** Grey instead of the status colour (NEUTRAL_TONE). */
  neutral?: boolean;
  /** Once a review is saved, its record (ReviewSummary) in place of the
   *  heading and the line, in the record's grey. The box itself stays --
   *  one component in both states -- so whatever is open in its row (a
   *  reply draft being edited, files chosen for a re-check) survives a
   *  confirm or a withdraw; swapping in another component remounted them. */
  record?: ReactNode;
  /** The row of findings. Absent on /compare, which has no review: the box
   *  is then the heading and the line alone. */
  children?: ReactNode;
  below?: ReactNode;
}) {
  const tone = neutral ? NEUTRAL_TONE : TONE[status];
  const Icon = neutral ? Info : status === "OK" ? CheckCircle2 : AlertTriangle;
  return (
    <div
      className={cn("rounded-lg border p-4", record ? "bg-muted/40 text-sm" : tone.container)}
      data-testid={record ? "review-summary" : "review-actions"}
    >
      {record ?? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Icon className={cn("size-4", tone.icon)} strokeWidth={2} />
            <div className={cn("text-sm font-semibold", tone.icon)}>{heading}</div>
            {saving && <span className="text-xs text-muted-foreground">Saving…</span>}
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">{line}</p>
        </>
      )}
      {children && <div className="mt-3 flex flex-wrap items-center gap-2">{children}</div>}
      {below && <div className="mt-3">{below}</div>}
    </div>
  );
}

/**
 * The end of a row of actions: the reply draft, whose trigger is a button
 * and whose open panel is a div -- the `:has(>div)` variant tells them
 * apart, so the open panel drops onto a full line under the buttons.
 * `data-spotlight="reply"` is the home tile's target, on every status.
 */
export function RowEnd({ children }: { children: ReactNode }) {
  return (
    <div data-spotlight="reply" className="ml-auto max-w-full [&:has(>div)]:mt-1 [&:has(>div)]:basis-full">
      {children}
    </div>
  );
}

/** The note, saved when the reviewer clicks away -- there is no Save button
 *  anywhere in the review, and the note is no exception. Uncontrolled on
 *  purpose: the value only leaves the box on blur. Opened from an "Add
 *  note" link rather than always on screen: an empty box under every
 *  finding read as "you have to say why". */
function NoteField({ value, onSave, onDone }: { value: string; onSave: (note: string) => void; onDone: () => void }) {
  return (
    <Textarea
      autoFocus
      defaultValue={value}
      placeholder="Note for the next reviewer — saved when you click away"
      aria-label="Review note"
      rows={1}
      className="mt-2 min-h-8 bg-background/60"
      onBlur={(e) => {
        const next = e.currentTarget.value;
        if (next.trim() !== value.trim()) onSave(next);
        onDone();
      }}
    />
  );
}

/**
 * Once a review is saved: what the reviewer found, beside what Sentinel
 * said -- both kept, because "the system said X, a person said Y, here is
 * what both were looking at" is the whole point of the page; hiding X would
 * turn an audit trail into a silent overwrite. The field cards below show
 * the same thing one field at a time. Rendered as ReviewBox's `record`: the
 * box keeps the row (the findings, the amended documents button, the reply
 * draft) and what a button opened under it.
 */
export function ReviewSummary({ report, control }: { report: CaseReport; control: ReviewController }) {
  const [noteOpen, setNoteOpen] = useState(false);
  const { draft } = control;
  const review = report.review;
  if (!review) return null;
  const saving = control.busy !== null;
  const savedCase = control.flash === "case";
  const after = report.effective ?? { status: review.status, defect_fields: review.defect_fields };
  // One rule for the review state, whichever button made the review:
  // still escalated after it is Unresolved; otherwise Confirmed when the
  // outcome is Sentinel's own (same status, same fields), Overridden when not.
  const sameFields = [...after.defect_fields].sort().join() === [...report.defect_fields].sort().join();
  const state =
    after.status === "NEEDS_REVIEW"
      ? "Unresolved"
      : after.status === report.status && sameFields
        ? "Confirmed"
        : "Overridden";
  const stateTitle = {
    Confirmed: "The outcome is the Sentinel result",
    Overridden: "The outcome differs from the Sentinel result",
    Unresolved: "The case is still escalated",
  }[state];
  const valuesOnly = isValuesOnly(report);
  // Corrected values alone and still escalated: say what is left, so
  // "Unresolved" is not read as nothing having happened.
  const stillOpen = report.fields.filter(
    (f) => (review.field_verdicts?.[f.field]?.stands ?? f.verdict) === "UNCOMPARABLE",
  ).length;
  const hasCorrections = Object.keys(draft.corrections).length > 0;
  const fieldNames = (fields: string[]) => fields.map((f) => FIELD_LABELS[f] ?? f).join(", ");
  const reason = escalationText(report);
  const sentinelSaid = (
    <>
      <StatusBadge status={report.status} />
      {report.status === "MISMATCH" && report.defect_fields.length > 0 && <span>{fieldNames(report.defect_fields)}</span>}
      {report.status === "NEEDS_REVIEW" && reason && (
        <span>— {reason.charAt(0).toLowerCase() + reason.slice(1).replace(/\.$/, "")}</span>
      )}
    </>
  );
  // What the reviewer changed, one line per field -- a corrected value with
  // what the pair now gets, or a call made in the box without touching the
  // values -- so "what did I change?" is read off a list, not worked out
  // from two outcomes.
  const changes: { key: string; body: ReactNode }[] = [];
  for (const [f, sides] of Object.entries(draft.corrections)) {
    const name = FIELD_LABELS[f] ?? f;
    const now = review.field_verdicts?.[f]?.verdict;
    for (const side of ["si", "bl"] as const) {
      if (sides[side] === undefined) continue;
      const original = report.fields.find((x) => x.field === f)?.[side];
      changes.push({
        key: `${f}:${side}`,
        body: (
          <>
            <span className="font-medium">{name}</span> · {side.toUpperCase()}:{" "}
            <span className="text-muted-foreground line-through">{original?.present ? (original.raw ?? "") : "not extracted"}</span> →{" "}
            <span className="font-medium">{sides[side]}</span>
            {now && (
              <>
                {" "}
                → now <VerdictBadge verdict={now} />
              </>
            )}
          </>
        ),
      });
    }
  }
  for (const [f, d] of Object.entries(draft.decisions)) {
    const sentinel = report.fields.find((x) => x.field === f)?.verdict;
    changes.push({
      key: `${f}:call`,
      body: (
        <>
          <span className="font-medium">{FIELD_LABELS[f] ?? f}</span> ·{" "}
          {d === "cleared"
            ? "cleared — same value, different format"
            : d === "flagged"
              ? "flagged as a discrepancy"
              : "checked against both documents — consistent"}
          {sentinel && (
            <span className="text-muted-foreground">
              {" "}
              (Sentinel result: <VerdictBadge verdict={sentinel} />)
            </span>
          )}
        </>
      ),
    });
  }
  const label = "text-xs font-semibold uppercase tracking-wide text-muted-foreground sm:pt-1";
  const cell = "flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1";
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 font-medium">
        Review record
        {saving ? (
          <span className="text-xs font-normal text-muted-foreground">Saving…</span>
        ) : savedCase ? (
          <span className="text-xs font-normal text-ok">Saved</span>
        ) : null}
      </div>
      {/* The same three-line shape every time -- Sentinel result, reviewer
          decision, changes -- in the label column the filter card and
          the field cards use, so a reviewer reads their own review at a
          glance instead of working it out from two sentences. */}
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-[10rem_minmax(0,1fr)]">
        <span className={label}>Sentinel result</span>
        <span className={cell}>{sentinelSaid}</span>
        {/* Values only: no decision was made, so the row names what the
            outcome came from instead of calling it a decision. */}
        {valuesOnly ? (
          <span
            className={label}
            title="The corrected values were compared again with the run's own rules; this result follows from them"
          >
            After corrections
          </span>
        ) : (
          <span className={label}>Reviewer decision</span>
        )}
        <span className={cell}>
          <StatusBadge status={after.status} />
          {after.status === "MISMATCH" && after.defect_fields.length > 0 && <span>{fieldNames(after.defect_fields)}</span>}
          <span title={stateTitle}>· {state}</span>
          {valuesOnly && state === "Unresolved" && stillOpen > 0 && (
            <span className="text-muted-foreground">
              — {stillOpen} field{stillOpen === 1 ? "" : "s"} still not compared
            </span>
          )}
        </span>
        {changes.length > 0 && (
          <>
            <span className={label}>Changes</span>
            <ul className="flex min-w-0 flex-col gap-1">
              {changes.map((c) => (
                <li key={c.key} className={cell}>
                  {c.body}
                </li>
              ))}
            </ul>
          </>
        )}
        {review.reviewer && (
          <>
            <span className={label}>Reviewed by</span>
            <span className={cell}>{review.reviewer}</span>
          </>
        )}
        {draft.note && !noteOpen && (
          <>
            <span className={label}>Note</span>
            <span className="whitespace-pre-line text-muted-foreground">{draft.note}</span>
          </>
        )}
      </div>
      {noteOpen && (
        <NoteField
          key={draft.note}
          value={draft.note}
          onSave={(n) => control.commit({ ...draft, note: n }, "case")}
          onDone={() => setNoteOpen(false)}
        />
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="ghost"
          onClick={control.withdraw}
          title={
            hasCorrections
              ? "Remove the review, corrected values included; the Sentinel result stands and the case returns to Not reviewed"
              : "Remove the reviewer decision; the Sentinel result stands and the case returns to Not reviewed"
          }
        >
          <Undo2 className="size-3.5" />
          Withdraw review
        </Button>
        {!noteOpen && (
          <button
            type="button"
            onClick={() => setNoteOpen(true)}
            className="text-xs text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
          >
            {draft.note ? "Edit note" : "Add note"}
          </button>
        )}
      </div>
    </>
  );
}

/** "SI: ACME LTD · BL: —": both readings of a field on one line, for the
 *  picker, so the reviewer chooses with the values in front of them. */
function pairText(f: FieldComparisonReport): string {
  const side = (v: FieldComparisonReport["si"]) => (v.present ? (v.raw ?? "") : "—");
  return `SI: ${side(f.si)} · BL: ${side(f.bl)}`;
}

/**
 * "Flag fields" on a case Sentinel passed or could not check: which fields
 * differ, as one checkbox per field with both readings beside it. Saving
 * flags the chosen fields (and takes any of Sentinel's own off the list
 * that were not chosen); the backend derives the outcome from those
 * choices as it does for the pills on the cards -- this is the same
 * decision made for several fields at once.
 */
export function FieldPicker({
  fields,
  initial,
  busy,
  onSave,
  onCancel,
}: {
  fields: FieldComparisonReport[];
  initial: string[];
  busy?: boolean;
  onSave: (chosen: string[]) => void;
  onCancel: () => void;
}) {
  const [chosen, setChosen] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(fields.map((f) => [f.field, initial.includes(f.field)])),
  );
  const picked = fields.map((f) => f.field).filter((k) => chosen[k]);
  return (
    <div className="rounded-md border bg-background p-3" data-testid="field-picker">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Discrepant fields</div>
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {fields.map((f) => (
          <label key={f.field} className="flex min-w-0 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(chosen[f.field])}
              onChange={(e) => setChosen({ ...chosen, [f.field]: e.target.checked })}
              className="size-4 shrink-0 accent-primary"
            />
            <span className="shrink-0">{FIELD_LABELS[f.field] ?? f.field}</span>
            <span className="min-w-0 truncate text-xs text-muted-foreground" title={pairText(f)}>
              {pairText(f)}
            </span>
          </label>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={picked.length === 0 || busy} onClick={() => onSave(picked)}>
          {picked.length === 0
            ? "Select at least one field"
            : `Save (${picked.length} discrepant field${picked.length === 1 ? "" : "s"})`}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/** What the model read on an image-only scan for one field, per side --
 *  null where Sentinel already had the value, or where the model found the
 *  field illegible (left blank, never guessed). */
export interface ReadOutRow {
  field: string;
  si: string | null;
  bl: string | null;
}

/**
 * "Use scan transcription": the model's reading of each scan, laid out for
 * the reviewer to adopt field by field. readers/scan.py's rule holds here:
 * a transcript is evidence for a person and never grounds for a decision,
 * so nothing is saved until the reviewer ticks what they have checked
 * against the image and presses the button; what they adopt becomes their
 * own corrections, compared by the run's rules like any other, and stays
 * editable on the cards.
 */
export function ScanAdoptPanel({
  rows,
  model,
  busy,
  onSave,
  onCancel,
}: {
  rows: ReadOutRow[];
  model: string;
  busy?: boolean;
  onSave: (chosen: string[]) => void;
  onCancel: () => void;
}) {
  const [chosen, setChosen] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(rows.map((r) => [r.field, Boolean(r.si || r.bl)])),
  );
  const picked = rows.filter((r) => chosen[r.field] && (r.si || r.bl)).map((r) => r.field);
  const values = rows.filter((r) => picked.includes(r.field)).reduce((n, r) => n + (r.si ? 1 : 0) + (r.bl ? 1 : 0), 0);
  return (
    <div className="rounded-md border border-ai/40 bg-ai-bg/30 p-3" data-testid="scan-adopt">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ai">
        <Sparkles className="size-3.5" strokeWidth={2} />
        Transcribed from the scans by {model}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Not compared yet. Select the values you have verified against the scan; the rules then compare the pair, and every
        value stays editable on its card.
      </p>
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {rows.map((r) => {
          const none = !r.si && !r.bl;
          const text = none ? "illegible on both scans — left blank" : `SI: ${r.si ?? "illegible"} · BL: ${r.bl ?? "illegible"}`;
          return (
            <label key={r.field} className={cn("flex min-w-0 items-start gap-2 text-sm", none && "text-muted-foreground")}>
              <input
                type="checkbox"
                disabled={none || busy}
                checked={Boolean(chosen[r.field]) && !none}
                onChange={(e) => setChosen({ ...chosen, [r.field]: e.target.checked })}
                className="mt-0.5 size-4 shrink-0 accent-primary"
              />
              <span className="min-w-0">
                <span className="font-medium">{FIELD_LABELS[r.field] ?? r.field}</span>
                <span className="block truncate text-xs text-muted-foreground" title={text}>
                  {text}
                </span>
              </span>
            </label>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={picked.length === 0 || busy} onClick={() => onSave(picked)}>
          {picked.length === 0
            ? "Select at least one field"
            : `Accept ${values} value${values === 1 ? "" : "s"} — verified against the scan`}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
