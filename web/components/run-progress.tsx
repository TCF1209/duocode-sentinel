"use client";

/**
 * The panel a run shows while it is still going.
 *
 * It exists because of a measurement: the deployed API processes all 520
 * emails in **14 seconds** on Render's free CPU (39 → 142 → 272 → 350 → 433 →
 * 520, about 37 emails a second). Fourteen seconds is too long for a 128px
 * progress bar and a "312/520" caption — which is all this page had — and it is
 * the exact fourteen seconds someone demonstrating the product has to talk
 * over. Dead air there reads as "nothing is happening", which is the opposite
 * of what is happening.
 *
 * So the wait shows the work: the count ticks, the ring closes, the category
 * mix fills in, and the emails themselves scroll past as they finish. Every
 * number here is real and comes from the same two endpoints the table uses —
 * nothing is faked or eased for effect.
 *
 * Deliberately restrained about *what* it shows, though. Five categories and
 * three outcomes is the whole vocabulary; the full breakdown is one click away
 * on the metrics page. A progress screen that needs explaining has failed.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { DURATION, EASE_OUT } from "@/lib/motion";
import { STATUS_LABELS } from "@/lib/labels";
import type { CaseSummary, Category, CaseStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

// Same order and the same five colours the metrics page charts use, so the bar
// here and the donut there are read as the same fact seen twice.
const CATEGORY_COLOURS: Record<Category, string> = {
  BL_COMPARISON: "bg-chart-1",
  SI_REQUEST: "bg-chart-3",
  INVOICE_QUERY: "bg-chart-4",
  GENERAL: "bg-chart-2",
  SPAM: "bg-chart-5",
};
const CATEGORY_ORDER: Category[] = [
  "BL_COMPARISON",
  "SI_REQUEST",
  "INVOICE_QUERY",
  "GENERAL",
  "SPAM",
];

const OUTCOME_STYLE: Record<CaseStatus, { dot: string; text: string }> = {
  OK: { dot: "bg-ok", text: "text-ok" },
  MISMATCH: { dot: "bg-danger", text: "text-danger" },
  NEEDS_REVIEW: { dot: "bg-warn", text: "text-warn" },
};

/**
 * Springs towards `target` instead of restarting from zero.
 *
 * `useCountUp` in lib/motion.ts animates 0 → target every time target changes,
 * which is right for a figure that appears once and wrong for one that is
 * counting: at a 500ms poll it would snap back to 0 eighteen times on the way
 * to 520. This carries the previous value forward, so the poll interval stops
 * being visible.
 */
function useSmoothCount(target: number) {
  const value = useMotionValue(target);
  const spring = useSpring(value, { stiffness: 90, damping: 20, mass: 0.6 });
  const rounded = useTransform(spring, (v) => Math.round(v));
  const [shown, setShown] = useState(target);

  useEffect(() => value.set(target), [target, value]);
  useEffect(() => rounded.on("change", (v) => setShown(v)), [rounded]);
  return shown;
}

/**
 * Emails per second, over a short sliding window rather than since mount.
 *
 * A since-mount average was the first attempt and it read **10/s** against a
 * backend that recorded 24.8 ms per email — 40/s. The denominator was the
 * problem: the panel only mounts once the first status poll has returned, so
 * the window opened with a second or two in which nothing could have been
 * counted, and on a 13-second run that lag is most of the measurement. A
 * visibly wrong rate is worse than none at all — 520 at 10/s is 52 seconds,
 * and anyone watching the run finish in 13 can do that arithmetic.
 *
 * The window is what the last few seconds actually did, so it is right
 * whenever the panel mounted and it tracks the run speeding up or slowing
 * down instead of averaging both away.
 */
const RATE_WINDOW_MS = 3000;

