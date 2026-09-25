"use client";

import { Suspense, useEffect, useId, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, FileCheck2, Loader2, Play, ScanLine, Sparkles, Upload, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CaseReportView } from "@/components/case-report-view";
import { ApiError, compareUploads, type CaseReport } from "@/lib/api";
import { fadeUp, stagger, TAP, TAP_TRANSITION } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * docs/ROADMAP.md 3d: "the upload path is the demo, not a feature" — a judge
 * drops in their own SI and BL and watches the system work, live, on a
 * document it has never seen. No run, no stored case: just this one request.
 *
 * Rebuilt after the mentor session of 24 Sep, whose two points about this
 * page were one point: "too much text" and "not clear what to do" are the
 * same thing when a page explains in sentences what a first click would have
 * shown. So the page now shows instead of telling. The three sample pairs
 * are the first thing on it and are plainly buttons; the three steps are a
 * stepper that lights up as the visitor gets through them rather than three
 * sentences; the model switch keeps one line and folds its reasoning away;
 * and once a result is on screen the page itself proposes the next step —
 * "flip the switch and compare again" — as a button, which is the whole
 * argument of this page made into a click. Before a result there are four
 * short lines of prose on the page where there were fifteen sentences.
 */

/**
 * Three pairs a judge can load without preparing anything. They exist to make
 * the rule/model split visible rather than described: run each one with the
 * model off, then on, and watch which stage was actually doing the work. The
 * `blurb` is shown *after* a result — it explains what was just seen, which
 * is when a reader wants it; before, it was a wall of text over three cards.
 */
const SAMPLES = [
  {
    id: "ordinary",
    title: "Ordinary wording",
    tagline: "the rules alone answer it",
    blurb:
      "Labelled the way our table expects — the rules answer it; the whole graded inbox is like this.",
    si: "ordinary_SI.txt",
    bl: "ordinary_BL.txt",
    needsModel: false,
  },
  {
    id: "unfamiliar-labels",
    title: "Labels we have never seen",
    tagline: "rules escalate; the model reads it",
    blurb:
      "Labels our table has never seen — rules escalate, the model reads them, the real defect surfaces.",
    si: "unfamiliar-labels_SI.txt",
    bl: "unfamiliar-labels_BL.txt",
    needsModel: true,
  },
  {
    id: "scanned",
    title: "A scan with no text layer",
    tagline: "the vision path reads it out",
    blurb:
      "Image-only PDFs — the model transcribes both for the reviewer; the case still goes to a person.",
    si: "scanned_SI.pdf",
    bl: "scanned_BL.pdf",
    needsModel: true,
  },
] as const;

type Sample = (typeof SAMPLES)[number];

async function fetchSample(name: string): Promise<File> {
  const res = await fetch(`/samples/${name}`);
  if (!res.ok) throw new Error(`could not load sample ${name}`);
  return new File([await res.blob()], name);
}

/**
 * `?sample=<id>` arrives with that pair already loaded: the home page's
 * "Scans read out" tile sends a visitor here when no scan in the latest run
 * was read out. A pair that needs the model switches it on as well; pressing
 * Compare stays the visitor's move, as it is for every sample. Its own
 * component inside <Suspense> so the rest of the page still prerenders
 * (next/dist/docs/01-app/03-api-reference/04-functions/use-search-params.md).
 */
function SampleFromUrl({ onSample }: { onSample: (s: Sample) => void }) {
  const id = useSearchParams().get("sample");
  const loaded = useRef<string | null>(null);
  useEffect(() => {
    const s = SAMPLES.find((x) => x.id === id);
    if (!s || loaded.current === s.id) return;
    loaded.current = s.id;
    onSample(s);
  }, [id, onSample]);
  return null;
}

