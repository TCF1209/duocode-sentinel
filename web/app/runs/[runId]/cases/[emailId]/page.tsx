"use client";

import { use } from "react";
import { CaseDetailPageView } from "@/components/case-detail-page-view";

export default function CaseDetailPage({ params }: { params: Promise<{ runId: string; emailId: string }> }) {
  const { runId, emailId } = use(params);
  return <CaseDetailPageView runId={runId} emailId={emailId} />;
}
