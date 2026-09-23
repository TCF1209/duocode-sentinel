"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fadeUp, stagger } from "@/lib/motion";
import { motion } from "motion/react";
import { FIELD_LABELS } from "@/lib/labels";
import type { CaseSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Below this, one or two stray cases sharing a shipper and a field is not
 *  yet a pattern worth interrupting a triage screen for. */
const MIN_PATTERN_SIZE = 2;
/** Cards, not a scrollable list — a screen with more than this many patterns
 *  needs the batch view backlog item docs/ROADMAP.md already names, not a
 *  longer version of this one. */
const MAX_PATTERNS_SHOWN = 6;

interface Pattern {
  shipper: string;
  field: string;
  emailIds: string[];
}

function groupIntoPatterns(cases: CaseSummary[]): Pattern[] {
  // (shipper, field) -> email ids. A case with two defect fields contributes
  // to two groups, which is correct: "this shipper mismatches on both POD
  // and gross weight" is two separate, separately-actionable patterns, not
  // one that happens to have two field names attached.
  const groups = new Map<string, { shipper: string; field: string; emailIds: string[] }>();
  for (const c of cases) {
    if (!c.shipper || !c.has_defect) continue;
    for (const field of c.defect_fields) {
      const key = `${c.shipper}\u0000${field}`;
      const existing = groups.get(key);
      if (existing) {
        existing.emailIds.push(c.email_id);
      } else {
        groups.set(key, { shipper: c.shipper, field, emailIds: [c.email_id] });
      }
    }
  }
  return Array.from(groups.values())
    .filter((g) => g.emailIds.length >= MIN_PATTERN_SIZE)
    .sort((a, b) => b.emailIds.length - a.emailIds.length)
    .slice(0, MAX_PATTERNS_SHOWN);
}

/** "Twelve emails from this shipper all mismatch on port of discharge" is a
 *  different and more valuable statement than twelve separate reports —
 *  docs/ROADMAP.md's own backlog line for this. Reads the case list already
 *  fetched for the table below; no extra request. */
export function PatternAlerts({ runId, cases }: { runId: string; cases: CaseSummary[] }) {
  const patterns = useMemo(() => groupIntoPatterns(cases), [cases]);
  if (patterns.length === 0) return null;

  return (
    <motion.div variants={fadeUp}>
      <Card className="border-warn/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="size-4 text-warn" />
            Patterns worth a second look
          </CardTitle>
        </CardHeader>
        <CardContent>
          <motion.div className="flex flex-col gap-2" initial="hidden" animate="show" variants={stagger()}>
            {patterns.map((p) => (
              <motion.div key={`${p.shipper}\u0000${p.field}`} variants={fadeUp}>
                <PatternRow runId={runId} pattern={p} />
              </motion.div>
            ))}
          </motion.div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function PatternRow({ runId, pattern }: { runId: string; pattern: Pattern }) {
  const [open, setOpen] = useState(false);
  const fieldLabel = FIELD_LABELS[pattern.field] ?? pattern.field;

  return (
    <div className="rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 p-3 text-left"
        aria-expanded={open}
      >
        <span className="text-sm">
          <span className="font-medium">{pattern.emailIds.length} cases</span> from{" "}
          <span className="font-medium">{pattern.shipper}</span> mismatch on{" "}
          <span className="font-medium text-warn">{fieldLabel}</span>
        </span>
        {open ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {open && (
        <div className="flex flex-wrap gap-2 border-t px-3 py-2">
          {pattern.emailIds.map((id) => (
            <Link
              key={id}
              href={`/runs/${runId}/cases/${id}`}
              className={cn(
                "rounded-md border bg-background px-2 py-1 font-mono text-xs text-muted-foreground",
                "hover:border-primary/40 hover:text-foreground",
              )}
            >
              {id}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
