"use client";

import { use } from "react";
import { PatternsPageView } from "@/components/patterns-page-view";

export default function PatternsPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  return <PatternsPageView runId={runId} />;
}
