"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type Ref } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { BarChart3, ChevronRight, Layers, ShipCargo, Timer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { CategoryBadge, DecidedByBadge, RunStatusPill, StatusBadge } from "@/components/status-badges";
import { BackLink } from "@/components/back-link";
import { RunProgress } from "@/components/run-progress";
import { PatternAlerts } from "@/components/pattern-alerts";
import { cn } from "@/lib/utils";
import { fadeUp, stagger, TAP, TAP_TRANSITION } from "@/lib/motion";
import { CATEGORY_LABELS, FIELD_LABELS, STATUS_LABELS } from "@/lib/labels";
import { getRun, listCases, type CaseSummary, type CaseStatus, type Category, type RunStatus } from "@/lib/api";
import { useListMemory } from "@/lib/list-memory";
import { pickShowcases, showcaseHref } from "@/lib/showcases";
import { useViewMode } from "@/lib/view-mode";
import { ViewModeSwitch } from "@/components/view-mode-switch";
import {
  formatHours,
  formatSeconds,
  manualWorkload,
  MINUTES_TO_CHECK_ONE_PAIR,
  SECONDS_TO_READ_ONE_EMAIL,
} from "@/lib/manual-estimate";
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

// The third filter axis, asked for directly: "confirmed together, corrected
// together, and the ones nobody has looked at together". Not a backend
// field -- derived from the two the case list already carries (reviewed,
// outcome_source), exactly as the table's own "confirmed"/"corrected" tags
// are, so the filter can never disagree with the tag on the row.
type ReviewFilter = "pending" | "confirmed" | "corrected";
const REVIEW_FILTERS: ReviewFilter[] = ["pending", "confirmed", "corrected"];
const REVIEW_FILTER_LABELS: Record<ReviewFilter, string> = {
  pending: "Not reviewed",
  confirmed: "Confirmed",
  corrected: "Corrected",
};
type ListOrder = "attention" | "inbox";
const LIST_ORDERS: ListOrder[] = ["attention", "inbox"];
const ORDER_LABELS: Record<ListOrder, string> = {
  attention: "Needs attention first",
  inbox: "Inbox order",
};
const ATTENTION_RANK: Record<CaseStatus, number> = { MISMATCH: 0, NEEDS_REVIEW: 1, OK: 2 };
// The same three colours the outcome badges and the metrics charts use.
const STATUS_DOT: Record<CaseStatus, string> = { OK: "bg-ok", MISMATCH: "bg-danger", NEEDS_REVIEW: "bg-warn" };
// Table headers in the same small-caps style as every other section label
// on the site (the Before table, the case page's field cards), instead of
// the component's default body-size, body-colour header.
const TH = "text-xs font-semibold uppercase tracking-wide text-muted-foreground";
function reviewStateOf(c: CaseSummary): ReviewFilter {
  if (c.outcome_source === "review") return "corrected";
  return c.reviewed ? "confirmed" : "pending";
}

/** The "classify five yourself" exercise (Before Sentinel): the visitor's
 *  own calls and the wall-clock times of their first and last pick. Kept in
 *  sessionStorage per run, so opening a case and coming back, or flipping
 *  the switch, does not lose it mid-demo; a new tab starts fresh. */
