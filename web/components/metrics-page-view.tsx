"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getMetrics, type PipelineMetrics } from "@/lib/api";

/** See run-page-view.tsx's file comment: kept out of app/runs/[runId]/... on purpose. */
const STATUS_COLORS: Record<string, string> = {
  OK: "#10b981",
  MISMATCH: "#ef4444",
  NEEDS_REVIEW: "#f59e0b",
};

export function MetricsPageView({ runId }: { runId: string }) {
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMetrics(runId)
      .then(setMetrics)
      .catch((e) => setError(e.message));
  }, [runId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!metrics) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const categoryData = Object.entries(metrics.by_category).map(([name, value]) => ({ name, value }));
  const statusData = Object.entries(metrics.by_status).map(([name, value]) => ({ name, value }));
  const reasonData = Object.entries(metrics.by_review_reason).map(([name, value]) => ({ name, value }));

  return (
    <div className="flex flex-col gap-4">
      <Link href={`/runs/${runId}`} className="text-sm text-muted-foreground underline">
        &larr; back to {runId}
      </Link>
      <h1 className="text-xl font-semibold">Metrics</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Emails" value={metrics.emails} />
        <Stat label="Mean ms / email" value={metrics.mean_ms_per_email} />
        <Stat label="Resolved by rules" value={`${Math.round(metrics.rule_share * 100)}%`} />
        <Stat label="Model calls" value={metrics.llm_calls} />
        <Stat label="Documents read" value={metrics.documents_read} />
        <Stat label="Unreadable" value={metrics.documents_unreadable} />
        {metrics.llm?.available && (
          <Stat label="Model cost" value={`$${(metrics.llm.usage as { cost_usd?: number })?.cost_usd?.toFixed(4) ?? "0.0000"}`} />
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">By category</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">By outcome</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" outerRadius={90} label>
                  {statusData.map((entry) => (
                    <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#94a3b8"} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {reasonData.length > 0 && (
          <Card className="sm:col-span-2">
            <CardHeader>
              <CardTitle className="text-sm font-medium">Escalated for review, by reason</CardTitle>
            </CardHeader>
            <CardContent className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reasonData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}
