"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CaseReportView } from "@/components/case-report-view";
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
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (!report) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <Link href={`/runs/${runId}`} className="text-sm text-muted-foreground underline">
        &larr; back to {runId}
      </Link>
      <CaseReportView
        report={report}
        onReview={async (body) => {
          await reviewCase(runId, emailId, body);
          toast.success("Review saved");
          refresh();
        }}
      />
    </div>
  );
}
