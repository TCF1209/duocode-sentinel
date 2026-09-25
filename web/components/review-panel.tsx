"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, Sparkles, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge, VerdictBadge } from "@/components/status-badges";
import { FIELD_LABELS, STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { CaseReport, CaseStatus, FieldComparisonReport, FieldCorrection, FieldDecision, ReviewBody } from "@/lib/api";

/** "Mismatch on Container Count, Port of Discharge" / "No mismatch" -- one
 *  outcome as a phrase, for the before/after lines in the reviewed state
 *  (and the same lines in recheck-panel.tsx, which reuses it). */
export function describeOutcome(status: CaseStatus, defectFields: string[]): string {
  const label = STATUS_LABELS[status];
  if (status !== "MISMATCH" || defectFields.length === 0) return label;
  return `${label} on ${defectFields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}`;
}

/**
 * The review as the reviewer builds it, one change at a time: a finding on
 * the whole case (no mismatch / mismatch on these fields / can't tell), a
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
  /** "Can't tell" -- the whole case goes to Needs review regardless. */
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
// the rest of the app colours by -- a clean case can still be reviewed, but
// it has not earned a warn/danger-tinted card the way an actual problem has.
const TONE: Record<CaseStatus, { container: string; icon: string }> = {
  OK: { container: "bg-card", icon: "" },
  MISMATCH: { container: "border-danger/40 bg-danger-bg", icon: "text-danger" },
  NEEDS_REVIEW: { container: "border-warn/40 bg-warn-bg", icon: "text-warn" },
};

/**
 * The box a reviewer decides a case in: what Sentinel found, as a heading
 * and one line the page writes for the status the case stands at; one row
 * of findings (`children`), the first of them Sentinel's own answer so
 * agreeing is one click; and under the row whatever a button opened
 * (`below`: the field picker, the re-sent documents area). The user's
 * reading of the old box: "Confirm outcome" confirmed an abstract word, and
 * a first-time reviewer took it for "I confirm this email is wrong" -- so
 * every button here says the finding in plain words instead.
 */
export function ReviewBox({
  status,
  heading,
  line,
  saving,
  children,
  below,
}: {
  status: CaseStatus;
  heading: string;
  line: string;
  saving?: boolean;
  children: ReactNode;
  below?: ReactNode;
}) {
  const tone = TONE[status];
  return (
    <div className={cn("rounded-lg border p-4", tone.container)} data-testid="review-actions">
      <div className="flex flex-wrap items-center gap-2">
        {status !== "OK" && <AlertTriangle className={cn("size-4", tone.icon)} strokeWidth={2} />}
        <div className={cn("text-sm font-semibold", tone.icon)}>{heading}</div>
        {saving && <span className="text-xs text-muted-foreground">Saving…</span>}
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">{line}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">{children}</div>
      {below && <div className="mt-3">{below}</div>}
    </div>
  );
}

/**
 * The end of a row of actions: the reply draft, whose trigger is a button
 * and whose open panel is a div -- the `:has(>div)` variant tells them
 * apart, so the open panel drops onto a full line under the buttons.
 * `data-spotlight="reply"` is the home tile's target; an escalated case
 * carries it in the workspace instead, and the two are never both rendered.
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
 *  purpose: the value only leaves the box on blur. Opened from an "Add a
 *  note" link rather than always on screen: an empty box under every
 *  finding read as "you have to say why". */
function NoteField({ value, onSave, onDone }: { value: string; onSave: (note: string) => void; onDone: () => void }) {
  return (
    <Textarea
      autoFocus
      defaultValue={value}
      placeholder="A note for whoever reads this next — saved when you click away"
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
 * the same thing one field at a time. `children` end the row (the re-sent
 * documents button, the reply draft); `below` is what a button opened.
 */
export function ReviewSummary({
  report,
  control,
  children,
  below,
}: {
  report: CaseReport;
  control: ReviewController;
  children?: ReactNode;
  below?: ReactNode;
}) {
  const [noteOpen, setNoteOpen] = useState(false);
  const { draft } = control;
  const review = report.review;
  if (!review) return null;
  const saving = control.busy !== null;
  const savedCase = control.flash === "case";
  const after = report.effective ?? { status: review.status, defect_fields: review.defect_fields };
  const agreed = review.decision === "confirm";
  const fieldNames = (fields: string[]) => fields.map((f) => FIELD_LABELS[f] ?? f).join(", ");
  const sentinelSaid = (
    <>
      <StatusBadge status={report.status} />
      {report.status === "MISMATCH" && report.defect_fields.length > 0 && <span>on {fieldNames(report.defect_fields)}</span>}
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
            <span className="text-muted-foreground line-through">{original?.present ? (original.raw ?? "") : "not read"}</span> →{" "}
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
          {d === "cleared" ? "not a mismatch — the two are the same thing" : d === "flagged" ? "flagged as a mismatch" : "fine — you read both documents"}
          {sentinel && (
            <span className="text-muted-foreground">
              {" "}
              (Sentinel: <VerdictBadge verdict={sentinel} />)
            </span>
          )}
        </>
      ),
    });
  }
  const label = "text-xs font-semibold uppercase tracking-wide text-muted-foreground sm:pt-1";
  const cell = "flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1";
  return (
    <div className="rounded-lg border bg-muted/40 p-4 text-sm" data-testid="review-summary">
      <div className="flex flex-wrap items-center gap-2 font-medium">
        Reviewed
        {saving ? (
          <span className="text-xs font-normal text-muted-foreground">Saving…</span>
        ) : savedCase ? (
          <span className="text-xs font-normal text-ok">Saved</span>
        ) : null}
      </div>
      {/* The same three-line shape every time -- what Sentinel said, what
          you said, what changed -- in the label column the filter card and
          the field cards use, so a reviewer reads their own review at a
          glance instead of working it out from two sentences. */}
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-[7rem_minmax(0,1fr)]">
        <span className={label}>Sentinel said</span>
        <span className={cell}>{sentinelSaid}</span>
        <span className={label}>You said</span>
        <span className={cell}>
          {agreed ? (
            <>
              <StatusBadge status={report.status} />
              <span>the same — agreed</span>
            </>
          ) : draft.cantTell ? (
            <>
              <StatusBadge status="NEEDS_REVIEW" />
              <span>couldn&apos;t tell</span>
            </>
          ) : (
            <>
              <StatusBadge status={after.status} />
              {after.status === "MISMATCH" && after.defect_fields.length > 0 && <span>on {fieldNames(after.defect_fields)}</span>}
            </>
          )}
        </span>
        {changes.length > 0 && (
          <>
            <span className={label}>Changed</span>
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
            <span className={label}>By</span>
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
          title="Take this review back altogether: Sentinel's answer stands and nobody has signed it off"
        >
          <Undo2 className="size-3.5" />
          Undo review
        </Button>
        {!noteOpen && (
          <button
            type="button"
            onClick={() => setNoteOpen(true)}
            className="text-xs text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
          >
            {draft.note ? "Edit note" : "Add a note"}
          </button>
        )}
        {children}
      </div>
      {below && <div className="mt-3">{below}</div>}
    </div>
  );
}

/** "SI: ACME LTD · BL: —": both readings of a field on one line, for the
 *  picker, so the reviewer chooses with the values in front of them. */
function pairText(f: FieldComparisonReport): string {
  const side = (v: FieldComparisonReport["si"]) => (v.present ? (v.raw ?? "") : "—");
  return `SI: ${side(f.si)} · BL: ${side(f.bl)}`;
}

/**
 * "Mismatch…" on a case Sentinel passed or could not check: which fields
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
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Which fields differ?</div>
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
            ? "Pick at least one field"
            : `Save — mismatch on ${picked.length} field${picked.length === 1 ? "" : "s"}`}
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
 * "Use the scan read-out": the model's reading of each scan, laid out for
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
        Read from the scans by {model}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Nothing here was compared yet. Tick what you have checked against the image; the rules then compare the pair, and
        every value stays editable on its card.
      </p>
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {rows.map((r) => {
          const none = !r.si && !r.bl;
          const text = none ? "not legible on either scan — left blank" : `SI: ${r.si ?? "not legible"} · BL: ${r.bl ?? "not legible"}`;
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
            ? "Tick at least one field"
            : `Adopt ${values} value${values === 1 ? "" : "s"} — I checked them against the scan`}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
