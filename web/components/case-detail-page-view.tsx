"use client";

import { useCallback, useEffect, useState } from "react";
import { RotateCw } from "lucide-react";
import { CaseReportView } from "@/components/case-report-view";
import { BackLink } from "@/components/back-link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getCase, retryCase, reviewCase, type CaseReport } from "@/lib/api";
import { toast } from "sonner";

/** See run-page-view.tsx's file comment: kept out of app/runs/[runId]/... on purpose. */
export function CaseDetailPageView({ runId, emailId }: { runId: string; emailId: string }) {
  const [report, setReport] = useState<CaseReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const refresh = useCallback(() => {
    getCase(runId, emailId)
      .then(setReport)
      .catch((e) => setError(e.message));
  }, [runId, emailId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (error) {
    return <p className="text-sm text-danger">{error}</p>;
  }
  if (!report) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  // Retry is offered where it is the plausible next action and hidden where it
  // is not. Re-reading an email whose documents both parsed and matched would
  // do nothing but spend a second and invite the reviewer to doubt a clean
  // result; re-reading one that arrived corrupt is exactly what they want
  // after the sender re-sends it, because the file is read from disk again.
  const couldChange =
    report.status === "NEEDS_REVIEW" || report.errors.length > 0;

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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <BackLink href={`/runs/${runId}`} label={`Back to ${runId}`} />
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