interface ClassifyFive {
  guesses: Record<string, Category>;
  startedAt: number | null;
  endedAt: number | null;
}
const EMPTY_EXERCISE: ClassifyFive = { guesses: {}, startedAt: null, endedAt: null };
const exerciseKey = (runId: string) => `sentinel:classify-five:${runId}`;
function readExercise(runId: string): ClassifyFive {
  if (typeof window === "undefined") return EMPTY_EXERCISE;
  try {
    const raw = window.sessionStorage.getItem(exerciseKey(runId));
    if (!raw) return EMPTY_EXERCISE;
    const parsed = JSON.parse(raw) as Partial<ClassifyFive>;
    return {
      guesses: parsed.guesses && typeof parsed.guesses === "object" ? parsed.guesses : {},
      startedAt: typeof parsed.startedAt === "number" ? parsed.startedAt : null,
      endedAt: typeof parsed.endedAt === "number" ? parsed.endedAt : null,
    };
  } catch {
    return EMPTY_EXERCISE;
  }
}
function writeExercise(runId: string, value: ClassifyFive) {
  try {
    window.sessionStorage.setItem(exerciseKey(runId), JSON.stringify(value));
  } catch {
    // Storage blocked: the exercise still works for this page.
  }
}

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
  const reviewParam = searchParams.get("review");
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter | null>(
    REVIEW_FILTERS.includes(reviewParam as ReviewFilter) ? (reviewParam as ReviewFilter) : null,
  );
  // Row order, in the URL like the filters so "Back to run" (lib/list-memory)
  // brings it back too. "Needs attention first" is the default: the mentor
  // session's ask was that a mismatch be visible from the list without
  // opening anything, and the surest way is for it to be at the top.
  const orderParam = searchParams.get("order");
  const [order, setOrder] = useState<ListOrder>(orderParam === "inbox" ? "inbox" : "attention");
  const [run, setRun] = useState<RunStatus | null>(null);
  // Always the whole run, never filtered server-side any more -- see
  // visibleCases below for why, and refresh() for how it stays that way.
  const [allCases, setAllCases] = useState<CaseSummary[]>([]);
  // Separate from `allCases.length > 0`: a run that genuinely has zero cases
  // yet (just started) is a real, different state from "hasn't answered
  // the first fetch yet", and the table/stat-strip below need to tell those
  // two apart instead of both reading as "nothing here" -- raised directly
  // as "clicking into a run looks empty for a few seconds".
  const [casesLoaded, setCasesLoaded] = useState(false);

  // "Before Sentinel" shows the same inbox as it arrived -- subject lines,
  // attachments, and what a person would have to do -- with none of
  // Sentinel's columns, filters or patterns (lib/view-mode.ts). Same page
  // skeleton either way; only the contents cross-fade.
  const [mode, setMode] = useViewMode();
  const before = mode === "before";
  // The home page's "Patterns across the inbox" tile arrives with
  // ?open=patterns: the box starts open and scrolls into view
  // (pattern-alerts.tsx), in With mode whatever the switch was left on.
  // Consumed once the box has read it (`onOpened`): the list memory
  // (lib/list-memory.ts) remembers this page's URL, and a remembered ?open
  // would re-open and re-scroll on every return from a case.
  const openPatterns = searchParams.get("open") === "patterns";
  useEffect(() => {
    if (openPatterns && mode !== "with") setMode("with");
  }, [openPatterns, mode, setMode]);
  const consumeOpen = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("open");
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);
  // "Classify five yourself": the visitor's own calls on the first five
  // emails, timed from their first pick to their fifth, then compared with
  // Sentinel's once they flip back -- and projected over the whole inbox at
  // their own pace. Remembered per run for the visit (ClassifyFive above).
  // Read lazily: nothing that shows it renders before the cases have
  // loaded, so the server's empty first paint and the client's remembered
  // one never disagree.
  const [exercise, setExercise] = useState<ClassifyFive>(() => readExercise(runId));
  useEffect(() => {
    writeExercise(runId, exercise);
  }, [runId, exercise]);
  const guesses = exercise.guesses;
  // Elapsed ms while the visitor is mid-way, advanced by the interval below
  // -- the clock is read in the interval, never in render (react-hooks/purity).
  const [elapsedMs, setElapsedMs] = useState(0);
  const firstFive = useMemo(() => allCases.slice(0, 5), [allCases]);
  const answeredCount = firstFive.filter((c) => guesses[c.email_id]).length;
  const guessStarted = exercise.startedAt !== null;
  const guessDone = exercise.endedAt !== null;
  useEffect(() => {
    if (exercise.startedAt === null || exercise.endedAt !== null) return;
    const start = exercise.startedAt;
    const tick = () => setElapsedMs(Date.now() - start);
    // The first tick straight away (a page change mid-exercise lands here
    // with the clock already running), then once a second.
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [exercise.startedAt, exercise.endedAt]);
  // `at` is the change event's own timestamp, on the performance clock; its
  // origin turns it into wall-clock time that survives a page change. No
  // clock is read here -- this function is render-scope to the lint.
  function guess(emailId: string, category: Category, at: number) {
    const now = performance.timeOrigin + at;
    setExercise((prev) => {
      const next = { ...prev.guesses, [emailId]: category };
      const answered = firstFive.filter((c) => next[c.email_id]).length;
      return {
        guesses: next,
        startedAt: prev.startedAt ?? now,
        endedAt: answered >= firstFive.length ? (prev.endedAt ?? now) : null,
      };
    });
  }
  function startOver() {
    setExercise(EMPTY_EXERCISE);
    setElapsedMs(0);
  }
  const guessSeconds =
    exercise.startedAt === null
      ? 0
      : ((exercise.endedAt ?? exercise.startedAt + elapsedMs) - exercise.startedAt) / 1000;
  const agreed = firstFive.filter((c) => guesses[c.email_id] === c.category).length;
  const workload = useMemo(() => manualWorkload(allCases), [allCases]);
  const sentinelSeconds = run?.metrics ? run.metrics.total_ms / 1000 : null;
  // The visitor's measured pace, projected: their own seconds per email
  // over every email in the inbox -- classification only -- plus the pair
  // checks at the team's estimated rate (lib/manual-estimate.ts), which no
  // five-email exercise can measure. The two are kept apart on screen.
  const perEmailSeconds = guessDone && firstFive.length > 0 ? guessSeconds / firstFive.length : 0;
  const classifyAllSeconds = perEmailSeconds * allCases.length;
  const pairCheckHours = (workload.comparisons * MINUTES_TO_CHECK_ONE_PAIR) / 60;

  // The one place a filter actually narrows what's shown. Everything that
  // used to read the old server-filtered `cases` for a *count of the whole
  // run* (the pattern alerts, the stat strip, "how many cases total") reads
  // allCases instead now: computing those from a filtered fetch meant they
  // silently meant "of the filtered subset" the moment a filter was active,
  // which nothing on screen said out loud.
  const visibleCases = useMemo(() => {
    const filtered = allCases.filter(
      (c) =>
        (!categoryFilter || c.category === categoryFilter) &&
        (!statusFilter || c.status === statusFilter) &&
        (!reviewFilter || reviewStateOf(c) === reviewFilter),
    );
    if (order === "inbox") return filtered;
    // Mismatches first, the ones with more fields wrong ahead of the rest,
    // then the cases a person has to decide, then the clean ones. Sort is
    // stable, so within a rank the inbox order still holds.
    return [...filtered].sort(
      (a, b) => ATTENTION_RANK[a.status] - ATTENTION_RANK[b.status] || b.defect_fields.length - a.defect_fields.length,
    );
  }, [allCases, categoryFilter, statusFilter, reviewFilter, order]);

  // Keys the two row lists below, so a filter change swaps the whole list at
  // once instead of exit-animating every row that just left it. Measured
  // before this existed: with `layout` on 520 motion.tr rows, dropping 10
  // rows took ~8s and dropping 517 (the Confirmed filter) was still going
  // after 5s, each exiting row forcing a reflow of the whole table. Within
  // one filter the key is stable, so rows appended by a live run still
  // animate in one by one exactly as before.
  const filterKey = `${categoryFilter ?? ""}|${statusFilter ?? ""}|${reviewFilter ?? ""}|${order}`;

  // Feeds the stat strip below. Counted from allCases (effective status,
  // always the whole run) rather than trusted from run.metrics.by_status --
  // see the stat strip's own comment for why that field cannot be used here.
  const statusCounts = useMemo(() => {
    const counts: Record<CaseStatus, number> = { OK: 0, MISMATCH: 0, NEEDS_REVIEW: 0 };
    for (const c of allCases) counts[c.status]++;
    return counts;
  }, [allCases]);
  // How the inbox was sorted (step 1, Classify) -- shown on the category
  // chips, which are the one place this page said it once a run had ended.
  const categoryCounts = useMemo(() => {
    const counts: Record<Category, number> = { BL_COMPARISON: 0, SI_REQUEST: 0, INVOICE_QUERY: 0, GENERAL: 0, SPAM: 0 };
    for (const c of allCases) counts[c.category]++;
    return counts;
  }, [allCases]);

  // How much of the run a person has actually looked at -- the review
  // queue's own progress, which nothing on this page said before.
  const reviewCounts = useMemo(() => {
    const counts: Record<ReviewFilter, number> = { pending: 0, confirmed: 0, corrected: 0 };
    for (const c of allCases) counts[reviewStateOf(c)]++;
    return counts;
  }, [allCases]);

  // Not wrapped in useCallback: the React Compiler in this project memoizes
  // call sites automatically, and a manual dependency array here previously
  // fought its inference (it saw only the setState calls, not the reads of
  // categoryFilter/statusFilter in the ternaries) — "Compilation Skipped"
  // rather than a working memoization.
  function setFilters(next: {
    category?: Category | null;
    status?: CaseStatus | null;
    review?: ReviewFilter | null;
    order?: ListOrder;
  }) {
    const category = next.category !== undefined ? next.category : categoryFilter;
    const status = next.status !== undefined ? next.status : statusFilter;
    const review = next.review !== undefined ? next.review : reviewFilter;
    const nextOrder = next.order !== undefined ? next.order : order;
    if (next.category !== undefined) setCategoryFilter(next.category);
    if (next.status !== undefined) setStatusFilter(next.status);
    if (next.review !== undefined) setReviewFilter(next.review);
    if (next.order !== undefined) setOrder(next.order);

    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (status) params.set("status", status);
    if (review) params.set("review", review);
    // The default order is left out of the URL, so a plain /runs/{id} link
    // and the default view stay the same address.
    if (nextOrder !== "attention") params.set("order", nextOrder);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  // Always fetches the whole run, no category/status params -- visibleCases
  // above does the narrowing client-side instead. Each setState compares
  // against what's already there and hands back the *same* reference when
  // a poll tick fetched back exactly what was already there, so React bails
  // out of re-rendering (and every layout-animated row re-measuring) on a
  // no-op tick. That comparison is what makes the interval below safe to
  // run indefinitely instead of stopping once the run is done -- a
  // reviewer can correct a case well after the run finishes, and this page
  // needs to notice on its own, not just on a manual reload.
  const refresh = useCallback(() => {
    getRun(runId)
      .then((r) => setRun((prev) => (prev && JSON.stringify(prev) === JSON.stringify(r) ? prev : r)))
      .catch((e) => toast.error(e.message));
    listCases(runId, {})
      .then((r) => {
        setAllCases((prev) => (JSON.stringify(prev) === JSON.stringify(r.cases) ? prev : r.cases));
        setCasesLoaded(true);
      })
      .catch((e) => toast.error(e.message));
  }, [runId]);

  // Slows down once the run itself is no longer running, but never stops
  // any more -- see refresh()'s own comment for why a done run still needs
  // to be polled, just rarely. 20s is deliberately not 2s: a review is a
  // human action on a timescale of "the reviewer moved to the next tab and
  // came back", not "the pipeline just finished another email".
  //
  // Depends on the plain `runStatus` string, not `run` itself: the object
  // can get a new reference every poll even while status stays "running"
  // (the no-op guard above only skips a poll that changed *nothing*), and
  // this effect must not tear down and recreate the interval on every one
  // of those ticks — only when the status value actually changes.
  const runStatus = run?.status;
  useEffect(() => {
    refresh();
    const intervalMs = runStatus === "running" ? 2000 : 20000;
    const id = setInterval(refresh, intervalMs);
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
  // list), so the last entry in allCases is genuinely "the most recently
  // completed email" — not a guess from array position. No filter guard
  // needed any more: allCases is never the server-filtered list a stale
  // comment here used to warn about, so its last entry is always the
  // run's, regardless of what visibleCases is currently narrowed to.
  const lastCompleted = allCases.length > 0 ? allCases[allCases.length - 1].email_id : null;

  // `ready` once the list has its real height -- restoring before then would
  // scroll a page that is still its skeleton height, which does nothing.
  // See lib/list-memory.ts for what this remembers and when it restores.
  useListMemory({ runId, ready: casesLoaded });

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
                  : before
                    ? `${run.total_emails} emails in the inbox`
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

        {/* Wraps: with the Before/With switch beside Patterns and View
            metrics this row is wider than a phone, and clipped there. */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {/* The percentage lives in the header while the run is going; the
              ring, rate and live tallies are in <RunProgress> below. Two
              progress bars on one screen is one too many. */}
          {run?.status === "running" && (
            <span className="font-mono text-sm tabular-nums text-muted-foreground">{progress}%</span>
          )}
          {run?.status === "done" && (
            <>
              <ViewModeSwitch />
              {/* Patterns before metrics: metrics is how the run went, patterns
                  is what the inbox is like, and the second is the one a desk
                  supervisor opens. */}
              <Link href={`/runs/${runId}/patterns`}>
                <Button variant="outline" size="sm">
                  <Layers className="size-4" />
                  Patterns
                </Button>
              </Link>
              <Link href={`/runs/${runId}/metrics`}>
                <Button variant="outline" size="sm">
                  <BarChart3 className="size-4" />
                  View metrics
                </Button>
              </Link>
            </>
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
            cases={visibleCases}
            filtered={Boolean(categoryFilter || statusFilter)}
            done={run.status === "done"}
            llmEnabled={run.llm_enabled}
          />
        )}
      </AnimatePresence>

      {/* The shape of the whole run, as the controls that narrow the list
          -- one card where a stat strip and a separate filter bar used to
          say the same things twice, one with numbers and one with buttons.
          Row one is the inbox sorted into its five kinds (step 1, Classify:
          the one result this page never showed once a run had ended, and
          the reason the mentor could not find the classification; the chips
          also said BL_COMPARISON). Row two is the three outcomes. Row three
          is the reviewer's own two controls, as selects rather than eight
          more chips.

          Every count is the whole run's, computed from allCases, not read
          off run.metrics.by_status: that field is a snapshot written once
          when the run finishes (backend/api/store.py's finish_run) and
          never recomputed, so it does not move when a reviewer corrects a
          case afterwards -- confirmed live by correcting a real case and
          watching metrics.by_status stay exactly what it was. allCases
          carries each case's *effective* status already (the list endpoint
          reads store.effective_outcome, same as the table below).
          rule_share/llm_calls stay sourced from run.metrics on purpose --
          which tier decided a case is a system fact a review never
          changes. */}
      {!casesLoaded && (
        <motion.div className="rounded-xl border bg-card px-4 py-3" variants={fadeUp}>
          <Skeleton className="h-5 w-72" />
        </motion.div>
      )}
      {/* Before Sentinel: the same strip, holding what a person would have
          to do with this inbox instead of what Sentinel found. The rates are
          the team's own estimates (lib/manual-estimate.ts) and say so. */}
      {before && casesLoaded && allCases.length > 0 && (
        <motion.div className="flex flex-col gap-1.5 rounded-xl border bg-card px-4 py-3 text-sm" variants={fadeUp}>
          <div className="text-xs font-medium text-muted-foreground">What a person would do with this inbox</div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <span>
              <span className="font-medium tabular-nums">{workload.emails.toLocaleString()}</span> emails to read
            </span>
            <span>
              <span className="font-medium tabular-nums">{workload.comparisons.toLocaleString()}</span> comparison requests to
              find among them
            </span>
            <span>
              <span className="font-medium tabular-nums">{workload.fields.toLocaleString()}</span> fields to check by eye
            </span>
            <span>
              ≈ <span className="font-medium tabular-nums">{formatHours(workload.hours)}</span> of work
            </span>
            {sentinelSeconds !== null && (
              <span className="text-muted-foreground sm:ml-auto">
                Sentinel: <span className="font-medium tabular-nums text-foreground">{sentinelSeconds.toFixed(1)} s</span>
              </span>
            )}
          </div>
          <div className="text-xs text-muted-foreground">
            Estimate: {SECONDS_TO_READ_ONE_EMAIL} s per email, {MINUTES_TO_CHECK_ONE_PAIR} min per pair.
          </div>
        </motion.div>
      )}
      {!before && casesLoaded && allCases.length > 0 && (
        <motion.div className="flex flex-col gap-2.5 rounded-xl border bg-card px-4 py-3" variants={fadeUp} data-testid="run-filters">
          <FilterGroup
            label="Sorted into"
            options={CATEGORIES}
            value={categoryFilter}
            onChange={(category) => setFilters({ category })}
            renderLabel={(c) => CATEGORY_LABELS[c]}
            counts={categoryCounts}
            total={allCases.length}
          />
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <FilterGroup
              label="Outcome"
              options={STATUSES}
              value={statusFilter}
              onChange={(status) => setFilters({ status })}
              renderLabel={(s) => STATUS_LABELS[s]}
              counts={statusCounts}
              total={allCases.length}
              dot={(s) => STATUS_DOT[s]}
            />
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground sm:ml-auto">
              {/* The review queue's progress, beside the outcomes it applies
                  to. The hover breaks it down the same three ways the Review
                  select below does, so the number and the control can never
                  mean different things. */}
              <span title={`${reviewCounts.confirmed} confirmed · ${reviewCounts.corrected} corrected · ${reviewCounts.pending} not reviewed yet`}>
                Reviewed{" "}
                <span className="font-medium tabular-nums text-foreground">{reviewCounts.confirmed + reviewCounts.corrected}</span>{" "}
                / {allCases.length}
              </span>
              {run?.metrics && (
                <span>
                  {Math.round(run.metrics.rule_share * 100)}% by rules · {run.metrics.llm_calls} model call
                  {run.metrics.llm_calls === 1 ? "" : "s"}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <label className="flex items-center gap-1.5 text-muted-foreground">
              <span className="w-24 shrink-0">Review</span>
              <select
                value={reviewFilter ?? ""}
                onChange={(e) => setFilters({ review: (e.target.value || null) as ReviewFilter | null })}
                aria-label="Review state"
                className="rounded-md border bg-background px-2 py-1 text-sm text-foreground"
              >
                <option value="">All</option>
                {REVIEW_FILTERS.map((r) => (
                  <option key={r} value={r}>
                    {REVIEW_FILTER_LABELS[r]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-1.5 text-muted-foreground">
              Order
              <select
                value={order}
                onChange={(e) => setFilters({ order: e.target.value as ListOrder })}
                aria-label="Row order"
                className="rounded-md border bg-background px-2 py-1 text-sm text-foreground"
              >
                {LIST_ORDERS.map((o) => (
                  <option key={o} value={o}>
                    {ORDER_LABELS[o]}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-3 text-xs text-muted-foreground sm:ml-auto">
              <span>
                {visibleCases.length === allCases.length
                  ? `${allCases.length} cases`
                  : `Showing ${visibleCases.length} of ${allCases.length}`}
              </span>
              {(categoryFilter || statusFilter || reviewFilter) && (
                <button
                  type="button"
                  onClick={() => setFilters({ category: null, status: null, review: null })}
                  className="underline decoration-dotted underline-offset-2 hover:text-foreground"
                >
                  Clear filters
                </button>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* "Classify five yourself" -- the manual effort, felt rather than
          quoted: the visitor's own five calls, timed, against Sentinel's
          520 in under two seconds. Before mode shows the invitation and the
          clock; With mode shows the score once they have flipped back. */}
      {before && casesLoaded && firstFive.length > 0 && (
        <motion.div
          className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm"
          variants={fadeUp}
        >
          <Timer className="size-4 shrink-0 text-primary" strokeWidth={2} />
          {!guessStarted ? (
            <span>
              Try it: classify the first {firstFive.length} emails (the <span className="font-medium">Your call</span>{" "}
              column). The clock starts at your first pick.
            </span>
          ) : !guessDone ? (
            <>
              <span>
                {answeredCount} of {firstFive.length} ·{" "}
                <span className="font-mono tabular-nums">{Math.round(guessSeconds)} s</span>
              </span>
              <Button size="sm" variant="ghost" onClick={startOver} title="Clear your calls and the clock">
                Start over
              </Button>
            </>
          ) : (
            <>
              <span>
                You classified {firstFive.length} in{" "}
                <span className="font-medium tabular-nums">{Math.round(guessSeconds)} s</span>.
                {sentinelSeconds !== null && (
                  <>
                    {" "}
                    Sentinel classified {allCases.length} in{" "}
                    <span className="font-medium tabular-nums">{sentinelSeconds.toFixed(1)} s</span>.
                  </>
                )}
              </span>
              <Button size="sm" onClick={() => setMode("with")}>
                See what Sentinel said
              </Button>
              <Button size="sm" variant="ghost" onClick={startOver} title="Clear your calls and the clock">
                Start over
              </Button>
            </>
          )}
        </motion.div>
      )}
      {/* With Sentinel, once they have done the five: their own pace, what
          the inbox costs at that pace, and Sentinel's time beside it. The
          measured part (classification) and the estimated part (pair
          checks) are said separately, and the estimate is called one. */}
      {!before && casesLoaded && guessDone && firstFive.length > 0 && (
        <motion.div
          className="flex flex-col gap-1.5 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm"
          variants={fadeUp}
          data-testid="pace-banner"
        >
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Timer className="size-4 shrink-0 text-primary" strokeWidth={2} />
            <span>
              Your pace: <span className="font-medium tabular-nums">{perEmailSeconds.toFixed(1)} s per email</span>{" "}
              <span className="text-muted-foreground">
                ({firstFive.length} in {Math.round(guessSeconds)} s)
              </span>
              .
            </span>
          </div>
          <div className="pl-6">
            All {allCases.length.toLocaleString()} at that pace:{" "}
            <span className="font-medium tabular-nums">≈ {formatSeconds(classifyAllSeconds)}</span>. Plus{" "}
            {workload.comparisons.toLocaleString()} pair checks at {MINUTES_TO_CHECK_ONE_PAIR} min each:{" "}
            <span className="font-medium tabular-nums">+ {formatHours(pairCheckHours)}</span>{" "}
            <span className="text-muted-foreground">(estimate)</span>.
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pl-6">
            <span>
              Sentinel:{" "}
              {sentinelSeconds !== null && (
                <>
                  <span className="font-medium tabular-nums">{sentinelSeconds.toFixed(1)} s</span>.{" "}
                </>
              )}
              Agreed with you on{" "}
              <span className="font-medium">
                {agreed} of {firstFive.length}
              </span>
              .
            </span>
            {/* Listed here, not left to be found in the table: the list is
                ordered "needs attention first", so the first five emails of
                the inbox are rarely its first five rows. Each is marked
                beside its row as well. */}
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs">
              {firstFive.map((c) => {
                const right = guesses[c.email_id] === c.category;
                return (
                  <span
                    key={c.email_id}
                    className={right ? "text-ok" : "text-danger"}
                    title={`You said ${CATEGORY_LABELS[guesses[c.email_id]!]}; Sentinel said ${CATEGORY_LABELS[c.category]}`}
                  >
                    {c.email_id} {right ? "✓" : "✗"}
                  </span>
                );
              })}
            </span>
          </div>
        </motion.div>
      )}

      {!before && <WorthOpening runId={runId} cases={allCases} />}

      {!before && <PatternAlerts runId={runId} cases={allCases} openRequested={openPatterns} onOpened={consumeOpen} />}

      {/* Before Sentinel: the toolbar's place is kept, so the list does not
          jump when the mode flips; its controls all filter on things
          Sentinel produced. */}
      {before && (
        <motion.div className="flex items-center rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground" variants={fadeUp}>
          Filters, ordering and patterns come with Sentinel.
        </motion.div>
      )}

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
              {before ? (
                <>
                  <TableHead className={TH}>Email</TableHead>
                  <TableHead className={TH}>From</TableHead>
                  <TableHead className={TH}>Subject</TableHead>
                  <TableHead className={TH}>Attachments</TableHead>
                  <TableHead className={TH}>Your call</TableHead>
                  <TableHead />
                </>
              ) : (
                <>
                  <TableHead className={TH}>Email</TableHead>
                  <TableHead className={TH}>Category</TableHead>
                  <TableHead className={cn(TH, "text-right")}>Confidence</TableHead>
                  <TableHead className={TH}>Status</TableHead>
                  <TableHead className={TH}>Mismatched fields</TableHead>
                  <TableHead className={TH}>Decided by</TableHead>
                  <TableHead />
                </>
              )}
            </TableRow>
          </TableHeader>
          <TableBody key={`${filterKey}|${mode}`}>
            <AnimatePresence mode="popLayout" initial={false}>
              {!casesLoaded ? (
                // Distinct from the "no cases match this filter" row below:
                // that one is a real, finished answer, this one is standing
                // in for rows that just haven't arrived yet. Showing the
                // filter message here first, however briefly, was reading
                // as "there's nothing in this run" during the initial fetch.
                Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={`skeleton-${i}`}>
                    <TableCell colSpan={7} className="py-2.5">
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : (before ? allCases : visibleCases).length === 0 ? (
                <motion.tr key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                    {run?.status === "running" ? "Processing…" : "No cases match this filter."}
                  </TableCell>
                </motion.tr>
              ) : (
                (before ? allCases : visibleCases).map((c) => (
                  <motion.tr
                    key={c.email_id}
                    layout
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="border-b transition-colors last:border-0 hover:bg-muted/50"
                  >
                    {before ? (
                      <>
                        <TableCell className="font-mono text-sm">{c.email_id}</TableCell>
                        <TableCell className="max-w-[12rem] truncate text-sm text-muted-foreground" title={c.sender}>
                          {c.sender || "—"}
                        </TableCell>
                        <TableCell className="max-w-[22rem] truncate text-sm" title={c.subject}>
                          {c.subject || "(no subject)"}
                        </TableCell>
                        <TableCell
                          className="max-w-[16rem] truncate font-mono text-xs text-muted-foreground"
                          title={c.attachments.join(", ")}
                        >
                          {c.attachments.length > 0 ? c.attachments.join(", ") : "—"}
                        </TableCell>
                        <TableCell>
                          {firstFive.some((f) => f.email_id === c.email_id) ? (
                            <YourCall value={guesses[c.email_id]} onChange={(cat, at) => guess(c.email_id, cat, at)} />
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
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
                      </>
                    ) : (
                    <>
                    <TableCell className="font-mono text-sm">{c.email_id}</TableCell>
                    <TableCell>
                      <CategoryBadge category={c.category} />
                      {guesses[c.email_id] && (
                        <span
                          className={cn(
                            "ml-2 whitespace-nowrap text-xs",
                            guesses[c.email_id] === c.category ? "text-ok" : "text-danger",
                          )}
                          title="Your own call on this email, from Before Sentinel"
                        >
                          you said {CATEGORY_LABELS[guesses[c.email_id]]} {guesses[c.email_id] === c.category ? "✓" : "✗"}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground tabular-nums">
                      {Math.round(c.category_confidence * 100)}%
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={c.status} />
                      {/* How many fields, right on the badge -- the mentor's
                          words: "without clicking inside you can already
                          know there are two mismatches". The names are in the
                          next column; the count is what a scan of the list
                          picks up. */}
                      {c.status === "MISMATCH" && c.defect_fields.length > 0 && (
                        <span className="ml-1.5 whitespace-nowrap text-xs text-muted-foreground">
                          · {c.defect_fields.length} field{c.defect_fields.length === 1 ? "" : "s"}
                        </span>
                      )}
                      {/* A row a person overrode must not read like a row we
                          got right. The badge shows the outcome that stands;
                          this shows who it came from, and what we had said. */}
                      {c.outcome_source === "review" && (
                        <span
                          className="ml-2 whitespace-nowrap text-xs text-muted-foreground"
                          title={`Sentinel said ${STATUS_LABELS[c.system_status]}; corrected by a reviewer`}
                        >
                          Corrected
                        </span>
                      )}
                      {c.outcome_source === "system" && c.reviewed && (
                        <span className="ml-2 whitespace-nowrap text-xs text-muted-foreground">
                          Confirmed
                        </span>
                      )}
                      {/* The other way a case moves on after the run: the
                          sender re-sent a document and the check ran
                          again. The answer this row shows was reached on
                          that, not on what arrived in the inbox. */}
                      {c.recheck_count > 0 && (
                        <span
                          className="ml-2 whitespace-nowrap text-xs text-muted-foreground"
                          title="Re-checked on re-sent documents; the previous answer is kept on the case"
                        >
                          Re-checked
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
                    </>
                    )}
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
      <motion.div key={`${filterKey}|${mode}`} className="flex flex-col rounded-md border bg-card md:hidden" variants={fadeUp}>
        <AnimatePresence mode="popLayout" initial={false}>
          {!casesLoaded ? (
            <div className="flex flex-col gap-3 p-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={`skeleton-${i}`} className="h-16 w-full" />
              ))}
            </div>
          ) : (before ? allCases : visibleCases).length === 0 ? (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="p-8 text-center text-sm text-muted-foreground">
              {run?.status === "running" ? "Processing…" : "No cases match this filter."}
            </motion.div>
          ) : before ? (
            allCases.map((c) => (
              <BeforeRowCard
                key={c.email_id}
                runId={runId}
                c={c}
                guessable={firstFive.some((f) => f.email_id === c.email_id)}
                guess={guesses[c.email_id]}
                onGuess={(cat, at) => guess(c.email_id, cat, at)}
              />
            ))
          ) : (
            visibleCases.map((c) => <CaseRowCard key={c.email_id} runId={runId} c={c} guess={guesses[c.email_id]} />)
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}

// `ref` is forwarded to the motion.div because this is a direct child of an
// AnimatePresence in popLayout mode, which needs the DOM node to pop an
// exiting card out of the flow while it fades -- Framer's own documented
// requirement for custom components in that position. Without it the exit
// still runs, but in place, shoving the rows below it around as it goes.
/** Before Sentinel: one email as it sits in the inbox -- who, what subject,
 *  which files -- and, on the first five, the visitor's own call. The
 *  select sits outside the link so picking a category does not open the
 *  case. */
function BeforeRowCard({
  runId,
  c,
  guessable,
  guess,
  onGuess,
  ref,
}: {
  runId: string;
  c: CaseSummary;
  guessable: boolean;
  guess?: Category;
  onGuess: (cat: Category, at: number) => void;
  ref?: Ref<HTMLDivElement>;
}) {
  return (
    <motion.div
      ref={ref}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="border-b last:border-0"
    >
      <Link href={`/runs/${runId}/cases/${c.email_id}`}>
        <motion.div whileTap={TAP} transition={TAP_TRANSITION} className="flex flex-col gap-1 p-3 active:bg-muted/50">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm">{c.email_id}</span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
          </div>
          <div className="truncate text-sm">{c.subject || "(no subject)"}</div>
          <div className="truncate text-xs text-muted-foreground">{c.sender || "—"}</div>
          {c.attachments.length > 0 && (
            <div className="truncate font-mono text-xs text-muted-foreground">{c.attachments.join(", ")}</div>
          )}
        </motion.div>
      </Link>
      {guessable && (
        <div className="flex items-center gap-2 px-3 pb-3 text-xs text-muted-foreground">
          Your call:
          <YourCall value={guess} onChange={onGuess} />
        </div>
      )}
    </motion.div>
  );
}

/** The "Your call" control for the classify-five exercise: a plain select,
 *  the same five categories Sentinel picks from. */
function YourCall({ value, onChange }: { value?: Category; onChange: (cat: Category, at: number) => void }) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => {
        // The event's timestamp doubles as the click of the stopwatch.
        if (e.target.value) onChange(e.target.value as Category, e.timeStamp);
      }}
      aria-label="Your category for this email"
      className="rounded-md border bg-background px-2 py-1 text-xs text-foreground"
    >
      <option value="">Pick one…</option>
      {CATEGORIES.map((k) => (
        <option key={k} value={k}>
          {CATEGORY_LABELS[k]}
        </option>
      ))}
    </select>
  );
}

function CaseRowCard({
  runId,
  c,
  guess,
  ref,
}: {
  runId: string;
  c: CaseSummary;
  /** The visitor's own call from Before Sentinel, if they made one. */
  guess?: Category;
  ref?: Ref<HTMLDivElement>;
}) {
  return (
    <motion.div
      ref={ref}
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
              {c.status === "MISMATCH" && c.defect_fields.length > 0 && (
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  · {c.defect_fields.length} field{c.defect_fields.length === 1 ? "" : "s"}
                </span>
              )}
              <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <CategoryBadge category={c.category} />
            {guess && (
              <span className={cn("text-xs", guess === c.category ? "text-ok" : "text-danger")}>
                you said {CATEGORY_LABELS[guess]} {guess === c.category ? "✓" : "✗"}
              </span>
            )}
            <span>{Math.round(c.category_confidence * 100)}%</span>
            <DecidedByBadge decidedBy={c.decided_by} />
            {c.outcome_source === "review" && (
              <span title={`Sentinel said ${STATUS_LABELS[c.system_status]}; corrected by a reviewer`}>Corrected</span>
            )}
            {c.outcome_source === "system" && c.reviewed && <span>Confirmed</span>}
            {c.recheck_count > 0 && (
              <span title="Re-checked on re-sent documents; the previous answer is kept on the case">Re-checked</span>
            )}
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

/**
 * Three or four cases worth opening first, picked from this run by what
 * they are (lib/showcases.ts -- the same picks the home page's tiles use),
 * each landing on the panel that shows the thing. The mentor's point, one
 * screen earlier than the home page makes it: a judge who arrives straight
 * at a run should not have to open twenty rows to find the scanned pair or
 * the BL that never came.
 */
function WorthOpening({ runId, cases }: { runId: string; cases: CaseSummary[] }) {
  const picks = useMemo(() => pickShowcases(cases), [cases]);
  const mismatchFields = cases.find((c) => c.email_id === picks.mismatch)?.defect_fields.length ?? 0;
  const items = [
    {
      key: "mismatch",
      label: `a mismatch on ${mismatchFields} field${mismatchFields === 1 ? "" : "s"}`,
      emailId: picks.mismatch,
      spotlight: "fields",
    },
    { key: "recheck", label: "a BL that never arrived — re-upload it", emailId: picks.recheck, spotlight: "recheck" },
    // "read out" only when the model read it: a run made without the model
    // has scans on it and no transcript on any of them.
    {
      key: "scan",
      label: picks.scanReadOut ? "a scanned pair, read out" : "a scanned pair",
      emailId: picks.scan,
      spotlight: "documents",
    },
    { key: "history", label: "same shipper, same field, again", emailId: picks.history, spotlight: "history" },
  ].filter((i): i is typeof i & { emailId: string } => Boolean(i.emailId));
  if (items.length === 0) return null;

  return (
    <motion.div className="flex flex-wrap items-center gap-2 text-xs" variants={fadeUp}>
      <span className="text-muted-foreground">Worth opening:</span>
      {items.map((i) => (
        <Link
          key={i.key}
          href={showcaseHref(runId, i.emailId, i.spotlight)}
          className="rounded-full border bg-card px-2.5 py-1 transition-colors hover:border-primary/40 hover:bg-muted/40"
        >
          {i.label} <span className="font-mono text-muted-foreground">{i.emailId}</span>
        </Link>
      ))}
    </motion.div>
  );
}

/** One row of chips: "All" and the options, each with its count when the
 *  caller has one -- so the row is the run's own tally as much as a filter,
 *  and a first-time visitor sees what is there before clicking anything. */
function FilterGroup<T extends string>({
  label,
  options,
  value,
  onChange,
  renderLabel = (opt: T) => opt,
  counts,
  total,
  dot,
}: {
  label: string;
  options: T[];
  value: T | null;
  onChange: (v: T | null) => void;
  /** The words a person reads for each option (lib/labels.ts), never the
   *  backend code. */
  renderLabel?: (opt: T) => string;
  /** Whole-run count per option, and the run's total for the "All" chip. */
  counts?: Record<T, number>;
  total?: number;
  /** A colour class for a small dot before the label (the outcome row). */
  dot?: (opt: T) => string;
}) {
  const chip = (active: boolean) =>
    cn(
      "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs transition-colors",
      active ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:border-primary/40 hover:text-foreground",
    );
  const count = (n: number, active: boolean) => (
    <span className={cn("tabular-nums", active ? "text-primary-foreground/80" : "text-muted-foreground/80")}>{n.toLocaleString()}</span>
  );
  return (
    <div className="flex w-full min-w-0 items-center gap-1.5 text-sm sm:w-auto">
      {/* A fixed label column, so the chips of every row in the card start
          on the same line (the mentor's "everything must line up"). */}
      <span className="w-24 shrink-0 text-muted-foreground">{label}</span>
      <ScrollFade>
        <motion.button whileTap={TAP} transition={TAP_TRANSITION} onClick={() => onChange(null)} aria-pressed={value === null} className={chip(value === null)}>
          All
          {total !== undefined && count(total, value === null)}
        </motion.button>
        {options.map((opt) => (
          <motion.button
            key={opt}
            whileTap={TAP}
            transition={TAP_TRANSITION}
            onClick={() => onChange(opt)}
            aria-pressed={value === opt}
            className={chip(value === opt)}
          >
            {dot && <span aria-hidden className={cn("size-1.5 rounded-full", dot(opt))} />}
            {renderLabel(opt)}
            {counts && count(counts[opt], value === opt)}
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
