"use client";

import { use } from "react";
import { MetricsPageView } from "@/components/metrics-page-view";

export default function MetricsPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  return <MetricsPageView runId={runId} />;
}
