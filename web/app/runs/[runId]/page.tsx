"use client";

import { use } from "react";
import { RunPageView } from "@/components/run-page-view";

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  return <RunPageView runId={runId} />;
}
