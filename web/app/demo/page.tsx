"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, Cloud, Code2, Loader2, Server, ShipCargo, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CaseReportView } from "@/components/case-report-view";
import { RunStatusPill } from "@/components/status-badges";
import { BigStat, MiniStat } from "@/components/big-stat";
import { PIPELINE_STEPS } from "@/lib/pipeline-steps";
import { SAMPLES, loadSamplePair } from "@/lib/samples";
import { STATUS_LABELS, CATEGORY_LABELS } from "@/lib/labels";
import { DURATION, EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import {
  createRun,
  getRun,
  listCases,
  getCase,
  compareUploads,
  type RunStatus,
  type CaseReport,
  type CaseStatus,
  type Category,
} from "@/lib/api";

/**
 * A guided, presenter-paced walkthrough over the *real* product — every
 * number and every model call here is live, nothing is scripted or replayed.
 * Mirrors the mandatory demo video's own required section order (Intro,
 * Problem, Tech Stack, Live Demo, Impact) one-to-one, with "Live Demo" split
 * into three small beats instead of one: the batch inbox (breadth, rules
 * only, the speed claim), the evidence screen (docs/ROADMAP.md 3b: "the
 * screen the whole project exists to produce"), and the model actually
 * reading something the rules could not (docs/ROADMAP.md 3d). A presenter
 * can follow this page step by step on camera and hit every required
 * section without ad-libbing the order.
 *
 * All state lives here, not in the step components below — AnimatePresence
 * remounts whichever step is showing on every Back/Next, and a run started
 * in step 4 has to still be there when step 5 or 7 asks for it.
 */
const STEP_TITLES = ["Welcome", "The problem", "Tech stack", "The inbox", "The evidence", "The model", "Impact"];

const STATUS_DOT: Record<CaseStatus, string> = { OK: "bg-ok", MISMATCH: "bg-danger", NEEDS_REVIEW: "bg-warn" };

export default function DemoPage() {
  const [step, setStep] = useState(0);

  const [run, setRun] = useState<RunStatus | null>(null);
  const [runStarting, setRunStarting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [mismatch, setMismatch] = useState<CaseReport | null>(null);
  const [mismatchLoading, setMismatchLoading] = useState(false);
  const [mismatchError, setMismatchError] = useState<string | null>(null);

  const [aiReport, setAiReport] = useState<CaseReport | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Polls only while a run is actually in flight, and stops the moment it
  // isn't — same reasoning as run-page-view.tsx: depend on the primitive
  // id/status, not the `run` object itself, or this tears the interval down
  // and rebuilds it on every tick.
  const runId = run?.run_id;
  const runStatus = run?.status;
  useEffect(() => {
    if (!runId || runStatus !== "running") return;
    const id = setInterval(() => {
      getRun(runId).then(setRun).catch(() => {});
    }, 1200);
    return () => clearInterval(id);
  }, [runId, runStatus]);

  async function startRun() {
    setRunStarting(true);
    setRunError(null);
    try {
      // Explicitly false: POST /runs 403s on use_llm=true (a public,
      // unauthenticated endpoint stays rules-only by design) — the model
      // gets its own dedicated beat two steps later instead.
      const { run_id } = await createRun({ use_llm: false });
      setRun(await getRun(run_id));
    } catch (e) {
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunStarting(false);
    }
  }

  async function findMismatch() {
    if (!run) return;
    setMismatchLoading(true);
    setMismatchError(null);
    try {
      const { cases } = await listCases(run.run_id, { status: "MISMATCH" });
      const first = cases[0];
      if (!first) {
        setMismatchError("This run didn't produce a mismatch — rare on the curated demo inbox. Try again, or open the run from Runs.");
        return;
      }
      setMismatch(await getCase(run.run_id, first.email_id));
    } catch (e) {
      setMismatchError(e instanceof Error ? e.message : String(e));
    } finally {
      setMismatchLoading(false);
    }
  }

  async function runAiSample() {
    setAiBusy(true);
    setAiError(null);
    try {
      const { si, bl } = await loadSamplePair(SAMPLES[0]);
      setAiReport(await compareUploads(si, bl, true));
    } catch (e) {
      setAiError(e instanceof Error ? e.message : String(e));
    } finally {
      setAiBusy(false);
    }
  }

  const next = () => setStep((s) => Math.min(s + 1, STEP_TITLES.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="flex flex-col gap-6">
      <DemoStepper step={step} onJump={setStep} />

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: DURATION.base, ease: EASE_OUT }}
        >
          {step === 0 && <WelcomeStep onNext={next} />}
          {step === 1 && <ProblemStep />}
          {step === 2 && <TechStackStep />}
          {step === 3 && <InboxStep run={run} starting={runStarting} error={runError} onStart={startRun} />}
          {step === 4 && (
            <EvidenceStep
              ready={run?.status === "done"}
              mismatch={mismatch}
              loading={mismatchLoading}
              error={mismatchError}
              onFind={findMismatch}
            />
          )}
          {step === 5 && <AiStep report={aiReport} busy={aiBusy} error={aiError} onRun={runAiSample} />}
          {step === 6 && <ImpactStep run={run} />}
        </motion.div>
      </AnimatePresence>

      {step > 0 && (
        <div className="flex items-center justify-between border-t pt-4">
          <Button variant="outline" onClick={back}>
            <ArrowLeft className="size-4" />
            Back
          </Button>
          {step < STEP_TITLES.length - 1 && (
            <Button onClick={next}>
              Next
              <ArrowRight className="size-4" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function DemoStepper({ step, onJump }: { step: number; onJump: (i: number) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Step {step + 1} of {STEP_TITLES.length}
        </span>
        <span className="font-medium text-foreground">{STEP_TITLES[step]}</span>
      </div>
      <div className="flex gap-1.5">
        {STEP_TITLES.map((title, i) => (
          <button
            key={title}
            type="button"
            onClick={() => onJump(i)}
            aria-label={`Go to step ${i + 1}: ${title}`}
            className={cn("h-1.5 flex-1 rounded-full transition-colors", i === step ? "bg-primary" : i < step ? "bg-primary/40" : "bg-muted")}
          />
        ))}
      </div>
    </div>
  );
}

function StepHeading({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h1 className="font-heading text-2xl font-semibold tracking-tight text-balance">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{text}</p>
    </div>
  );
}

function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="flex flex-col items-center gap-5 py-10 text-center">
      <span className="flex size-16 items-center justify-center rounded-full border border-primary/30 bg-primary/10">
        <ShipCargo className="size-8 text-primary" strokeWidth={1.5} />
      </span>
      <div className="max-w-lg">
        <p className="font-mono text-xs tracking-[0.14em] text-primary uppercase">Welcome to the Sentinel demo</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance">
          Catch a mismatched shipment before the paperwork ships
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Seven short steps, each one real: a real inbox, a real model call, real numbers. Nothing on the following
          screens is pre-recorded or replayed.
        </p>
      </div>
      <Button size="lg" onClick={onNext}>
        Start the walkthrough
        <ArrowRight className="size-4" />
      </Button>
    </div>
  );
}

function ProblemStep() {
  return (
    <div className="flex flex-col gap-5">
      <StepHeading
        title="The problem"
        text="A shipping operations inbox mixes document checks with new requests, invoice questions and plain noise — and a comparison has to catch a mismatch before the paperwork ships."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        {PIPELINE_STEPS.map((s) => (
          <div key={s.step} className="flex gap-3 rounded-xl border bg-card p-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10">
              <s.icon className="size-5 text-primary" strokeWidth={1.75} />
            </span>
            <div>
              <div className="font-medium">{s.step}</div>
              <p className="text-sm text-muted-foreground">{s.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const STACK = [
  { icon: Code2, label: "Next.js 16 + Tailwind", text: "This dashboard — a client app talking straight to the API, no server-rendered state to keep in sync." },
  { icon: Server, label: "FastAPI (Python)", text: "10 routes over one deterministic pipeline. No web or database code lives inside the pipeline itself." },
  { icon: Sparkles, label: "OpenAI, as a fallback", text: "Off for all 520 emails of the graded inbox. On only for label wording or scans the rules can't resolve." },
  { icon: Cloud, label: "Vercel + Render", text: "Deployed straight from this repository's own committed config — nothing clicked together by hand." },
];

function TechStackStep() {
  return (
    <div className="flex flex-col gap-5">
      <StepHeading title="Tech stack" text="Four pieces, each doing exactly one job." />
      <div className="grid gap-3 sm:grid-cols-2">
        {STACK.map((s) => (
          <div key={s.label} className="flex gap-3 rounded-xl border bg-card p-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10">
              <s.icon className="size-5 text-primary" strokeWidth={1.75} />
            </span>
            <div>
              <div className="font-medium">{s.label}</div>
              <p className="text-sm text-muted-foreground">{s.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InboxStep({
  run,
  starting,
  error,
  onStart,
}: {
  run: RunStatus | null;
  starting: boolean;
  error: string | null;
  onStart: () => void;
}) {
  const progress = run && run.total_emails > 0 ? Math.round((run.processed / run.total_emails) * 100) : 0;
  return (
    <div className="flex flex-col gap-5">
      <StepHeading
        title="Live demo — the inbox"
        text="One click, the real pipeline, the real demo inbox — rules only, no model call, no answer key involved."
      />
      <div className="rounded-xl border bg-card p-6">
        {!run ? (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <p className="text-sm text-muted-foreground">Nothing has run yet in this walkthrough.</p>
            <Button size="lg" onClick={onStart} disabled={starting}>
              {starting && <Loader2 className="size-4 animate-spin" />}
              {starting ? "Starting…" : "Run the demo inbox"}
            </Button>
            {error && <p className="text-xs text-danger">{error}</p>}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm">{run.run_id}</span>
              <RunStatusPill status={run.status} />
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-300"
                style={{ width: `${run.status === "done" ? 100 : progress}%` }}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              {run.processed}/{run.total_emails} emails processed
              {run.status === "done" && run.metrics && ` in ${run.metrics.total_ms.toFixed(0)}ms — rules decided every one of them.`}
            </p>
            {run.status === "done" && run.metrics && (
              <div className="flex flex-wrap gap-3 pt-1 text-sm">
                {(["OK", "MISMATCH", "NEEDS_REVIEW"] as CaseStatus[]).map((s) => (
                  <span key={s} className="flex items-center gap-1.5">
                    <span className={cn("size-1.5 rounded-full", STATUS_DOT[s])} />
                    {STATUS_LABELS[s]} <span className="font-medium text-foreground tabular-nums">{run.metrics!.by_status?.[s] ?? 0}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceStep({
  ready,
  mismatch,
  loading,
  error,
  onFind,
}: {
  ready: boolean;
  mismatch: CaseReport | null;
  loading: boolean;
  error: string | null;
  onFind: () => void;
}) {
  return (
    <div className="flex flex-col gap-5">
      <StepHeading
        title="Live demo — the evidence"
        text="The screen the whole project exists to produce: every field, both sides, the exact line each value was read from."
      />
      {mismatch ? (
        <div className="rounded-xl border bg-card p-6">
          <CaseReportView report={mismatch} />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-xl border bg-card p-6 py-10 text-center">
          <p className="text-sm text-muted-foreground">
            {ready ? "Pull up a real mismatch from the run you just started." : "Finish the previous step's run first, then come back here."}
          </p>
          <Button size="lg" onClick={onFind} disabled={!ready || loading}>
            {loading && <Loader2 className="size-4 animate-spin" />}
            {loading ? "Looking…" : "Show me a real mismatch"}
          </Button>
          {error && <p className="text-xs text-danger">{error}</p>}
        </div>
      )}
    </div>
  );
}

function AiStep({
  report,
  busy,
  error,
  onRun,
}: {
  report: CaseReport | null;
  busy: boolean;
  error: string | null;
  onRun: () => void;
}) {
  const sample = SAMPLES[0];
  return (
    <div className="flex flex-col gap-5">
      <StepHeading title="Live demo — the model" text={sample.blurb} />
      {report ? (
        <div className="rounded-xl border bg-card p-6">
          <CaseReportView report={report} />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-xl border bg-card p-6 py-10 text-center">
          <p className="text-sm text-muted-foreground">
            Loads &ldquo;{sample.title}&rdquo; — the exact pair from the Compare page — and asks the model to read
            what the rules could not, live, right now.
          </p>
          <Button size="lg" onClick={onRun} disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {busy ? "Reading…" : "Let the model read it"}
          </Button>
          {error && <p className="text-xs text-danger">{error}</p>}
        </div>
      )}
    </div>
  );
}

function ImpactStep({ run }: { run: RunStatus | null }) {
  if (!run?.metrics) {
    return (
      <div className="flex flex-col gap-5">
        <StepHeading title="Impact" text="Run the demo inbox in an earlier step to see this walkthrough's own real numbers here." />
      </div>
    );
  }
  const m = run.metrics;
  const mismatches = m.by_status?.MISMATCH ?? 0;
  const escalated = m.by_status?.NEEDS_REVIEW ?? 0;
  const runHref = `/runs/${run.run_id}`;
  const categoryKeys = Object.keys(CATEGORY_LABELS) as Category[];

  return (
    <div className="flex flex-col gap-5">
      <StepHeading title="Impact" text={`From this walkthrough's own run, ${run.run_id} — nothing here is made up.`} />
      <div className="grid gap-3 sm:grid-cols-3">
        <BigStat label="Emails processed" value={m.emails} accent="primary" href={runHref} />
        <BigStat label="Mismatches caught" value={mismatches} accent="danger" href={`${runHref}?status=MISMATCH`} />
        <BigStat label="Escalated to a person" value={escalated} accent="warn" href={`${runHref}?status=NEEDS_REVIEW`} />
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {categoryKeys.map((key) => (
          <MiniStat key={key} label={CATEGORY_LABELS[key]} value={m.by_category?.[key] ?? 0} href={`${runHref}?category=${key}`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-3 pt-2">
        <Link href={runHref}>
          <Button variant="outline">Open this run</Button>
        </Link>
        <Link href="/">
          <Button variant="outline">Back to Home</Button>
        </Link>
      </div>
    </div>
  );
}
