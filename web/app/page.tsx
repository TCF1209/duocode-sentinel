"use client";

import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform, type MotionValue } from "motion/react";
import {
  ArrowRight,
  Eye,
  FileSearch,
  GitCompareArrows,
  Inbox,
  Layers,
  Mail,
  RefreshCw,
  ScanLine,
  ShipCargo,
  UserCheck,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listCases, listRuns, type CaseSummary, type Category, type RunStatus } from "@/lib/api";
import { pickShowcases, SAMPLE_SCAN_HREF, showcaseHref, type ShowcaseKey } from "@/lib/showcases";
import { fadeUp, stagger, TAP, TAP_TRANSITION, useCountUp } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { CATEGORY_LABELS } from "@/lib/labels";

/** The landing page — what this is and how it works, nothing operational on it. */
export default function HomePage() {
  return (
    <motion.div className="flex flex-col gap-10" initial="hidden" animate="show" variants={stagger()}>
      <motion.div className="flex flex-col gap-5" variants={fadeUp}>
        <div className="max-w-2xl">
          <p className="font-mono text-xs tracking-[0.14em] text-primary uppercase">
            Shipping document verification
          </p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance">
            Catch a mismatched shipment before the paperwork ships
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Reads the inbox, checks each Shipping Instruction against its draft Bill of Lading on 7 fields, and sends
            anything it can&apos;t confirm to a person — with the evidence.
          </p>
        </div>

        <PipelineRoadmap
          steps={[
            {
              icon: Inbox,
              step: "1. Classify",
              text: "Sort the inbox: comparison requests, SI requests, invoice queries, general, spam.",
            },
            {
              icon: FileSearch,
              step: "2. Extract",
              text: "Pull the 7 fields from the SI and the BL, whatever the labels say.",
            },
            {
              icon: GitCompareArrows,
              step: "3. Compare",
              text: "Which fields agree and which don't, side by side.",
            },
            {
              icon: UserCheck,
              step: "4. Escalate",
              text: "Missing, unreadable or unsure? A person gets it, with the reason.",
            },
          ]}
        />
      </motion.div>

      <motion.div className="flex flex-col gap-4 border-t pt-6" variants={fadeUp}>
        <div>
          <h2 className="font-heading text-xl font-semibold tracking-tight">What it&apos;s caught so far</h2>
          <p className="text-sm text-muted-foreground">
            From the latest run over the graded inbox.
          </p>
        </div>
        <LiveStats />
      </motion.div>

      <motion.div className="flex flex-col gap-4 border-t pt-6" variants={fadeUp}>
        <div>
          <h2 className="font-heading text-xl font-semibold tracking-tight">See it live</h2>
          <p className="text-sm text-muted-foreground">
            Each tile opens a real case from the latest run.
          </p>
        </div>
        <SeeItLive />
        <div className="flex flex-wrap gap-3">
          <motion.div whileTap={TAP} transition={TAP_TRANSITION} className="inline-block">
            <Link href="/runs">
              <Button>Go to Runs</Button>
            </Link>
          </motion.div>
          <motion.div whileTap={TAP} transition={TAP_TRANSITION} className="inline-block">
            <Link href="/compare">
              <Button variant="outline">Compare two documents</Button>
            </Link>
          </motion.div>
        </div>
      </motion.div>
    </motion.div>
  );
}

/**
 * The mentor's largest point (24 Sep): the features that set this apart --
 * correction by re-upload, scans read out, shipper history, the original a
 * click away, a drafted reply, patterns -- all live deep inside a case page,
 * where a judge exploring alone never finds them. These tiles bring them to
 * the landing page, and each one links not just to a case but to the panel
 * on it (`?spotlight=`, case-report-view.tsx), chosen from the latest
 * finished run by what the case *is* -- never a hard-coded email id.
 */
interface Showcase {
  key: string;
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  title: string;
  text: string;
  /** Which pick to link to (lib/showcases.ts), and the panel to land on.
   *  `patterns` links to the run page's own card instead. */
  pick: ShowcaseKey | "patterns";
  spotlight?: string;
}

const SHOWCASES: Showcase[] = [
  {
    key: "recheck",
    icon: RefreshCw,
    title: "Correct by re-upload",
    text: "Re-send the BL; the check runs again.",
    pick: "recheck",
    spotlight: "recheck",
  },
  {
    key: "scan",
    icon: ScanLine,
    title: "Scans read out for the reviewer",
    text: "Image-only PDF, read out for the reviewer.",
    pick: "scan",
    spotlight: "documents",
  },
  {
    key: "history",
    icon: Users,
    title: "Shipper history on the field",
    text: "Same shipper, same field, again.",
    pick: "history",
    spotlight: "history",
  },
  {
    key: "original",
    icon: Eye,
    title: "The original, one click away",
    text: "Every value links to its line in the file.",
    pick: "mismatch",
    spotlight: "documents",
  },
  {
    key: "reply",
    icon: Mail,
    title: "A reply drafted from the outcome",
    text: "Subject and body written; a person sends it.",
    pick: "mismatch",
    spotlight: "reply",
  },
  {
    key: "patterns",
    icon: Layers,
    title: "Patterns across the inbox",
    text: "One shipper, one field, seven emails.",
    pick: "patterns",
  },
];

