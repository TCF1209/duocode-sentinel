"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/status-badges";
import { FIELD_LABELS, STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { CaseReport, CaseStatus } from "@/lib/api";

const STATUS_OPTIONS: CaseStatus[] = ["OK", "MISMATCH", "NEEDS_REVIEW"];
// FIELD_LABELS' own key order is the canonical 7, already relied on
// elsewhere (lib/labels.ts's own comment) as the one place these are
// spelled out -- reused here rather than a second hardcoded list.
const ALL_FIELDS = Object.keys(FIELD_LABELS);

/** "Mismatch on Container Count, Port of Discharge" / "Matched" -- one
 *  outcome as a phrase, for the before/after lines in the reviewed state. */
function describeOutcome(status: CaseStatus, defectFields: string[]): string {
  const label = STATUS_LABELS[status];
  if (status !== "MISMATCH" || defectFields.length === 0) return label;
  return `${label} on ${defectFields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}`;
}

// How urgently this panel should read, keyed to the same status the rest of
// the app already colors by — an OK case can still be reviewed, but it
// hasn't earned a warn/danger-tinted card the way an actual problem has.
//
// The heading and description differ for OK on purpose, not just the color:
// "Human review" on a case that already matched on all 7 fields reads as
// "something might be wrong here", which is the opposite of what a Matched
// case means. This panel exists on every case regardless of outcome — it is
// an operator sign-off with an audit trail, not an escalation flag — and
// only the MISMATCH/NEEDS_REVIEW copy is actually about a score not being
// trustworthy enough to skip a person.
const URGENCY: Record<CaseStatus, { container: string; icon: string; heading: string; description: string }> = {
  OK: {
    container: "",
    icon: "",
    heading: "Confirm this outcome",
    description: "All 7 fields matched. Confirming just records who signed off — there's nothing here to fix.",
  },
  MISMATCH: {
    container: "border-danger/40 bg-danger-bg/40",
    icon: "text-danger",
    heading: "Review this mismatch",
    // Spelled out on purpose: "Confirm outcome" read, to more than one
    // person, as confirming the *documents* are fine — it confirms
    // Sentinel's call instead, which on this status means agreeing a real
    // discrepancy is there, not clearing one.
    description:
      "Confirming means you agree Sentinel is right that these documents don't match — not that they do. " +
      "If Sentinel got it wrong, use Correct it instead.",
  },
  NEEDS_REVIEW: {
    container: "border-warn/40 bg-warn-bg/40",
    icon: "text-warn",
    // Third section of the needs-review workspace (case-report-view.tsx),
    // after "why this needs a person" and "what to do": the fallback for
    // a reviewer who has looked at the documents themselves.
    heading: "Decide it yourself",
    description:
      "Looked at the documents and can tell what they say? Correct it to what you found. " +
      "Confirming means you agree it genuinely couldn't be checked automatically.",
  },
};

export function ReviewPanel({
  report,
  onSubmit,
  priorDefectCounts,
}: {
  report: CaseReport;
  onSubmit: (body: { decision: "confirm" | "correct"; status?: CaseStatus; defect_fields?: string[]; note?: string }) => Promise<void>;
  /** Other cases from this case's shipper, already flagged on each field,
   *  counted across the current run -- "this isn't a one-off" context
   *  shown next to the matching checkbox below. Absent on /compare, which
   *  has no run to look across, and on a case with no shipper name read. */
  priorDefectCounts?: Record<string, number>;
}) {
  const [mode, setMode] = useState<"confirm" | "correct" | null>(null);
  const [correctedStatus, setCorrectedStatus] = useState<CaseStatus>(report.status);
  // Seeded from what Sentinel itself flagged, not blank -- correcting a
  // mismatch usually means "most of these are real, one of them isn't",
  // not "start from nothing and re-find every defect by hand". A reviewer
  // unchecks what wasn't actually wrong and checks anything Sentinel missed.
  const [correctedFields, setCorrectedFields] = useState<string[]>(report.defect_fields);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (report.review) {
    // What changed, in one glance, for a correction: Sentinel's own answer
    // on the left, what now stands on the right. The field cards below show
    // the same thing one field at a time; this is the whole case at once,
    // asked for as "keep the unchanged version visible to whoever changed it".
    const after = report.effective ?? {
      status: report.review.status,
      defect_fields: report.review.defect_fields,
    };
    return (
      <div className="rounded-lg border bg-muted/40 p-4 text-sm">
        <div className="flex items-center gap-2 font-medium">
          {report.review.decision === "confirm" ? (
            "Reviewed: confirmed as-is"
          ) : (
            <>
              Reviewed: corrected to <StatusBadge status={report.review.status} />
            </>
          )}
        </div>
        {report.review.decision === "correct" && (
          <div className="mt-2 grid gap-x-3 gap-y-0.5 text-xs sm:grid-cols-[auto_1fr]">
            <span className="text-muted-foreground">Sentinel said</span>
            <span>{describeOutcome(report.status, report.defect_fields)}</span>
            <span className="text-muted-foreground">Now</span>
            <span className="font-medium">{describeOutcome(after.status, after.defect_fields)}</span>
          </div>
        )}
        {report.review.reviewer && <div className="mt-1 text-muted-foreground">by {report.review.reviewer}</div>}
        {report.review.note && <div className="mt-1 text-muted-foreground">&ldquo;{report.review.note}&rdquo;</div>}
      </div>
    );
  }

  function toggleField(field: string) {
    setCorrectedFields((prev) => (prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]));
  }

  async function submit(decision: "confirm" | "correct") {
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        decision,
        status: decision === "correct" ? correctedStatus : undefined,
        // Only meaningful when the corrected status is MISMATCH -- the
        // backend derives has_defect/defect_fields from status for OK and
        // NEEDS_REVIEW regardless of what's sent (store.py's
        // effective_outcome), so sending [] there matches what actually
        // takes effect rather than leaving a stale field list unsent.
        defect_fields: decision === "correct" ? (correctedStatus === "MISMATCH" ? correctedFields : []) : undefined,
        note: note || undefined,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const urgency = URGENCY[report.status];
  return (
    <div className={cn("rounded-lg border p-4", urgency.container)}>
      <div className="mb-3 flex items-center gap-2">
        {report.status !== "OK" && <AlertTriangle className={cn("size-4", urgency.icon)} strokeWidth={2} />}
        <div className={cn("text-sm font-semibold", urgency.icon)}>{urgency.heading}</div>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">{urgency.description}</p>
      {mode === "correct" ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {STATUS_OPTIONS.map((s) => (
              <Button key={s} size="sm" variant={s === correctedStatus ? "default" : "outline"} onClick={() => setCorrectedStatus(s)}>
                {STATUS_LABELS[s]}
              </Button>
            ))}
          </div>
          {/* Only for MISMATCH: "which field" isn't a meaningful question
              for OK (nothing is wrong) or NEEDS_REVIEW (nothing was
              comparable), and the backend ignores defect_fields for both
              regardless of what's checked here. */}
          {correctedStatus === "MISMATCH" && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs text-muted-foreground">Which fields are actually wrong?</span>
              <div className="flex flex-wrap gap-2">
                {ALL_FIELDS.map((f) => {
                  const priorCount = priorDefectCounts?.[f] ?? 0;
                  return (
                    <label
                      key={f}
                      className={cn(
                        "flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                        correctedFields.includes(f)
                          ? "border-danger/40 bg-danger-bg/40"
                          : "text-muted-foreground hover:border-primary/40 hover:text-foreground",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="size-3.5 accent-danger"
                        checked={correctedFields.includes(f)}
                        onChange={() => toggleField(f)}
                      />
                      {FIELD_LABELS[f]}
                      {priorCount > 0 && (
                        <span
                          className="rounded-full bg-warn/20 px-1.5 py-0.5 text-[10px] font-medium text-warn"
                          title={`${priorCount} other case${priorCount === 1 ? "" : "s"} from this shipper already flagged on this field in this run`}
                        >
                          {priorCount} prior
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          )}
          <Textarea placeholder="Why? (optional)" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          <div className="flex gap-2">
            <Button size="sm" disabled={busy} onClick={() => submit("correct")}>
              {busy ? "Saving…" : "Save correction"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" disabled={busy} onClick={() => submit("confirm")}>
            {busy ? "Saving…" : "Confirm outcome"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setMode("correct")}>
            Correct it
          </Button>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
