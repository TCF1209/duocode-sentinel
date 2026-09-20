"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ShipCargo } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RunStatusPill, STATUS_COLOR_VAR } from "@/components/status-badges";
import { BackLink } from "@/components/back-link";
import { getMetrics, getRun, type CaseStatus, type Category, type PipelineMetrics, type ReviewReason, type RunStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { fadeUp, stagger, useCountUp } from "@/lib/motion";
import { CATEGORY_LABELS, REVIEW_REASON_LABELS, STATUS_LABELS } from "@/lib/labels";

const CHART_MS = 420;

export function MetricsPageView({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunStatus | null>(null);
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRun(runId)
      .then(setRun)
      .catch(() => {});
    getMetrics(runId)
      .then(setMetrics)
      .catch((e) => setError(e.message));
  }, [runId]);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!metrics) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-4 w-40" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  const categoryData = Object.entries(metrics.by_category).map(([name, value]) => ({ name, value }));
  const statusData = Object.entries(metrics.by_status).map(([name, value]) => ({ name, value }));
  const reasonData = Object.entries(metrics.by_review_reason).map(([name, value]) => ({ name, value }));
  const costUsd = (metrics.llm?.usage as { cost_usd?: number } | undefined)?.cost_usd ?? 0;

  return (
    <motion.div className="flex flex-col gap-4" initial="hidden" animate="show" variants={stagger()}>
      <motion.div variants={fadeUp}>
        <BackLink href={`/runs/${runId}`} label={`Back to ${runId}`} />
      </motion.div>

      <motion.div className="flex items-center gap-3 rounded-xl border bg-card p-4" variants={fadeUp}>
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10">
          <ShipCargo className="size-5 text-primary" strokeWidth={1.75} />
        </span>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-heading text-xl font-semibold">Metrics</h1>
            {run && <RunStatusPill status={run.status} />}
          </div>
          <p className="font-mono text-sm text-muted-foreground">{runId}</p>
        </div>
      </motion.div>

      <motion.div className="grid grid-cols-2 gap-3 sm:grid-cols-4" variants={stagger()}>
        <Stat label="Emails" value={metrics.emails} />
        <Stat label="Mean ms / email" value={metrics.mean_ms_per_email} decimals={2} />
        <Stat label="Resolved by rules" value={metrics.rule_share * 100} format={(v) => `${Math.round(v)}%`} accent="ok" />
        <Stat label="Model calls" value={metrics.llm_calls} accent={metrics.llm_calls > 0 ? "ai" : undefined} />
        <Stat label="Documents read" value={metrics.documents_read} />
        <Stat
          label="Unreadable"
          value={metrics.documents_unreadable}
          accent={metrics.documents_unreadable > 0 ? "warn" : undefined}
        />
        {metrics.llm?.available && <Stat label="Model cost" value={costUsd} format={(v) => `$${v.toFixed(4)}`} />}
      </motion.div>

      <motion.div className="grid gap-4 sm:grid-cols-2" variants={stagger()}>
        <motion.div variants={fadeUp}>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">By category</CardTitle>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    tickFormatter={(key: string) => CATEGORY_LABELS[key as Category] ?? key}
                    tick={{ fontSize: 11 }}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis allowDecimals={false} />
                  <Tooltip labelFormatter={(label) => CATEGORY_LABELS[String(label) as Category] ?? String(label)} />
                  <Bar
                    dataKey="value"
                    name="Emails"
                    fill="var(--primary)"
                    radius={[4, 4, 0, 0]}
                    animationDuration={CHART_MS}
                    animationEasing="ease-out"
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">By outcome</CardTitle>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="value"
                    nameKey="name"
                    outerRadius={90}
                    label={(entry) => STATUS_LABELS[entry.name as CaseStatus] ?? entry.name}
                    animationDuration={CHART_MS}
                    animationEasing="ease-out"
                  >
                    {statusData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={STATUS_COLOR_VAR[entry.name as CaseStatus] ?? "var(--muted-foreground)"}
                      />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [value, STATUS_LABELS[String(name) as CaseStatus] ?? name]} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {reasonData.length > 0 && (
          <motion.div className="sm:col-span-2" variants={fadeUp}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Escalated for review, by reason</CardTitle>
              </CardHeader>
              <CardContent className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={reasonData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={140}
                      tick={{ fontSize: 12 }}
                      tickFormatter={(key: string) => REVIEW_REASON_LABELS[key as ReviewReason] ?? key}
                    />
                    <Tooltip
                      labelFormatter={(label) => REVIEW_REASON_LABELS[String(label) as ReviewReason] ?? String(label)}
                    />
                    <Bar
                      dataKey="value"
                      name="Cases"
                      fill="var(--warn)"
                      radius={[0, 4, 4, 0]}
                      animationDuration={CHART_MS}
                      animationEasing="ease-out"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  );
}

const ACCENT_STYLE = {
  ok: "text-ok",
  warn: "text-warn",
  ai: "text-ai",
} as const;

function Stat({
  label,
  value,
  decimals = 0,
  format,
  accent,
}: {
  label: string;
  value: number;
  decimals?: number;
  format?: (v: number) => string;
  accent?: keyof typeof ACCENT_STYLE;
}) {
  const display = useCountUp(value, decimals);
  return (
    <motion.div variants={fadeUp}>
      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className={cn("font-heading text-xl font-semibold tabular-nums", accent && ACCENT_STYLE[accent])}>
            {format ? format(display) : display}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
