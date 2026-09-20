"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/status-badges";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { CaseReport, CaseStatus } from "@/lib/api";

const STATUS_OPTIONS: CaseStatus[] = ["OK", "MISMATCH", "NEEDS_REVIEW"];

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
    description: "A score cannot tell whether this outcome reads sensibly to an operator — that is this panel's job.",
  },
  NEEDS_REVIEW: {
    container: "border-warn/40 bg-warn-bg/40",
    icon: "text-warn",
    heading: "Human review needed",
    description: "A score cannot tell whether this outcome reads sensibly to an operator — that is this panel's job.",
  },
};

export function ReviewPanel({
  report,
  onSubmit,
}: {
  report: CaseReport;
  onSubmit: (body: { decision: "confirm" | "correct"; status?: CaseStatus; defect_fields?: string[]; note?: string }) => Promise<void>;
}) {
  const [mode, setMode] = useState<"confirm" | "correct" | null>(null);
  const [correctedStatus, setCorrectedStatus] = useState<CaseStatus>(report.status);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (report.review) {
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
        {report.review.reviewer && <div className="text-muted-foreground">by {report.review.reviewer}</div>}
        {report.review.note && <div className="mt-1 text-muted-foreground">&ldquo;{report.review.note}&rdquo;</div>}
      </div>
    );
  }

  async function submit(decision: "confirm" | "correct") {
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        decision,
        status: decision === "correct" ? correctedStatus : undefined,
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
