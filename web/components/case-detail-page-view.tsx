"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { RotateCw } from "lucide-react";
import { CaseReportView } from "@/components/case-report-view";
import { BackLink } from "@/components/back-link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getCase, listCases, recheckCase, retryCase, reviewCase, type CaseReport, type CaseSummary } from "@/lib/api";
import { listUrlFor, markReturningToRun } from "@/lib/list-memory";
import { describeOutcome } from "@/components/review-panel";
import type { RecheckFiles } from "@/components/recheck-panel";
import { toast } from "sonner";

// The list URL never changes while this page is open, so there is nothing
// to subscribe to -- useSyncExternalStore is used here only for its
// hydration-safe read of sessionStorage (see backHref below).
const subscribeNever = () => () => {};

/** See run-page-view.tsx's file comment: kept out of app/runs/[runId]/... on purpose. */
export function CaseDetailPageView({ runId, emailId }: { runId: string; emailId: string }) {
  const [report, setReport] = useState<CaseReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  // For "this shipper has already had N mismatches on this field in this
  // run" in the Correct it panel below -- a case detail page otherwise has
  // no reason to know about any case but its own. Fetched alongside the
  // case itself, not gated behind opening the panel, so the hint is ready
  // the moment a reviewer clicks Correct it rather than popping in late.
  // Best-effort: a failure here should not block the case report itself
  // from rendering, so it is swallowed rather than surfaced as a page error.
  const [allCases, setAllCases] = useState<CaseSummary[]>([]);

  const refresh = useCallback(() => {
    getCase(runId, emailId)
      .then(setReport)
      .catch((e) => setError(e.message));
    listCases(runId, {})
      .then((r) => setAllCases(r.cases))
      .catch(() => {});
  }, [runId, emailId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Tells the run's list that its next mount is a return from one of its
  // cases (lib/list-memory.ts): the list restores the reviewer's place only
  // then, never on a fresh visit from Runs.
  useEffect(() => {
    markReturningToRun(runId);
  }, [runId]);

  // The run's list URL, filters included, for "Back to run". Read via
  // useSyncExternalStore rather than in render or in an effect: the value
  // lives in sessionStorage, which the server cannot see, so rendering it
  // straight into the href would make server and client disagree on the
  // first pass, and setting state from an effect body is what this
  // project's lint (react-hooks/set-state-in-effect) rejects. The server
  // snapshot is the bare run URL; the client swaps in the remembered one
  // after hydration, which is exactly what this hook exists to do.
  const backHref = useSyncExternalStore(subscribeNever, () => listUrlFor(runId), () => `/runs/${runId}`);

  const priorDefectCounts = useMemo(() => {
    const self = allCases.find((c) => c.email_id === emailId);
    if (!self?.shipper) return undefined;
    const counts: Record<string, number> = {};
    for (const c of allCases) {
      if (c.email_id === emailId || c.shipper !== self.shipper) continue;
      for (const f of c.defect_fields) counts[f] = (counts[f] ?? 0) + 1;
    }
    return counts;
  }, [allCases, emailId]);

  if (error) {
    return <p className="text-sm text-danger">{error}</p>;
  }
  if (!report) {
    // Shaped like the page it's standing in for (back link, header, review
    // panel, a few field rows) rather than a bare "Loading…" line, which
    // read as "the page is empty" more than "the page is working" -- this
    // was raised directly, not a guess at what needed fixing.
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-36 rounded-full" />
        <Card>
          <CardContent className="flex flex-col gap-4 p-6">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-20 w-full" />
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Retry is offered where it is the plausible next action and hidden where it
  // is not. Re-reading an email whose documents both parsed and matched would
  // do nothing but spend a second and invite the reviewer to doubt a clean
  // result; re-reading one that arrived corrupt is exactly what they want
  // after the sender re-sends it, because the file is read from disk again.
  //
  // For a NEEDS_REVIEW case the button now lives inside the report's own
  // workspace, next to "what to do" (case-report-view.tsx), so the header
  // only keeps it for the other case where re-reading can change the
  // answer: a run-level error on a case that was not escalated. Never once
  // the case has been re-checked on re-sent documents: a retry would read
  // the disk originals back over them, and the backend refuses it (409).
  const couldChange =
    report.status !== "NEEDS_REVIEW" && report.errors.length > 0 && !report.recheck;

  async function onRetry() {
    setRetrying(true);
    try {
      const fresh = await retryCase(runId, emailId);
      setReport(fresh);
      toast.success(
        fresh.status === report?.status
          ? `Re-processed — still ${fresh.status}`
          : `Re-processed — now ${fresh.status}`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setRetrying(false);
    }
  }

  // Errors are not caught here on purpose: the recheck panel shows the
  // backend's own refusal text next to its button, where the reviewer is
  // looking, which a toast that fades would only duplicate.
  async function onRecheck(files: RecheckFiles) {
    setRechecking(true);
    try {
      const was = report?.effective ?? report;
      const fresh = await recheckCase(runId, emailId, files);
      setReport(fresh);
      toast.success(
        was
          ? `Re-checked — was ${describeOutcome(was.status, was.defect_fields)}, now ${describeOutcome(fresh.status, fresh.defect_fields)}`
          : `Re-checked — now ${describeOutcome(fresh.status, fresh.defect_fields)}`,
      );
      // The list's prior-defect counts for this shipper may have moved with
      // this case; best-effort, same as on first load.
      listCases(runId, {})
        .then((r) => setAllCases(r.cases))
        .catch(() => {});
    } finally {
      setRechecking(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <BackLink href={backHref} label={`Back to ${runId}`} />
        {couldChange && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            disabled={retrying}
            title="Read the attachments again and re-decide this one case"
          >
            <RotateCw className={retrying ? "animate-spin" : undefined} />
            {retrying ? "Re-processing…" : "Retry this case"}
          </Button>
        )}
      </div>
      <Card>
        <CardContent className="p-6">
          <CaseReportView
            report={report}
            caseId={`${runId}:${emailId}`}
            priorDefectCounts={priorDefectCounts}
            onRetry={onRetry}
            retrying={retrying}
            onRecheck={onRecheck}
            rechecking={rechecking}
            onReview={async (body) => {
              await reviewCase(runId, emailId, body);
              toast.success("Review saved");
              refresh();
            }}
          />
        </CardContent>
      </Card>
    </div>
  );
}
