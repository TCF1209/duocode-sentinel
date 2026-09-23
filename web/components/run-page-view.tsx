"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { BarChart3, ChevronRight, Filter, ShipCargo } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CategoryBadge, DecidedByBadge, RunStatusPill, StatusBadge } from "@/components/status-badges";
import { BackLink } from "@/components/back-link";
import { RunProgress } from "@/components/run-progress";
import { PatternAlerts } from "@/components/pattern-alerts";
import { cn } from "@/lib/utils";
import { fadeUp, stagger, TAP, TAP_TRANSITION } from "@/lib/motion";
import { FIELD_LABELS, STATUS_LABELS } from "@/lib/labels";
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
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Filters live in the URL (?category=&status=), not just component state,
  // so "Mismatches caught" on the home page can link straight to a
  // pre-filtered table instead of dumping the visitor on the unfiltered
  // list and making them find it themselves.
  const categoryParam = searchParams.get("category");
  const statusParam = searchParams.get("status");
  const [categoryFilter, setCategoryFilter] = useState<Category | null>(
    CATEGORIES.includes(categoryParam as Category) ? (categoryParam as Category) : null,
  );
  const [statusFilter, setStatusFilter] = useState<CaseStatus | null>(
    STATUSES.includes(statusParam as CaseStatus) ? (statusParam as CaseStatus) : null,
  );
  const [run, setRun] = useState<RunStatus | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);

  // Not wrapped in useCallback: the React Compiler in this project memoizes
  // call sites automatically, and a manual dependency array here previously
  // fought its inference (it saw only the setState calls, not the reads of
  // categoryFilter/statusFilter in the ternaries) — "Compilation Skipped"
  // rather than a working memoization.
  function setFilters(next: { category?: Category | null; status?: CaseStatus | null }) {
    const category = next.category !== undefined ? next.category : categoryFilter;
    const status = next.status !== undefined ? next.status : statusFilter;
    if (next.category !== undefined) setCategoryFilter(next.category);
    if (next.status !== undefined) setStatusFilter(next.status);

    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (status) params.set("status", status);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

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

  // Stops polling once the run reaches a terminal state — a done run's
  // cases never change again, so refetching every 2s forever was pure
  // waste: each tick set fresh array/object references even when nothing
  // actually changed, and every case row is a layout-animated motion.tr, so
  // Framer Motion re-measured every row's position on each of those
  // no-op refreshes. That's exactly the kind of per-tick layout thrash
  // that reads as jank if it lands mid-scroll.
  //
  // Depends on the plain `runStatus` string, not `run` itself: the object
  // gets a new reference every poll even while status stays "running", and
  // this effect must not tear down and recreate the interval on every one
  // of those ticks — only when the status value actually changes.
  const runStatus = run?.status;
  useEffect(() => {
    refresh();
    if (runStatus && runStatus !== "running") return;
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [refresh, runStatus]);

  // While a run is going, poll the *status* endpoint far more often than the
  // case list. Measured on the deployed API: 520 emails finish in 14 seconds
  // at about 37 a second, so a 2s tick moves the counter in jumps of ~74 and
  // the progress panel reads as stuttering. `GET /runs/{id}` is a handful of
  // fields, so 500ms of it costs nothing, while the case list — 520 rows by
  // the end, and every row a layout-animated table row — stays on 2s.
  // Errors are swallowed rather than toasted: the slow poll above is already
  // reporting failures, and one outage should not produce four notifications
  // a second.
  useEffect(() => {
    if (runStatus !== "running") return;
    const id = setInterval(() => {
      getRun(runId).then(setRun).catch(() => {});
    }, 500);
    return () => clearInterval(id);
  }, [runId, runStatus]);

  const progress = useMemo(() => {
    if (!run || run.total_emails === 0) return 0;
    return Math.round((run.processed / run.total_emails) * 100);
  }, [run]);

  // <RunProgress> stays mounted for a few seconds after the run actually
  // finishes, instead of unmounting the instant `status` flips to "done" —
  // that instant is exactly when someone narrating a demo wants to point at
  // the final tally, and the old behaviour pulled it out from under them.
  //
  // The transition is detected during render (React's own "adjusting state
  // when a prop changes" pattern — comparing against a snapshot held in
  // state, not a ref), not inside a useEffect: the effect below only arms a
  // setTimeout and calls setState from *its* callback, never synchronously
  // in the effect body, which is what react-hooks/set-state-in-effect
  // actually objects to. Only a genuine running -> done transition counts:
  // a page opened straight onto an already-finished run has nothing to
  // hold, so it never shows the panel at all.
  const [prevStatus, setPrevStatus] = useState(runStatus);
  const [progressVisible, setProgressVisible] = useState(runStatus === "running");
  const [holdGeneration, setHoldGeneration] = useState(0);
  if (runStatus !== prevStatus) {
    setPrevStatus(runStatus);
    if (runStatus === "running") {
      setProgressVisible(true);
    } else if (prevStatus === "running" && runStatus === "done") {
      setProgressVisible(true);
      setHoldGeneration((g) => g + 1);
    } else {
      setProgressVisible(false);
    }
  }
  useEffect(() => {
    if (holdGeneration === 0) return;
    const id = setTimeout(() => setProgressVisible(false), 2500);
    return () => clearTimeout(id);
  }, [holdGeneration]);

  // Emails finish in strict file order and the backend records that order
  // separately from the case data itself (backend/api/store.py's `_order`
  // list), so the last entry in an UNFILTERED case list is genuinely "the
  // most recently completed email" — not a guess from array position. Gated
  // on no filter being active because a filtered list's last row is just the
  // last row that happens to match, not the most recent one overall.
  const lastCompleted = !categoryFilter && !statusFilter && cases.length > 0 ? cases[cases.length - 1].email_id : null;

  return (
    <motion.div className="flex flex-col gap-4" initial="hidden" animate="show" variants={stagger()}>
      {/* Every page deeper than this one (metrics, a single case) already had
          its own "back to {runId}" link — this page, one level up from
          those, had no equivalent way back to the Runs list besides the nav
          bar's "Runs" link, which doesn't read as a back affordance the way
          an explicit "← back to Runs" does. */}
      <motion.div variants={fadeUp}>
        <BackLink href="/runs" label="Back to Runs" />
      </motion.div>

      <motion.div
        className="flex flex-col gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-center sm:justify-between"
        variants={fadeUp}
      >
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10">
            <ShipCargo className="size-5 text-primary" strokeWidth={1.75} />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-mono text-base font-semibold">{runId}</h1>
              {run && <RunStatusPill status={run.status} />}
            </div>
            <p className="text-sm text-muted-foreground">
              {!run
                ? "Loading…"
                : run.status === "failed"
                  ? `Failed after ${run.processed}/${run.total_emails} emails: ${run.error}`
                  : `${run.processed}/${run.total_emails} emails processed`}
              {/* Answers "if it suddenly stops, where was I" directly, not
                  just with a count — naming the actual last email that
                  finished, whether the run is still going or has already
                  failed, so there's a concrete anchor rather than just a
                  number to do the arithmetic on. */}
              {run && run.status !== "done" && lastCompleted && (
                <span className="block text-xs">Last finished: {lastCompleted}</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* The percentage lives in the header while the run is going; the
              ring, rate and live tallies are in <RunProgress> below. Two
              progress bars on one screen is one too many. */}
          {run?.status === "running" && (
            <span className="font-mono text-sm tabular-nums text-muted-foreground">{progress}%</span>
          )}
          {run?.status === "done" && (
            <Link href={`/runs/${runId}/metrics`}>
              <Button variant="outline" size="sm">
                <BarChart3 className="size-4" />
                View metrics
              </Button>
            </Link>
          )}
        </div>
      </motion.div>

      {/* Stays up through a short hold after the run finishes (see
          progressVisible above), then removes itself rather than turning
          into a permanent "100%" panel nobody needs. */}
      <AnimatePresence initial={false}>
        {progressVisible && run && (
          <RunProgress
            key="progress"
            processed={run.processed}
            total={run.total_emails}
            cases={cases}
            filtered={Boolean(categoryFilter || statusFilter)}
            done={run.status === "done"}
          />
        )}
      </AnimatePresence>

      <PatternAlerts runId={runId} cases={cases} />

      <motion.div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border bg-card px-4 py-3" variants={fadeUp}>
        <div className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <Filter className="size-3.5" />
          Filters
        </div>
        <FilterGroup
          label="Category"
          options={CATEGORIES}
          value={categoryFilter}
          onChange={(category) => setFilters({ category })}
        />
        <FilterGroup
          label="Status"
          options={STATUSES}
          value={statusFilter}
          onChange={(status) => setFilters({ status })}
          renderLabel={(s) => STATUS_LABELS[s]}
        />
        <div className="flex items-center gap-3 text-xs text-muted-foreground sm:ml-auto">
          <span>
            {cases.length} case{cases.length === 1 ? "" : "s"}
          </span>
          {(categoryFilter || statusFilter) && (
            <button
              type="button"
              onClick={() => setFilters({ category: null, status: null })}
              className="underline decoration-dotted underline-offset-2 hover:text-foreground"
            >
              Clear filters
            </button>
          )}
        </div>
      </motion.div>

      {/* Two renderings of the same `cases`, CSS-switched at `md` rather than
          picked in JS: a table this wide has no reflow that keeps it a table,
          and the alternative — measuring viewport width in an effect — would
          paint the desktop table first on every phone and swap it a frame
          later. `hidden md:block` / `md:hidden` costs one extra copy of 520
          rows in the DOM, half of them display:none and so never laid out or
          painted; that is cheaper than a visible layout swap on first load. */}
      <motion.div className="hidden rounded-md border bg-card md:block" variants={fadeUp}>
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
            <AnimatePresence mode="popLayout" initial={false}>
              {cases.length === 0 ? (
                <motion.tr key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                    {run?.status === "running" ? "Processing…" : "No cases match this filter."}
                  </TableCell>
                </motion.tr>
              ) : (
                cases.map((c) => (
                  <motion.tr
                    key={c.email_id}
                    layout
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="border-b transition-colors last:border-0 hover:bg-muted/50"
                  >
                    <TableCell className="font-mono text-sm">{c.email_id}</TableCell>
                    <TableCell>
                      <CategoryBadge category={c.category} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {Math.round(c.category_confidence * 100)}%
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={c.status} />
                      {/* A row a person overrode must not read like a row we
                          got right. The badge shows the outcome that stands;
                          this shows who it came from, and what we had said. */}
                      {c.outcome_source === "review" && (
                        <span
                          className="ml-2 whitespace-nowrap text-[11px] text-muted-foreground"
                          title={`Sentinel said ${c.system_status}; corrected by a reviewer`}
                        >
                          corrected
                        </span>
                      )}
                      {c.outcome_source === "system" && c.reviewed && (
                        <span className="ml-2 whitespace-nowrap text-[11px] text-muted-foreground">
                          confirmed
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      {c.defect_fields.length > 0 ? (
                        <span className="text-sm">{c.defect_fields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}</span>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <DecidedByBadge decidedBy={c.decided_by} />
                    </TableCell>
                    <TableCell>
                      <Link href={`/runs/${runId}/cases/${c.email_id}`}>
                        <motion.span whileTap={TAP} transition={TAP_TRANSITION} className="inline-block">
                          <Button size="sm" variant="outline">
                            Open
                          </Button>
                        </motion.span>
                      </Link>
                    </TableCell>
                  </motion.tr>
                ))
              )}
            </AnimatePresence>
          </TableBody>
        </Table>
      </motion.div>

      {/* Below `md`: the table's own column count is the problem, not its
          styling, so this is not a narrower table -- one card per case,
          the two things worth a glance (which email, what it decided) up
          top, the fields it actually flagged front and center underneath.
          That second part is not decoration: it is the evidence-gated
          verdict that is Sentinel's actual claim, put where a thumb
          scrolling past 500 rows will still see it without a tap. */}
      <motion.div className="flex flex-col rounded-md border bg-card md:hidden" variants={fadeUp}>
        <AnimatePresence mode="popLayout" initial={false}>
          {cases.length === 0 ? (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="p-8 text-center text-sm text-muted-foreground">
              {run?.status === "running" ? "Processing…" : "No cases match this filter."}
            </motion.div>
          ) : (
            cases.map((c) => <CaseRowCard key={c.email_id} runId={runId} c={c} />)
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}

function CaseRowCard({ runId, c }: { runId: string; c: CaseSummary }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="border-b last:border-0"
    >
      <Link href={`/runs/${runId}/cases/${c.email_id}`}>
        <motion.div whileTap={TAP} transition={TAP_TRANSITION} className="flex flex-col gap-1.5 p-3 active:bg-muted/50">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm">{c.email_id}</span>
            <div className="flex items-center gap-1.5">
              <StatusBadge status={c.status} />
              <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <CategoryBadge category={c.category} />
            <span>{Math.round(c.category_confidence * 100)}%</span>
            <DecidedByBadge decidedBy={c.decided_by} />
            {c.outcome_source === "review" && (
              <span title={`Sentinel said ${c.system_status}; corrected by a reviewer`}>corrected</span>
            )}
            {c.outcome_source === "system" && c.reviewed && <span>confirmed</span>}
          </div>
          {c.defect_fields.length > 0 && (
            <div className="text-sm text-danger">
              {c.defect_fields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}
            </div>
          )}
        </motion.div>
      </Link>
    </motion.div>
  );
}

function FilterGroup<T extends string>({
  label,
  options,
  value,
  onChange,
  renderLabel = (opt: T) => opt,
}: {
  label: string;
  options: T[];
  value: T | null;
  onChange: (v: T | null) => void;
  // Category options already display as their raw code everywhere else
  // (CategoryBadge shows "BL_COMPARISON" verbatim too), so only the Status
  // filter passes this — its pills would otherwise be the one place still
  // saying "OK" once StatusBadge said "Matched" everywhere else.
  renderLabel?: (opt: T) => string;
}) {
  return (
    <div className="flex w-full min-w-0 items-center gap-1.5 text-sm sm:w-auto">
      <span className="shrink-0 text-muted-foreground">{label}:</span>
      <ScrollFade>
        <motion.button
          whileTap={TAP}
          transition={TAP_TRANSITION}
          onClick={() => onChange(null)}
          className={cn(
            "shrink-0 rounded-full border px-2 py-0.5 text-xs transition-colors",
            value === null
              ? "border-primary bg-primary text-primary-foreground"
              : "text-muted-foreground hover:border-primary/40 hover:text-foreground",
          )}
        >
          all
        </motion.button>
        {options.map((opt) => (
          <motion.button
            key={opt}
            whileTap={TAP}
            transition={TAP_TRANSITION}
            onClick={() => onChange(opt)}
            className={cn(
              "shrink-0 rounded-full border px-2 py-0.5 text-xs transition-colors",
              value === opt
                ? "border-primary bg-primary text-primary-foreground"
                : "text-muted-foreground hover:border-primary/40 hover:text-foreground",
            )}
          >
            {renderLabel(opt)}
          </motion.button>
        ))}
      </ScrollFade>
    </div>
  );
}

/**
 * Lets a pill row overflow sideways instead of wrapping to a second line —
 * on a narrow filter toolbar, wrapping both the Category and Status rows
 * cost a full extra card's worth of vertical space before the case table
 * even started. The right-edge fade only shows when there's actually
 * something to scroll to (checked via scrollWidth vs clientWidth) and hides
 * again once scrolled to the end, so it never claims "more" when there
 * isn't any — a ResizeObserver keeps that honest across viewport changes,
 * not just on mount.
 */
function ScrollFade({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [showMore, setShowMore] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    function update() {
      const atEnd = el!.scrollLeft + el!.clientWidth >= el!.scrollWidth - 1;
      setShowMore(el!.scrollWidth > el!.clientWidth + 1 && !atEnd);
    }
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, []);

  return (
    <div className="relative min-w-0">
      <div ref={ref} className="flex gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {children}
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 flex w-10 items-center justify-end bg-gradient-to-l from-card to-transparent transition-opacity duration-200"
        style={{ opacity: showMore ? 1 : 0 }}
      >
        <ChevronRight className="size-3.5 text-muted-foreground" strokeWidth={2.5} />
      </div>
    </div>
  );
}