export default function ComparePage() {
  const [si, setSi] = useState<File | null>(null);
  const [bl, setBl] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [useLlm, setUseLlm] = useState(false);
  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  // Which sample pair is loaded, if any -- the page's own suggestions after
  // a result ("flip the switch and compare again") only make sense for a
  // pair it knows. Cleared the moment a visitor picks a file of their own.
  const [loadedSample, setLoadedSample] = useState<Sample | null>(null);
  const [report, setReport] = useState<CaseReport | null>(null);
  // The switch position the current report was produced with, and which
  // positions this pair has been run with so far -- what the stepper's
  // third step and the post-result nudge are keyed on.
  const [reportLlm, setReportLlm] = useState<boolean | null>(null);
  const [ranWith, setRanWith] = useState<{ off: boolean; on: boolean }>({ off: false, on: false });
  const [error, setError] = useState<string | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  // The light round the sample buttons (globals.css .attention-beam) is a
  // function of page state and nothing else -- no timer, no "first visit",
  // no listening for the visitor's first move; all three of those were
  // tried and each left a state with no cue in it (a second visit, a stray
  // scroll). Nothing loaded: every sample beams. A sample loaded: that one
  // beams, marking the pair the result came from. The visitor's own file
  // on either side: none, so the cue never competes with their upload.
  const nothingLoaded = !si && !bl;

  // The result is below the fold on every screen once the samples and the
  // upload card are above it; a visitor who pressed Compare should not have
  // to go looking for what it produced.
  useEffect(() => {
    if (report) reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [report]);

  function resetForNewPair() {
    setReport(null);
    setReportLlm(null);
    setRanWith({ off: false, on: false });
    setError(null);
  }

  // Picking a sample loads the pair; pressing Compare compares it. Running
  // on the click was tried and taken out on purpose: on stage, the press on
  // Compare is the moment the audience knows what is being compared.
  async function loadSample(s: Sample) {
    setLoadingSample(s.id);
    resetForNewPair();
    try {
      const [a, b] = await Promise.all([fetchSample(s.si), fetchSample(s.bl)]);
      setSi(a);
      setBl(b);
      setLoadedSample(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSample(null);
    }
  }

  function loadSampleFromUrl(s: Sample) {
    if (s.needsModel) setUseLlm(true);
    loadSample(s);
  }

  function pickOwn(side: "si" | "bl", f: File | null) {
    (side === "si" ? setSi : setBl)(f);
    setLoadedSample(null);
    resetForNewPair();
  }

  // `withLlm` is passed in rather than read from state so the post-result
  // button can flip the switch and run in the same click; `files` likewise,
  // so a sample can run the moment it has loaded, before state has caught up.
  async function run(withLlm: boolean, files?: { si: File; bl: File }) {
    const pair = files ?? (si && bl ? { si, bl } : null);
    if (!pair) return;
    setUseLlm(withLlm);
    setBusy(true);
    setError(null);
    try {
      const next = await compareUploads(pair.si, pair.bl, withLlm);
      setReport(next);
      setReportLlm(withLlm);
      setRanWith((prev) => ({ ...prev, [withLlm ? "on" : "off"]: true }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const havePair = Boolean(si && bl);
  const steps = [
    { label: "Pick a pair", done: havePair },
    { label: "Compare", done: report !== null },
    { label: "Flip the model switch, compare again", done: ranWith.off && ranWith.on },
  ];

  return (
    <motion.div className="flex flex-col gap-6" initial="hidden" animate="show" variants={stagger()}>
      <Suspense fallback={null}>
        <SampleFromUrl onSample={loadSampleFromUrl} />
      </Suspense>
      <motion.div variants={fadeUp} className="flex flex-col gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight">Compare two documents</h1>
          <p className="text-sm text-muted-foreground">
            One SI against one BL, the same check as the inbox. Nothing is stored.
          </p>
        </div>
        <Stepper steps={steps} />
      </motion.div>

      {/* The samples lead. A first-time visitor's first click should be
          here, so this is the first thing on the page and each one is
          unmistakably a button: a play glyph, a title, six words on what it
          shows, and a "Loaded" mark once it is the pair in the card below. */}
      <motion.section variants={fadeUp} className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Try a pair</h2>
          <span className="text-xs text-muted-foreground">Pick one, then press Compare.</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {SAMPLES.map((s, i) => {
            const isLoaded = loadedSample?.id === s.id;
            const isLoading = loadingSample === s.id;
            return (
              <div key={s.id} className="relative">
                {/* The beam rule is `nothingLoaded` above. The three are
                    offset by a third of a turn each so they don't move in
                    lockstep. */}
                <motion.button
                  type="button"
                  whileTap={TAP}
                  transition={TAP_TRANSITION}
                  onClick={() => loadSample(s)}
                  disabled={loadingSample !== null || busy}
                  aria-pressed={isLoaded}
                  style={{ "--beam-delay": `${-i * 0.8}s` } as React.CSSProperties}
                  className={cn(
                    "relative flex w-full items-center gap-3 rounded-lg border bg-card p-3 text-left shadow-sm transition-all",
                    "hover:-translate-y-0.5 hover:border-primary hover:shadow-md disabled:cursor-default disabled:opacity-60",
                    isLoaded ? "border-primary bg-primary/5" : "border-primary/30",
                    (nothingLoaded || isLoaded) && "attention-beam",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-9 shrink-0 items-center justify-center rounded-full",
                      isLoaded ? "bg-primary text-primary-foreground" : "bg-primary/10 text-primary",
                    )}
                  >
                    {isLoading ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : isLoaded ? (
                      <Check className="size-4" strokeWidth={2.5} />
                    ) : s.id === "scanned" ? (
                      <ScanLine className="size-4" />
                    ) : (
                      <Play className="size-4" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold">{s.title}</span>
                    <span className="block text-xs text-muted-foreground">{s.tagline}</span>
                  </span>
                  {isLoaded && <span className="text-xs font-medium text-primary">Loaded</span>}
                </motion.button>
              </div>
            );
          })}
        </div>
      </motion.section>

      <motion.div variants={fadeUp}>
        <Card>
          <CardContent className="flex flex-col gap-4 p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {loadedSample ? `Loaded: ${loadedSample.title}` : "Or upload your own"}
              </h2>
              {!havePair && <span className="text-xs text-muted-foreground">Pick a pair above, or drop both files here.</span>}
            </div>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              <FilePicker label="Shipping Instruction (SI)" file={si} onChange={(f) => pickOwn("si", f)} />
              <FilePicker label="Draft Bill of Lading (BL)" file={bl} onChange={(f) => pickOwn("bl", f)} />
              <motion.div whileTap={!busy ? TAP : undefined} transition={TAP_TRANSITION} className="inline-block">
                <Button onClick={() => run(useLlm)} disabled={!havePair || busy}>
                  {busy && <Loader2 className="size-4 animate-spin" />}
                  {busy ? "Comparing…" : "Compare"}
                </Button>
              </motion.div>
            </div>

            {/* The toggle is the point of this page, not a setting. One
                line, with its reasoning a click away rather than four
                sentences in the visitor's path. */}
            <div className="rounded-md border border-dashed p-3">
              <label className="flex cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  checked={useLlm}
                  onChange={(e) => setUseLlm(e.target.checked)}
                  className="size-4 accent-primary"
                />
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <Sparkles className="size-3.5 text-primary" />
                  Let the model read what the rules could not
                </span>
                <span className="ml-auto text-xs text-muted-foreground">{useLlm ? "on" : "off"}</span>
              </label>
              <details className="mt-1.5 text-xs text-muted-foreground">
                <summary className="cursor-pointer select-none">Why off by default?</summary>
                <p className="mt-1">
                  Off, the rules answer all 520 graded emails on their own. On, the model is asked only about
                  fields no rule could resolve, and every answer is re-located in the document before it is
                  accepted.
                </p>
              </details>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      <AnimatePresence mode="popLayout" initial={false}>
        {error && (
          <motion.div
            key="error"
            layout
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-md border border-danger/30 bg-danger-bg p-3 text-sm text-danger"
          >
            {error}
          </motion.div>
        )}

        {report && (
          <motion.div
            key="report"
            ref={reportRef}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex scroll-mt-24 flex-col gap-3"
          >
            {loadedSample && reportLlm !== null && (
              <NextStep sample={loadedSample} reportLlm={reportLlm} ranWith={ranWith} busy={busy} onRun={run} />
            )}
            <Card>
              <CardContent className="p-6">
                <CaseReportView report={report} />
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/** The page's own suggestion for what to do next, on a pair it knows: the
 *  "run it twice" argument as a button instead of an instruction. Also
 *  carries the sample's explanation, now that there is a result to explain. */
function NextStep({
  sample,
  reportLlm,
  ranWith,
  busy,
  onRun,
}: {
  sample: Sample;
  reportLlm: boolean;
  ranWith: { off: boolean; on: boolean };
  busy: boolean;
  onRun: (withLlm: boolean) => void;
}) {
  const bothDone = ranWith.off && ranWith.on;
  let headline: string;
  let action: { label: string; withLlm: boolean } | null = null;
  if (bothDone) {
    headline = "You have now seen this pair both ways.";
  } else if (sample.needsModel && !reportLlm) {
    headline = "Rules alone sent this pair to a person. Now let the model try.";
    action = { label: "Flip the switch and compare again", withLlm: true };
  } else if (sample.needsModel && reportLlm) {
    headline = "That was with the model. See what the rules alone make of it.";
    action = { label: "Compare with the model off", withLlm: false };
  } else if (!reportLlm) {
    headline = "The rules answered it; no model needed — like the whole graded inbox.";
    action = { label: "Run it with the model on anyway", withLlm: true };
  } else {
    headline = "Same answer with the model on: nothing needed it.";
    action = { label: "Compare with the model off", withLlm: false };
  }
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-primary/30 bg-primary/5 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm font-medium">{headline}</p>
        {action && (
          <motion.div whileTap={!busy ? TAP : undefined} transition={TAP_TRANSITION} className="inline-block">
            <Button size="sm" onClick={() => onRun(action.withLlm)} disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {action.label}
            </Button>
          </motion.div>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground">What you just saw · </span>
        {sample.blurb}
      </p>
    </div>
  );
}

/** Three steps that light up as the visitor gets through them. State, not
 *  prose: the same guidance the old three-sentence strip gave, in twelve
 *  words, and it answers "where am I" as well as "what do I do". */
function Stepper({ steps }: { steps: { label: string; done: boolean }[] }) {
  const currentIndex = steps.findIndex((s) => !s.done);
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-sm" aria-label="Steps">
      {steps.map((s, i) => {
        const state = s.done ? "done" : i === currentIndex ? "current" : "upcoming";
        return (
          <li key={s.label} className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                state === "done" && "bg-primary text-primary-foreground",
                state === "current" && "border-2 border-primary text-primary",
                state === "upcoming" && "border text-muted-foreground",
              )}
              aria-current={state === "current" ? "step" : undefined}
            >
              {state === "done" ? <Check className="size-3" strokeWidth={3} /> : i + 1}
            </span>
            <span className={cn(state === "upcoming" ? "text-muted-foreground" : "font-medium")}>{s.label}</span>
            {i < steps.length - 1 && <span className="text-muted-foreground/50">→</span>}
          </li>
        );
      })}
    </ol>
  );
}

function FilePicker({
  label,
  file,
  onChange,
}: {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
}) {
  const inputId = useId();
  const [dragOver, setDragOver] = useState(false);

  return (
    <div className="flex flex-1 flex-col gap-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) onChange(dropped);
        }}
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-md border border-dashed p-3 transition-colors",
          dragOver ? "border-primary bg-primary/5" : "hover:border-primary/40 hover:bg-muted/40",
        )}
      >
        <input
          id={inputId}
          type="file"
          accept=".txt,.pdf,.docx,.xlsx,.csv"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
          className="sr-only"
        />
        {file ? (
          <FileCheck2 className="size-4 shrink-0 text-ok" />
        ) : (
          <Upload className="size-4 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          {file ? (
            <>
              <div className="truncate text-xs font-medium text-foreground">{file.name}</div>
              <div className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB · click to replace</div>
            </>
          ) : (
            <div className="text-xs text-muted-foreground">Click to browse, or drag a file here</div>
          )}
        </div>
        {file && (
          <motion.button
            type="button"
            whileTap={TAP}
            transition={TAP_TRANSITION}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onChange(null);
            }}
            aria-label={`Remove ${file.name}`}
            className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-danger"
          >
            <X className="size-3.5" />
          </motion.button>
        )}
      </label>
    </div>
  );
}
