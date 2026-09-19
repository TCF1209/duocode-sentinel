"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CategoryBadge, DecidedByBadge, StatusBadge } from "@/components/status-badges";
import { cn } from "@/lib/utils";
import { getRun, listCases, type CaseSummary, type CaseStatus, type Category, type RunStatus } from "@/lib/api";
import { toast } from "sonner";

/**
 * Lives outside app/runs/[runId]/ on purpose: Tailwind v4's automatic content
 * detection in this project does not scan Next.js's bracket-named route
 * folders (verified by diffing the compiled CSS — utility classes used only
 * inside a [runId]/ file never made it into the stylesheet, even with an
 * explicit @source pointed at it). Every page under app/ stays a thin
 * params-unwrapping shell; the real markup lives here where it is reliably
 * scanned.
 */
const CATEGORIES: Category[] = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"];
const STATUSES: CaseStatus[] = ["OK", "MISMATCH", "NEEDS_REVIEW"];

export function RunPageView({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunStatus | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<Category | null>(null);
  const [statusFilter, setStatusFilter] = useState<CaseStatus | null>(null);

  const refresh = useCallback(() => {
    getRun(runId)
      .then(setRun)
      .catch((e) => toast.error(e.message));
    listCases(runId, {
      category: categoryFilter ?? undefined,
      status: statusFilter ?? undefined,
    })
      .then((r) => setCases(r.cases))
      .catch((e) => toast.error(e.message));
  }, [runId, categoryFilter, statusFilter]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [refresh]);

  const progress = useMemo(() => {
    if (!run || run.total_emails === 0) return 0;
    return Math.round((run.processed / run.total_emails) * 100);
  }, [run]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-mono text-lg font-semibold">{runId}</h1>
        {run && (
          <p className="text-sm text-muted-foreground">
            {run.status === "running"
              ? `Processing… ${run.processed}/${run.total_emails} (${progress}%)`
              : run.status === "failed"
                ? `Failed: ${run.error}`
                : `Done — ${run.processed}/${run.total_emails} emails`}
            {run.status === "done" && (
              <>
                {" · "}
                <Link href={`/runs/${runId}/metrics`} className="underline">
                  view metrics
                </Link>
              </>
            )}
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-4">
        <FilterGroup label="Category" options={CATEGORIES} value={categoryFilter} onChange={setCategoryFilter} />
        <FilterGroup label="Status" options={STATUSES} value={statusFilter} onChange={setStatusFilter} />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Defects</TableHead>
              <TableHead>Decided by</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                  {run?.status === "running" ? "Processing…" : "No cases match this filter."}
                </TableCell>
              </TableRow>
            ) : (
              cases.map((c) => (
                <TableRow key={c.email_id}>
                  <TableCell className="font-mono text-sm">{c.email_id}</TableCell>
                  <TableCell>
                    <CategoryBadge category={c.category} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {Math.round(c.category_confidence * 100)}%
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={c.status} />
                  </TableCell>
                  <TableCell>
                    {c.defect_fields.length > 0 ? (
                      <span className="text-sm">{c.defect_fields.join(", ")}</span>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <DecidedByBadge decidedBy={c.decided_by} />
                  </TableCell>
                  <TableCell>
                    <Link href={`/runs/${runId}/cases/${c.email_id}`}>
                      <Button size="sm" variant="outline">
                        Open
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function FilterGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: T[];
  value: T | null;
  onChange: (v: T | null) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <span className="mr-1 text-muted-foreground">{label}:</span>
      <button
        onClick={() => onChange(null)}
        className={cn(
          "rounded-full border px-2 py-0.5 text-xs",
          value === null ? "border-foreground bg-foreground text-background" : "text-muted-foreground",
        )}
      >
        all
      </button>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={cn(
            "rounded-full border px-2 py-0.5 text-xs",
            value === opt ? "border-foreground bg-foreground text-background" : "text-muted-foreground",
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
