"use client";

import { useId, useState } from "react";
import { ArrowRight, FileCheck2, Loader2, Sparkles, Upload, X } from "lucide-react";
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
 */
/**
 * Three pairs a judge can load without preparing anything. They exist to make
 * the rule/model split visible rather than described: run each one with the
 * model off, then on, and watch which stage was actually doing the work.
 */
const SAMPLES = [
  {
    id: "unfamiliar-labels",
    title: "Labels we have never seen",
    blurb:
      "A human reads it at a glance — Sender of Goods, Deliver To, Loading Terminal. Our synonym table has none of them. Rules alone find nothing and escalate; the model reads it and the real defect surfaces.",
    si: "unfamiliar-labels_SI.txt",
    bl: "unfamiliar-labels_BL.txt",
    needsModel: true,
  },
  {
    id: "scanned",
    title: "A scan with no text layer",
    blurb:
      "Image-only PDFs. No parser can read them. With the model on, the vision path transcribes both for the reviewer — and the case still escalates, because a transcript is evidence for a person, not grounds for a verdict.",
    si: "scanned_SI.pdf",
    bl: "scanned_BL.pdf",
    needsModel: true,
  },
  {
    id: "ordinary",
    title: "Ordinary wording (the control)",
    blurb:
      "The same shipment, labelled the way our table expects. The rules answer it in milliseconds for nothing. This is the 100% of the graded inbox, and the reason the model is a fallback rather than the engine.",
    si: "ordinary_SI.txt",
    bl: "ordinary_BL.txt",
    needsModel: false,
  },
] as const;

async function fetchSample(name: string): Promise<File> {
  const res = await fetch(`/samples/${name}`);
  if (!res.ok) throw new Error(`could not load sample ${name}`);
  return new File([await res.blob()], name);
}

export default function ComparePage() {
  const [si, setSi] = useState<File | null>(null);
  const [bl, setBl] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [useLlm, setUseLlm] = useState(false);
  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  const [report, setReport] = useState<CaseReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadSample(s: (typeof SAMPLES)[number]) {
    setLoadingSample(s.id);
    setError(null);
    setReport(null);
    try {
      const [a, b] = await Promise.all([fetchSample(s.si), fetchSample(s.bl)]);
      setSi(a);
      setBl(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSample(null);
    }
  }

  async function submit() {
    if (!si || !bl) return;
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(await compareUploads(si, bl, useLlm));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div className="flex flex-col gap-6" initial="hidden" animate="show" variants={stagger()}>
      <motion.div variants={fadeUp}>
        <h1 className="font-heading text-2xl font-semibold tracking-tight">Compare your own documents</h1>
        <p className="text-sm text-muted-foreground">
          Upload a Shipping Instruction and a draft Bill of Lading. This runs the same reader, extraction,
          comparison and evidence-gate stages as the graded inbox — nothing is replayed from a stored answer.
          It&apos;s a one-off check: the result below isn&apos;t saved anywhere, and won&apos;t show up in Runs.
        </p>
      </motion.div>

      {/* "When we land on this page, what do we have to do?" -- the mentor's
          own question on 24 Sep. Three numbered steps answer it before the
          visitor has to work it out from the controls. */}
      <motion.ol variants={fadeUp} className="grid gap-2 sm:grid-cols-3">
        {[
          ["Pick a sample pair below, or upload your own SI and draft BL.", "1"],
          ["Choose whether the model may read what the rules cannot.", "2"],
          ["Press Compare. Then run the same pair with the switch the other way.", "3"],
        ].map(([text, n]) => (
          <li key={n} className="flex items-start gap-2.5 rounded-md border bg-card/60 px-3 py-2 text-sm">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
              {n}
            </span>
            <span>{text}</span>
          </li>
        ))}
      </motion.ol>

      <motion.div variants={fadeUp}>
        <Card>
          <CardContent className="flex flex-col gap-5 p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              <FilePicker label="Shipping Instruction (SI)" file={si} onChange={setSi} />
              <FilePicker label="Draft Bill of Lading (BL)" file={bl} onChange={setBl} />
              <motion.div whileTap={!busy ? TAP : undefined} transition={TAP_TRANSITION} className="inline-block">
                <Button onClick={submit} disabled={!si || !bl || busy}>
                  {busy && <Loader2 className="size-4 animate-spin" />}
                  {busy ? "Comparing…" : "Compare"}
                </Button>
              </motion.div>
            </div>

            {/* The toggle is the point of this page, not a setting. Run a
                sample with it off, then on: the difference is the whole
                argument for where the model sits in this system. */}
            <label className="flex cursor-pointer items-start gap-3 rounded-md border border-dashed p-3 transition-colors hover:bg-muted/40">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                className="mt-0.5 size-4 accent-primary"
              />
              <span className="text-sm">
                <span className="flex items-center gap-1.5 font-medium">
                  <Sparkles className="size-3.5 text-primary" />
                  Let the model read what the rules could not
                </span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  Off by default, and off for all 520 emails of the graded inbox — the rules
                  answer every one of them. Switch it on and the model is asked only about
                  fields no rule could resolve; every answer it gives is re-located in the
                  document before it is accepted, and anything it cannot ground is dropped.
                </span>
              </span>
            </label>
          </CardContent>
        </Card>
      </motion.div>

      <motion.div variants={fadeUp} className="flex flex-col gap-2">
        <p className="text-sm font-medium">
          No documents to hand? Load a sample pair — then run it twice, once with the model off and
          once on.
        </p>
        {/* These read as descriptions, not controls, to a first-time visitor
            (the mentor session of 24 Sep: "I'm not 100% sure it's clickable
            until I click it"). A solid border, a pointer cursor, and an
            explicit "Load this pair" footer with an arrow make the whole card
            an obvious button; the hover lift is the confirmation. */}
        <div className="grid gap-3 sm:grid-cols-3">
          {SAMPLES.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => loadSample(s)}
              disabled={loadingSample !== null}
              className="group flex cursor-pointer flex-col gap-1.5 rounded-lg border border-primary/30 bg-card p-3 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary hover:shadow-md disabled:cursor-default disabled:opacity-60"
            >
              <span className="flex items-center gap-1.5 text-sm font-medium">
                {loadingSample === s.id && <Loader2 className="size-3.5 animate-spin" />}
                {s.title}
              </span>
              <span className="text-xs leading-relaxed text-muted-foreground">{s.blurb}</span>
              {s.needsModel && (
                <span className="mt-0.5 text-[11px] text-primary">needs the model to get past &ldquo;unreadable&rdquo;</span>
              )}
              <span className="mt-auto flex items-center gap-1 pt-2 text-xs font-medium text-primary">
                Load this pair
                <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
              </span>
            </button>
          ))}
        </div>
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
          <motion.div key="report" layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
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
              <div className="truncate font-mono text-xs text-foreground">{file.name}</div>
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
