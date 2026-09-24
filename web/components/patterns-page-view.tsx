"use client";

/**
 * The inbox read sideways: what is wrong across 520 emails, not in one case.
 *
 * The case view answers "is this bill of lading right". This answers the
 * question the desk supervisor has instead — where should we be looking — and
 * it is the one screen in the product aimed at someone who will never open an
 * individual case.
 *
 * It is also the screen most able to lie, which is why the sender table is
 * built the way it is. A defect rate over eleven emails looks exactly like a
 * defect rate over ninety-seven, and printing "2.2x the average" beside the
 * first is an assertion the data cannot support. So every rate carries its 95%
 * interval, and a sender is only *called* elevated when that interval clears
 * the run's own baseline (`backend/api/patterns.py`). On the dev inbox that
 * means one sender out of nine is named and the other eight are shown with
 * their numbers and an explicit "too few to tell" — which is the same rule the
 * evidence gate applies to a single value, one level up.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { AlertTriangle, BarChart3, Layers, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BackLink } from "@/components/back-link";
import { fadeUp, stagger } from "@/lib/motion";
import { FIELD_LABELS, REVIEW_REASON_TEXT } from "@/lib/labels";
import type { ReviewReason } from "@/lib/api";
import { getPatterns, type RunPatterns } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
const pct0 = (n: number) => `${Math.round(n * 100)}%`;

export function PatternsPageView({ runId }: { runId: string }) {
  const [data, setData] = useState<RunPatterns | null>(null);
  const toasted = useCallback(() => {}, []);

  useEffect(() => {
    let alive = true;
    getPatterns(runId)
      .then((d) => alive && setData(d))
      .catch((e) => toast.error(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [runId, toasted]);

  if (!data) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const { totals } = data;
  const partial = data.cases_counted < data.total_emails;

  return (
    <motion.div className="flex flex-col gap-5" initial="hidden" animate="show" variants={stagger()}>
      <motion.div variants={fadeUp}>
        <BackLink href={`/runs/${runId}`} label={`Back to ${runId}`} />
      </motion.div>

      <motion.div variants={fadeUp} className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight">Patterns</h1>
          <p className="text-sm text-muted-foreground">
            What this inbox gets wrong, across{" "}
            <span className="font-mono">{data.cases_counted}</span> emails — the view for
            deciding where the desk should look, not for checking one document.
            {partial && " This run is still going; the counts grow as it finishes."}
          </p>
        </div>
        <Link href={`/runs/${runId}/metrics`}>
          <Button variant="outline" size="sm">
            <BarChart3 className="size-4" />
            Run metrics
          </Button>
        </Link>
      </motion.div>

      <motion.div className="grid gap-3 sm:grid-cols-4" variants={stagger(0, 0.05)}>
        <Stat label="emails" value={totals.emails} />
        <Stat label="comparison requests" value={totals.comparisons} />
        <Stat label="with a defect" value={totals.with_defect} tone="danger" />
        <Stat label="sent to a human" value={totals.escalated} tone="warn" />
      </motion.div>

      {/* ---------------------------------------------------------------- */}
      <motion.section variants={fadeUp} className="flex flex-col gap-3 rounded-xl border bg-card p-5">
        <header className="flex items-center gap-2">
          <Layers className="size-4 text-primary" strokeWidth={1.75} />
          <h2 className="font-heading font-semibold">Which fields go wrong</h2>
        </header>
        <p className="text-sm text-muted-foreground">
          {data.defect_fields_total} defective fields across {totals.with_defect} emails. This is
          the actionable one: the top three are what a carrier should be asked to check before
          sending a draft.
        </p>
        <div className="flex flex-col gap-1.5">
          {data.fields.map((f) => (
            <div key={f.field} className="flex items-center gap-3">
              <span className="w-40 shrink-0 text-sm">{FIELD_LABELS[f.field] ?? f.field}</span>
              <div className="h-5 min-w-0 flex-1 overflow-hidden rounded bg-muted">
                <motion.div
                  className="h-full rounded bg-chart-1"
                  initial={{ width: 0 }}
                  animate={{ width: `${f.share * 100}%` }}
                  transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                />
              </div>
              <span className="w-24 shrink-0 text-right font-mono text-sm tabular-nums">
                {f.count} · {pct0(f.share)}
              </span>
            </div>
          ))}
        </div>
      </motion.section>

      {/* ---------------------------------------------------------------- */}
      <motion.section variants={fadeUp} className="flex flex-col gap-3 rounded-xl border bg-card p-5">
        <header className="flex items-center gap-2">
          <Users className="size-4 text-primary" strokeWidth={1.75} />
          <h2 className="font-heading font-semibold">Which senders send worse drafts</h2>
        </header>
        <p className="text-sm text-muted-foreground">
          Baseline for this run is{" "}
          <span className="font-mono font-medium text-foreground">
            {pct(data.baseline_defect_rate)}
          </span>{" "}
          of comparison requests carrying a defect. A sender is only called{" "}
          <em>above baseline</em> when the 95% interval for its own rate clears that number —
          otherwise the figures are here and the claim is not made.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs tracking-wide text-muted-foreground uppercase">
                <th className="py-2 pr-3 font-medium">Sender</th>
                <th className="py-2 pr-3 text-right font-medium">Compared</th>
                <th className="py-2 pr-3 text-right font-medium">Defects</th>
                <th className="py-2 pr-3 text-right font-medium">Rate</th>
                <th className="py-2 pr-3 font-medium">95% interval</th>
                <th className="py-2 font-medium">Most often wrong</th>
              </tr>
            </thead>
            <tbody>
              {data.senders
                .filter((s) => s.comparisons > 0)
                .map((s) => (
                  <tr key={s.sender} className="border-b last:border-0">
                    <td className="py-2 pr-3">
                      <span className="flex items-center gap-1.5">
                        {s.above_baseline && (
                          <AlertTriangle className="size-3.5 shrink-0 text-warn" strokeWidth={2} />
                        )}
                        <span className="font-mono text-xs">{s.sender}</span>
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums">{s.comparisons}</td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums">{s.defects}</td>
                    <td
                      className={cn(
                        "py-2 pr-3 text-right font-mono tabular-nums",
                        s.above_baseline && "font-medium text-warn",
                      )}
                    >
                      {s.rate === null ? "—" : pct0(s.rate)}
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">
                      {s.ci_low === null || s.ci_high === null
                        ? "—"
                        : `${pct0(s.ci_low)} – ${pct0(s.ci_high)}`}
                    </td>
                    <td className="py-2 text-xs text-muted-foreground">
                      {s.above_baseline ? (
                        <span className="text-warn">
                          above baseline ·{" "}
                          {s.top_fields.map((f) => FIELD_LABELS[f.field] ?? f.field).join(", ")}
                        </span>
                      ) : s.conclusive ? (
                        "below baseline"
                      ) : (
                        <span className="italic">too few to tell</span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <p className="text-xs text-muted-foreground">
          Intervals are Wilson score, which is the one that behaves at eleven observations; the
          textbook normal approximation would declare a signal here that is not there.
        </p>
      </motion.section>

      {/* ---------------------------------------------------------------- */}
      {data.escalation_reasons.length > 0 && (
        <motion.section
          variants={fadeUp}
          className="flex flex-col gap-3 rounded-xl border bg-card p-5"
        >
          <header className="flex items-center gap-2">
            <AlertTriangle className="size-4 text-warn" strokeWidth={1.75} />
            <h2 className="font-heading font-semibold">Why cases reached a human</h2>
          </header>
          <div className="flex flex-wrap gap-2">
            {data.escalation_reasons.map((r) => (
              <span
                key={r.reason}
                className="rounded-full border border-warn/30 bg-warn-bg/60 px-3 py-1.5 text-sm"
              >
                {REVIEW_REASON_TEXT[r.reason as ReviewReason] ?? r.reason}
                <span className="ml-2 font-mono text-xs">{r.count}</span>
              </span>
            ))}
          </div>
        </motion.section>
      )}
    </motion.div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "danger" | "warn";
}) {
  return (
    <motion.div variants={fadeUp} className="rounded-xl border bg-card p-4">
      <div
        className={cn(
          "font-heading text-3xl font-semibold tabular-nums",
          tone === "danger" && "text-danger",
          tone === "warn" && "text-warn",
          !tone && "text-foreground",
        )}
      >
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </motion.div>
  );
}
