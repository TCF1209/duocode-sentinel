"use client";

import { useId, useState } from "react";
import { FileCheck2, Loader2, Upload, X } from "lucide-react";
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
export default function ComparePage() {
  const [si, setSi] = useState<File | null>(null);
  const [bl, setBl] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<CaseReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!si || !bl) return;
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(await compareUploads(si, bl));
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

      <motion.div variants={fadeUp}>
        <Card>
          <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-end">
            <FilePicker label="Shipping Instruction (SI)" file={si} onChange={setSi} />
            <FilePicker label="Draft Bill of Lading (BL)" file={bl} onChange={setBl} />
            <motion.div whileTap={!busy ? TAP : undefined} transition={TAP_TRANSITION} className="inline-block">
              <Button onClick={submit} disabled={!si || !bl || busy}>
                {busy && <Loader2 className="size-4 animate-spin" />}
                {busy ? "Comparing…" : "Compare"}
              </Button>
            </motion.div>
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
