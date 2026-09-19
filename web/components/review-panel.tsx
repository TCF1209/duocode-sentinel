"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { CaseReport, CaseStatus } from "@/lib/api";

const STATUS_OPTIONS: CaseStatus[] = ["OK", "MISMATCH", "NEEDS_REVIEW"];

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
        <div className="font-medium">
          Reviewed: {report.review.decision === "confirm" ? "confirmed as-is" : `corrected to ${report.review.status}`}
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

  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 text-sm font-medium">Human review</div>
      <p className="mb-3 text-xs text-muted-foreground">
        A score cannot tell whether this outcome reads sensibly to an operator — that is this panel&apos;s job.
      </p>
      {mode === "correct" ? (
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            {STATUS_OPTIONS.map((s) => (
              <Button key={s} size="sm" variant={s === correctedStatus ? "default" : "outline"} onClick={() => setCorrectedStatus(s)}>
                {s}
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
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
