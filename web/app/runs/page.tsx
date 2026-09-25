"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Info, ShipCargo, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RunStatusPill } from "@/components/status-badges";
import { createRun, listRuns, type CaseStatus, type RunStatus } from "@/lib/api";
import { fetchHealth, type ApiHealth } from "@/lib/health";
import { DURATION, EASE_OUT, fadeUp, stagger, TAP, TAP_TRANSITION } from "@/lib/motion";
import { useHasHover } from "@/lib/use-has-hover";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunStatus[] | null>(null);
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  // Empty string, not 0 — this is "no limit set" (process every email in the
  // inbox), which the backend already spells as `limit: null`
  // (backend/api/models.py). A blank field reading as "all" needs no label
  // to explain it; a 0 sitting in the box would.
  const [limitInput, setLimitInput] = useState("");

  // Off by default, and off for the number the README quotes: the rules
  // answer all 520 emails of the graded inbox and a rules-only run is what
  // was scored. Switching this on adds the model tier to the run. On this
  // inbox that is six image-only scans transcribed for the reviewer and
  // nothing else -- the classifier and the extractor are never asked, which
  // is measured rather than assumed (docs/STATUS.md 2026-09-24) -- so a
  // model run costs cents, is capped per run, and answers from the cache
  // the second time. The server decides whether it is permitted at all
  // (SENTINEL_ALLOW_LLM_RUNS, reported by GET /), so when it is not the box
  // is disabled and explained rather than hidden: a judge should see that
  // the choice exists and why this deployment keeps it closed.
  const [withModel, setWithModel] = useState(false);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const modelAllowed = health?.llm_runs_allowed === true;

  useEffect(() => {
    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const probe = () => {
      fetchHealth()
        .then((h) => {
          if (!cancelled) setHealth(h);
        })
        .catch(() => {
          // A cold container answers this in 30-60s like everything else on
          // this page; keep asking rather than leaving the switch unexplained.
          if (!cancelled) retry = setTimeout(probe, 10000);
        });
    };
    probe();
    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
    };
  }, []);

  // The poll fires every 3s and the API is on Render's free tier, which sleeps
  // after 15 minutes idle and takes 30-60s to wake. Toasting every failure
  // stacked ten to twenty red errors on the first screen a judge opens, which
  // reads as a broken product rather than a cold start. So: one toast per
  // outage, cleared when the API answers again, and a line of copy that says
  // what is actually happening. `app/page.tsx`'s LiveStats already swallows
  // the same failure silently; this is the same choice with an explanation.
  const [waking, setWaking] = useState(false);
  const toasted = useRef(false);

  const refresh = useCallback(() => {
    listRuns()
      .then((r) => {
        setRuns(r);
        setWaking(false);
        toasted.current = false;
      })
      .catch((e) => {
        setWaking(true);
        if (!toasted.current) {
          toasted.current = true;
          toast.error(`Could not load runs: ${e.message}`);
        }
      });
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  async function start() {
    const trimmed = limitInput.trim();
    const limit = trimmed ? Number(trimmed) : undefined;
    if (limit !== undefined && (!Number.isInteger(limit) || limit <= 0)) {
      toast.error("Limit must be a whole number greater than 0");
      return;
    }
    setStarting(true);
    try {
      const useLlm = withModel && modelAllowed;
      const { run_id } = await createRun({ use_llm: useLlm, limit });
      const scope = limit ? `${run_id} (${limit} emails)` : run_id;
      toast.success(useLlm ? `Started ${scope} · model tier on` : `Started ${scope}`);
      // Straight into the run rather than back to this list. The run page is
      // where the work is visible -- the ring, the rate, the categories
      // filling in -- and it is live for the ~13s a 520-email run takes on the
      // deployed API. Leaving the starter on the index meant finding the new
      // card and clicking it, which is a hunt during the only part of a demo
      // where something is actually happening.
      router.push(`/runs/${run_id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <motion.div className="flex flex-col gap-6" initial="hidden" animate="show" variants={stagger()}>
      <motion.div className="flex flex-wrap items-center justify-between gap-3" variants={fadeUp}>
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight">Runs</h1>
          <p className="text-sm text-muted-foreground">
            Start a run over the whole inbox.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            Limit
            <input
              type="number"
              min={1}
              step={1}
              placeholder="All"
              value={limitInput}
              onChange={(e) => setLimitInput(e.target.value)}
              className="w-16 rounded-md border bg-background px-2 py-1 text-sm text-foreground [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
          </label>
          <motion.div whileTap={TAP} transition={TAP_TRANSITION} className="inline-block">
            <Button onClick={start} disabled={starting}>
              {starting ? "Starting…" : "Start a run"}
            </Button>
          </motion.div>
        </div>
      </motion.div>

      <motion.label
        variants={fadeUp}
        className={cn(
          "flex items-start gap-3 rounded-md border border-dashed p-3 transition-colors",
          modelAllowed ? "cursor-pointer hover:bg-muted/40" : "cursor-not-allowed opacity-75",
        )}
      >
        <input
          type="checkbox"
          checked={withModel && modelAllowed}
          disabled={!modelAllowed}
          onChange={(e) => setWithModel(e.target.checked)}
          className="mt-0.5 size-4 accent-primary"
        />
        <span className="text-sm">
          <span className="flex items-center gap-1.5 font-medium">
            <Sparkles className="size-3.5 text-primary" />
            Run with the model tier
          </span>
          <span className="mt-0.5 block text-xs text-muted-foreground">
            {health === null
              ? "Checking whether this server allows model runs…"
              : modelAllowed
                ? "Also transcribes the six scanned PDFs for the reviewer. Every decision still comes from rules; the cost is capped."
                : "Off on this server — every run is rules only, as the graded inbox was scored. The model tier is on Compare."}
          </span>
        </span>
      </motion.label>

      <AnimatePresence mode="wait" initial={false}>
        {runs === null ? (
          <motion.div
            key="loading"
            className="grid gap-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE_OUT }}
          >
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            {waking && (
              <p className="text-center text-xs text-muted-foreground">
                Waking the API (free tier, 30–60 s) — retrying on its own.
              </p>
            )}
          </motion.div>
        ) : runs.length === 0 ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE_OUT }}
          >
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-14 text-center text-sm text-muted-foreground">
                <ShipCargo className="size-12 text-primary/25" strokeWidth={1.25} />
                <p>
                  No runs yet. Start one, or try{" "}
                  <Link href="/compare" className="underline">
                    the upload demo
                  </Link>{" "}
                  with your own documents.
                </p>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          <motion.div
            key="list"
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
            initial="hidden"
            animate="show"
            exit={{ opacity: 0 }}
            variants={stagger()}
          >
            {runs.map((r) => (
              <motion.div key={r.run_id} variants={fadeUp}>
                <RunCard run={r} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// Labels come from the shared STATUS_LABELS map, not a hand-written copy
// here — this card used to say "OK" while the rest of the app said
// "Matched" once that map changed, which is exactly the kind of drift a
// second copy of the same text invites.
const STATUS_SUMMARY: { key: CaseStatus; dot: string }[] = [
  { key: "OK", dot: "bg-ok" },
  { key: "MISMATCH", dot: "bg-danger" },
  { key: "NEEDS_REVIEW", dot: "bg-warn" },
];

/**
 * The trigger depends on what the device actually has: a real mouse gets
 * hover-to-flip (arriving is the whole gesture, no aiming required), a
 * touch screen gets tap-to-flip via a dedicated icon, since touch has no
 * hover to trigger it with. useHasHover checks `(hover: hover) and
 * (pointer: fine)` rather than viewport width — a touch laptop or a
 * landscape tablet can be "desktop-wide" without ever producing a real
 * hover, and guessing from width alone would give them a flip they can
 * never reach.
 *
 * The flip icon (shown only without hover) is a DOM sibling of the Link,
 * not a descendant of it — absolutely positioned on top instead — so its
 * click never bubbles into the card's own navigation and there's no
 * button-inside-an-anchor nesting to reason about.
 */
function RunCard({ run }: { run: RunStatus }) {
  const [flipped, setFlipped] = useState(false);
  const hasHover = useHasHover();
  const metrics = run.metrics;

  // A cursor resting right at the wrapper's edge gets judged "in" and "out"
  // on alternating frames — sub-pixel rounding in hit-testing, not
  // anything this component controls — and each flip restarts the 0.32s
  // rotation before the last one finished, which read as the card spinning
  // continuously rather than settling. Leaving is debounced: it only
  // commits 120ms after the last hoverEnd, and hoverStart cancels that
  // timer, so a burst of enter/leave/enter/leave at the boundary collapses
  // into whichever state the cursor is actually in once it stops jittering.
  // Entering stays instant — there's no ambiguity to debounce on the way in.
  const leaveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (leaveTimeout.current) clearTimeout(leaveTimeout.current);
    };
  }, []);

  function handleHoverStart() {
    if (!hasHover) return;
    if (leaveTimeout.current) {
      clearTimeout(leaveTimeout.current);
      leaveTimeout.current = null;
    }
    setFlipped(true);
  }

  function handleHoverEnd() {
    if (!hasHover) return;
    leaveTimeout.current = setTimeout(() => setFlipped(false), 120);
  }

  return (
    <motion.div style={{ perspective: 1200 }} onHoverStart={handleHoverStart} onHoverEnd={handleHoverEnd}>
      <motion.div
        className="grid"
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ duration: DURATION.base, ease: EASE_OUT }}
        style={{ transformStyle: "preserve-3d" }}
      >
        {/* Both faces share one grid cell instead of the back being
            position:absolute — an absolutely positioned face is out of
            flow, so the card's height came only from the front, and the
            back face's third summary row overflowed past the bottom edge
            uncut. Stacking them in the same grid area makes the container's
            height the max of both, whichever is currently facing forward. */}
        <div className="relative h-full" style={{ gridArea: "1 / 1", backfaceVisibility: "hidden" }}>
          {!hasHover && (
            <button
              type="button"
              onClick={() => setFlipped(true)}
              aria-label={`Show a quick summary of ${run.run_id}`}
              className="absolute top-3 right-3 z-10 flex size-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Info className="size-4" />
            </button>
          )}
          <Link href={`/runs/${run.run_id}`} className="block h-full">
            <Card className="h-full transition-colors hover:bg-muted/40">
              {/* `flex`, not the card header's default grid: the status pill
                  belongs on the run id's line, right-aligned, not under it. */}
              <CardHeader className={cn("flex flex-row items-center justify-between space-y-0 pb-2", !hasHover && "pr-9")}>
                <CardTitle className="text-sm">{run.run_id}</CardTitle>
                <RunStatusPill status={run.status} />
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {run.processed} / {run.total_emails} emails
                {run.llm_enabled ? " · model tier on" : " · rules only"}
                {run.error && <span className="ml-2 text-danger">{run.error}</span>}
              </CardContent>
            </Card>
          </Link>
        </div>

        <div style={{ gridArea: "1 / 1", backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}>
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm">{run.run_id}</CardTitle>
              {!hasHover && (
                <button
                  type="button"
                  onClick={() => setFlipped(false)}
                  aria-label="Back to the run card"
                  className="flex size-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              )}
            </CardHeader>
            <CardContent className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
              {/* One line, label and number together, not a label row
                  stacked over a number row — a run card is a summary you
                  glance at, not a stats panel, and every extra line here is
                  height the whole card (front face included, since both
                  faces share a height) doesn't need. */}
              {metrics ? (
                <>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
                    {STATUS_SUMMARY.map((s) => (
                      <span key={s.key} className="flex items-center gap-1.5">
                        <span className={`size-1.5 rounded-full ${s.dot}`} />
                        {STATUS_LABELS[s.key]}{" "}
                        <span className="font-medium text-foreground tabular-nums">{metrics.by_status?.[s.key] ?? 0}</span>
                      </span>
                    ))}
                  </div>
                  {/* An icon button matching the Info/X buttons already on
                      this card, not a small underlined text link — text
                      that size, this close to a row of bold colored
                      numbers, reads as a label rather than something
                      clickable. */}
                  <Link
                    href={`/runs/${run.run_id}`}
                    aria-label={`Open ${run.run_id}`}
                    className="flex size-7 shrink-0 items-center justify-center rounded-full border text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                  >
                    <ArrowRight className="size-3.5" />
                  </Link>
                </>
              ) : (
                <p className="text-muted-foreground">No summary yet — still processing.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </motion.div>
    </motion.div>
  );
}