function useRate(processed: number) {
  const samples = useRef<{ t: number; n: number }[]>([]);
  const [rate, setRate] = useState(0);

  useEffect(() => {
    const now = performance.now();
    const s = samples.current;
    if (s.length === 0 || s[s.length - 1].n !== processed) s.push({ t: now, n: processed });
    while (s.length > 2 && now - s[0].t > RATE_WINDOW_MS) s.shift();

    const first = s[0];
    const last = s[s.length - 1];
    const seconds = (last.t - first.t) / 1000;
    if (seconds > 0.4) setRate((last.n - first.n) / seconds);
  }, [processed]);

  return rate;
}

export function RunProgress({
  processed,
  total,
  cases,
  filtered,
  done = false,
}: {
  processed: number;
  total: number;
  cases: CaseSummary[];
  /** True when a filter is active, so the stream and tallies are a subset. */
  filtered: boolean;
  /**
   * True for the brief hold after the run finishes, before the panel
   * collapses — see run-page-view.tsx. "Reading the inbox" and a live
   * emails/second rate stop being true statements the instant the run is
   * done, so this swaps them for a completed heading and drops the rate row
   * rather than leaving stale process-in-progress language on screen.
   */
  done?: boolean;
}) {
  const count = useSmoothCount(processed);
  const rate = useRate(processed);
  const pct = total > 0 ? processed / total : 0;

  const remaining = rate > 1 ? Math.ceil((total - processed) / rate) : null;

  const tally = useMemo(() => {
    const byCategory = {} as Record<Category, number>;
    const byStatus = {} as Record<CaseStatus, number>;
    for (const c of cases) {
      byCategory[c.category] = (byCategory[c.category] ?? 0) + 1;
      byStatus[c.status] = (byStatus[c.status] ?? 0) + 1;
    }
    return { byCategory, byStatus };
  }, [cases]);

  // Newest first. The backend records completion order separately from the
  // case data (store.py's `_order`), so the tail of an unfiltered list really
  // is the most recently finished email rather than an artefact of array
  // position.
  const stream = useMemo(() => cases.slice(-5).reverse(), [cases]);

  return (
    <motion.div
      className="flex flex-col gap-5 overflow-hidden rounded-xl border bg-card p-5"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, paddingTop: 0, paddingBottom: 0, marginBottom: 0 }}
      transition={{ duration: DURATION.base, ease: EASE_OUT }}
    >
      <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center sm:gap-6">
        <ProgressRing pct={pct} count={count} total={total} />

        <div className="flex min-w-0 flex-1 flex-col gap-3 text-center sm:text-left">
          <div>
            <h2 className="font-heading text-lg font-semibold">
              {done ? "Done reading the inbox" : "Reading the inbox"}
            </h2>
            <p className="text-sm text-muted-foreground">
              Every email classified, every document pair compared, on rules alone — no
              model call, no network.
            </p>
          </div>

          {!done && (
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm text-muted-foreground sm:justify-start">
              <span>
                <span className="font-mono font-medium text-foreground">
                  {rate > 0 ? Math.round(rate) : "—"}
                </span>{" "}
                emails / second
              </span>
              <span aria-hidden className="text-border">
                ·
              </span>
              <span>
                {remaining === null
                  ? "estimating…"
                  : remaining <= 1
                    ? "finishing"
                    : `about ${remaining}s left`}
              </span>
            </div>
          )}

          <CategoryBar byCategory={tally.byCategory} total={total} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {(["OK", "MISMATCH", "NEEDS_REVIEW"] as CaseStatus[]).map((s) => (
          <OutcomeTile key={s} status={s} value={tally.byStatus[s] ?? 0} />
        ))}
      </div>

      {!filtered && stream.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Just finished
          </div>
          {/*
            No AnimatePresence here, deliberately, and the first attempt is
            worth recording because it looked right and was not.

            The case list arrives on a 2s poll and about 80 emails land in
            that time, so all five rows are replaced at once rather than
            scrolling one at a time. Under AnimatePresence that mounts five
            entering children beside five exiting ones, and with the older-row
            fade driven by index inside `animate`, the enter/exit opacity and
            the index opacity fought over the same property: inspected in the
            DOM mid-run, the five new rows had reached their `y` targets and
            were stuck at `opacity: 0` while the five old rows sat at full
            opacity and never left. Ten rows, five of them invisible, and on
            screen it read as an empty panel under a heading.

            So: keyed by slot *and* email, which remounts a row when the email
            in that slot changes and plays a plain fade-in with no exit to
            coordinate. The older-row fade is a gradient mask on the container,
            which is a paint effect and cannot collide with an animation.
          */}
          <div
            className="flex flex-col"
            style={{
              maskImage: "linear-gradient(to bottom, black 45%, transparent 100%)",
              WebkitMaskImage: "linear-gradient(to bottom, black 45%, transparent 100%)",
            }}
          >
            {stream.map((c, i) => (
              <motion.div
                key={`${i}-${c.email_id}`}
                className="flex items-center gap-2 py-1 text-sm"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: DURATION.fast, ease: EASE_OUT, delay: i * 0.04 }}
              >
                <span
                  aria-hidden
                  className={cn("size-1.5 shrink-0 rounded-full", OUTCOME_STYLE[c.status].dot)}
                />
                <span className="font-mono text-xs">{c.email_id}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {c.category.replace(/_/g, " ").toLowerCase()}
                </span>
                <span className={cn("ml-auto shrink-0 text-xs", OUTCOME_STYLE[c.status].text)}>
                  {STATUS_LABELS[c.status]}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function ProgressRing({ pct, count, total }: { pct: number; count: number; total: number }) {
  const R = 52;
  const C = 2 * Math.PI * R;
  return (
    <div className="relative size-32 shrink-0">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90">
        <circle cx="60" cy="60" r={R} fill="none" strokeWidth="8" className="stroke-muted" />
        <motion.circle
          cx="60"
          cy="60"
          r={R}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          className="stroke-primary"
          strokeDasharray={C}
          initial={{ strokeDashoffset: C }}
          animate={{ strokeDashoffset: C * (1 - pct) }}
          transition={{ duration: DURATION.slow, ease: EASE_OUT }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-2xl font-semibold tabular-nums">{count}</span>
        <span className="font-mono text-xs text-muted-foreground">of {total}</span>
      </div>
    </div>
  );
}

/**
 * One bar, five segments, growing left to right as the mix is discovered.
 *
 * Widths are a share of the *total* rather than of what has been read so far,
 * so the bar fills up instead of resegmenting on every poll — the categories
 * are interleaved through the inbox, so a share-of-processed bar twitches
 * sideways the whole way through and reads as instability rather than progress.
 */
function CategoryBar({
  byCategory,
  total,
}: {
  byCategory: Record<Category, number>;
  total: number;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        {CATEGORY_ORDER.map((c) => (
          <motion.div
            key={c}
            className={CATEGORY_COLOURS[c]}
            initial={{ width: 0 }}
            animate={{ width: `${total > 0 ? ((byCategory[c] ?? 0) / total) * 100 : 0}%` }}
            transition={{ duration: DURATION.slow, ease: EASE_OUT }}
          />
        ))}
      </div>
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground sm:justify-start">
        {CATEGORY_ORDER.map((c) => (
          <span key={c} className="flex items-center gap-1">
            <span aria-hidden className={cn("size-1.5 rounded-full", CATEGORY_COLOURS[c])} />
            {c.replace(/_/g, " ").toLowerCase()}
            <span className="font-mono tabular-nums">{byCategory[c] ?? 0}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function OutcomeTile({ status, value }: { status: CaseStatus; value: number }) {
  const shown = useSmoothCount(value);
  const style = OUTCOME_STYLE[status];
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border bg-background/60 px-3 py-2">
      <span className="flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
        <span aria-hidden className={cn("size-1.5 rounded-full", style.dot)} />
        {STATUS_LABELS[status]}
      </span>
      <span className={cn("font-mono text-xl font-semibold tabular-nums", style.text)}>
        {shown}
      </span>
    </div>
  );
}
