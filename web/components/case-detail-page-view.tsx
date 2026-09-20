"use client";

import { useCallback, useEffect, useState } from "react";
import { CaseReportView } from "@/components/case-report-view";
import { BackLink } from "@/components/back-link";
import { Card, CardContent } from "@/components/ui/card";
import { getCase, reviewCase, type CaseReport } from "@/lib/api";
import { toast } from "sonner";

/** See run-page-view.tsx's file comment: kept out of app/runs/[runId]/... on purpose. */
export function CaseDetailPageView({ runId, emailId }: { runId: string; emailId: string }) {
  const [report, setReport] = useState<CaseReport | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="flex flex-col gap-4">
      <BackLink href={`/runs/${runId}`} label={`Back to ${runId}`} />
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