function SeeItLive() {
  const [runId, setRunId] = useState<string | null | undefined>(undefined);
  const [cases, setCases] = useState<CaseSummary[] | null>(null);

  useEffect(() => {
    listRuns()
      .then((runs) => setRunId(runs.find((r) => r.status === "done")?.run_id ?? null))
      .catch(() => setRunId(null));
  }, []);
  useEffect(() => {
    if (!runId) return;
    listCases(runId, {})
      .then((r) => setCases(r.cases))
      .catch(() => setCases([]));
  }, [runId]);

  const picks = useMemo(() => pickShowcases(cases ?? []), [cases]);

  if (runId === undefined || (runId && cases === null)) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {SHOWCASES.map((s) => (
          <Skeleton key={s.key} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {SHOWCASES.map((s) => {
        const Icon = s.icon;
        let href: string | null = null;
        let cta = "Open a real case";
        // Said on the tile when it cannot go where its text promises.
        let note: string | null = null;
        if (s.pick === "scan" && !picks.scanReadOut) {
          // No scan in this run was read out -- the API's own startup run
          // makes no model call, by design -- so a scan here would open on
          // "could not be read" and nothing more. The Compare page's scanned
          // pair, with the model on, shows what this tile promises, live.
          href = SAMPLE_SCAN_HREF;
          cta = "Read a sample scan out";
          note = "This run ran without the model.";
        } else if (runId) {
          if (s.pick === "patterns") {
            href = `/runs/${runId}?open=patterns`;
            cta = "Open the run";
          } else {
            const emailId = picks[s.pick];
            if (emailId) href = showcaseHref(runId, emailId, s.spotlight);
          }
        }
        const body = (
          <>
            <span className="flex items-center gap-2.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10">
                <Icon className="size-4 text-primary" strokeWidth={1.75} />
              </span>
              <span className="text-sm font-semibold">{s.title}</span>
            </span>
            <span className="text-xs text-muted-foreground">{s.text}</span>
            {note && <span className="text-xs text-warn">{note}</span>}
            <span className="mt-auto flex items-center gap-1 pt-1 text-xs font-medium text-primary">
              {href ? cta : "No such case in the latest run"}
              {href && <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />}
            </span>
          </>
        );
        const className = cn(
          "group flex flex-col gap-2 rounded-xl border bg-card p-4 text-left transition-all",
          href ? "hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-md" : "opacity-70",
        );
        return href ? (
          <Link key={s.key} href={href} className={className}>
            {body}
          </Link>
        ) : (
          <div key={s.key} className={className}>
            {body}
          </div>
        );
      })}
    </div>
  );
}

interface Step {
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  step: string;
  text: string;
}

/**
 * Apple-product-page grammar, played with what we actually have (no 3D
 * render, no film): a cargo ship stands in for the product, pinned in view
 * on the right while the steps scroll past on the left — rotating and
 * growing with scroll progress, not autoplay. Each stop dims until the ship
 * is abreast of it, then lights up and holds — the "text ignites as you
 * arrive" beat from the reference page.
 */
function PipelineRoadmap({ steps }: { steps: Step[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start 0.8", "end 0.35"],
  });

  const shipRotate = useTransform(scrollYProgress, [0, 0.33, 0.66, 1], [-5, 4, -4, 5]);
  const shipScale = useTransform(scrollYProgress, [0, 1], [0.92, 1.06]);

  return (
    <div ref={containerRef} className="grid gap-7 lg:grid-cols-[1fr_18rem] lg:items-start lg:gap-12">
      <div className="flex flex-col gap-7">
        {steps.map((s, i) => (
          <RoadmapStep key={s.step} {...s} threshold={i / (steps.length - 1)} scrollYProgress={scrollYProgress} />
        ))}
      </div>

      {/*
       * The glow is a plain radial-gradient, not a blurred div: `filter:
       * blur()` repaints on every frame its transformed ancestor moves,
       * which is exactly what was making the scroll janky. A gradient
       * background composites on the GPU like any other transform, so it
       * stays static here rather than sharing the ship's rotate/scale.
       */}
      <div className="sticky top-24 hidden h-72 items-center justify-center lg:flex">
        <div
          aria-hidden
          className="absolute size-48 rounded-full"
          style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)", opacity: 0.22 }}
        />
        <motion.div style={{ rotate: shipRotate, scale: shipScale }}>
          <ShipCargo className="relative size-28 text-primary" strokeWidth={1} />
        </motion.div>
      </div>
    </div>
  );
}

function RoadmapStep({
  icon: Icon,
  step,
  text,
  threshold,
  scrollYProgress,
}: Step & { threshold: number; scrollYProgress: MotionValue<number> }) {
  // Only the icon badge dims/lights with scroll — text stays fully readable
  // at every position. Dimming a paragraph already sitting on
  // text-muted-foreground compounds two contrast cuts at once, which is
  // exactly what made steps 3–4 hard to read: legible now, not just lit.
  const litFrom = Math.max(0, threshold - 0.22);
  const badgeOpacity = useTransform(scrollYProgress, [litFrom, threshold], [0.45, 1]);
  const badgeScale = useTransform(scrollYProgress, [litFrom, threshold], [0.92, 1]);

  return (
    <div className="flex gap-4">
      <motion.div
        style={{ opacity: badgeOpacity, scale: badgeScale }}
        className="flex size-12 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10"
      >
        <Icon className="size-5 text-primary" strokeWidth={1.75} />
      </motion.div>
      <div className="flex flex-col gap-1 pt-0.5">
        <div className="text-base font-medium">{step}</div>
        <p className="max-w-md text-sm text-muted-foreground">{text}</p>
      </div>
    </div>
  );
}

// Object.keys() on a string-keyed object preserves insertion order, so this
// doubles as the display order — no separate ordered array to keep in sync
// with lib/labels.ts's CATEGORY_LABELS.
const CATEGORY_KEYS = Object.keys(CATEGORY_LABELS) as Category[];

/**
 * Pulled from whatever run actually finished most recently — never
 * hardcoded. `listRuns()` already returns each run's own metrics inline, so
 * this needs no second endpoint. If nothing has finished yet, the honest
 * answer is a prompt to go make one, not a placeholder number.
 */
function LiveStats() {
  const [runs, setRuns] = useState<RunStatus[] | null>(null);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(() => setRuns([]));
  }, []);

  if (runs === null) {
    return (
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  const latest = runs.find((r) => r.status === "done" && r.metrics);

  if (!latest || !latest.metrics) {
    return (
      <div className="rounded-xl border bg-card px-5 py-8 text-center text-sm text-muted-foreground">
        No runs finished yet — start one to see real numbers here.
      </div>
    );
  }

  const m = latest.metrics;
  const mismatches = m.by_status?.MISMATCH ?? 0;
  const escalated = m.by_status?.NEEDS_REVIEW ?? 0;
  const runHref = `/runs/${latest.run_id}`;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <BigStat label="Emails processed" value={m.emails} accent="primary" href={runHref} />
        <BigStat label="Mismatches caught" value={mismatches} accent="danger" href={`${runHref}?status=MISMATCH`} />
        <BigStat
          label="Escalated to a person"
          value={escalated}
          accent="warn"
          href={`${runHref}?status=NEEDS_REVIEW`}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {CATEGORY_KEYS.map((key) => (
          <MiniStat
            key={key}
            label={CATEGORY_LABELS[key]}
            value={m.by_category?.[key] ?? 0}
            href={`${runHref}?category=${key}`}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        From{" "}
        <Link href={`/runs/${latest.run_id}`} className="underline">
          {latest.run_id}
        </Link>
      </p>
    </div>
  );
}

const STAT_ACCENT = {
  primary: "text-primary",
  danger: "text-danger",
  warn: "text-warn",
} as const;

function BigStat({
  label,
  value,
  accent,
  href,
}: {
  label: string;
  value: number;
  accent: keyof typeof STAT_ACCENT;
  href: string;
}) {
  const display = useCountUp(value);
  return (
    <Link
      href={href}
      className="group rounded-xl border bg-card p-5 transition-colors hover:border-primary/40 hover:bg-muted/40"
    >
      <div className={cn("font-heading text-4xl font-semibold tabular-nums", STAT_ACCENT[accent])}>{display}</div>
      <div className="mt-1 flex items-center gap-1 text-sm text-muted-foreground">
        {label}
        <span className="opacity-0 transition-opacity group-hover:opacity-100">→</span>
      </div>
    </Link>
  );
}

function MiniStat({ label, value, href }: { label: string; value: number; href: string }) {
  const display = useCountUp(value);
  return (
    <Link
      href={href}
      className="rounded-lg border bg-card px-3 py-2 text-center transition-colors hover:border-primary/40 hover:bg-muted/40"
    >
      <div className="font-heading text-lg font-semibold tabular-nums">{display}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </Link>
  );
}
