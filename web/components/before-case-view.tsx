"use client";

import { Fragment, useEffect, useState } from "react";
import { motion } from "motion/react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { attachmentUrl, type CaseReport, type DocSide } from "@/lib/api";
import { FIELD_LABELS } from "@/lib/labels";
import { useViewMode } from "@/lib/view-mode";
import { fadeUp, stagger } from "@/lib/motion";
import { tidyDocument } from "@/lib/tidy-document";
import { cn } from "@/lib/utils";

/**
 * The case page with Sentinel taken away: the email as it arrived, the two
 * documents as files, and the seven fields a person would have to read out
 * of each and set side by side -- blank, because nobody has done it yet.
 * The "Before Sentinel" half of the switch (lib/view-mode.ts) for one case,
 * the way run-page-view.tsx's Before state is for the inbox. Read-only on
 * purpose: it shows the work, it does not ask a judge to do it.
 */

const SIDE_TITLE: Record<DocSide, string> = { si: "Shipping Instruction (SI)", bl: "Draft Bill of Lading (BL)" };

/** How a text document is shown: its lines re-set into two columns
 *  (lib/tidy-document.ts), or the file exactly as it arrived. */
type DocView = "tidy" | "raw";

/** One line for both states -- what each view is, nothing about how. */
const DOC_VIEW_TEXT = "Tidy: the same lines, in two columns. Raw: the file as it arrived.";

function DocumentPane({ caseId, side, report, view }: { caseId: string; side: DocSide; report: CaseReport; view: DocView }) {
  const doc = report.documents[side];
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isText = doc?.ext === ".txt";
  const isPdf = doc?.ext === ".pdf";

  useEffect(() => {
    if (!doc || !isText) return;
    let alive = true;
    fetch(attachmentUrl(caseId, side))
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then((t) => alive && setText(t))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [caseId, side, doc, isText]);

  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-lg border bg-card p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{SIDE_TITLE[side]}</span>
        {doc && <span className="truncate font-mono text-[11px] text-muted-foreground">{doc.path.split("/").pop()}</span>}
      </div>
      {!doc ? (
        <p className="text-sm text-muted-foreground">Not attached to this email.</p>
      ) : isText ? (
        <div className="max-h-80 overflow-auto rounded-md border bg-muted/30 p-3">
          {error && <p className="text-sm text-danger">Could not load the file: {error}</p>}
          {text === null && !error && <p className="text-sm text-muted-foreground">Loading…</p>}
          {text !== null && view === "raw" && <pre className="whitespace-pre-wrap font-mono text-xs">{text}</pre>}
          {/* Two columns from md up. Below that the pane is too narrow for
              a label column beside a value column -- a long label ("Consignee
              (Non-Negotiable)") took the width and the value broke letter by
              letter -- so the label sits above its value instead. */}
          {text !== null && view === "tidy" && (
            <div className="grid grid-cols-1 gap-y-1 text-sm md:grid-cols-[minmax(6rem,8rem)_minmax(0,1fr)] md:gap-x-3">
              {tidyDocument(text).map((l, i) =>
                l.kind === "field" ? (
                  <Fragment key={i}>
                    <div className="break-words text-xs text-muted-foreground md:pt-0.5">{l.label}</div>
                    <div className="mb-1 whitespace-pre-line break-words font-medium leading-snug md:mb-0">{l.value}</div>
                  </Fragment>
                ) : l.kind === "heading" ? (
                  <div
                    key={i}
                    className="pt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground first:pt-0 md:col-span-2"
                  >
                    {l.text}
                  </div>
                ) : (
                  <pre key={i} className="whitespace-pre-wrap font-mono text-xs md:col-span-2">
                    {l.text}
                  </pre>
                ),
              )}
            </div>
          )}
        </div>
      ) : isPdf ? (
        <>
          <iframe src={attachmentUrl(caseId, side)} title={doc.path} className="h-80 w-full rounded-md border bg-white" />
          {/* The line the tidy view exists to set up: this one cannot be
              tidied, and it is what arrives. */}
          {view === "tidy" && <p className="text-xs text-muted-foreground">A scan — nothing to tidy.</p>}
        </>
      ) : (
        <a href={attachmentUrl(caseId, side)} download className="text-sm text-primary hover:underline">
          Open the file ({doc.ext})
        </a>
      )}
    </div>
  );
}

export function BeforeCaseView({ report, caseId }: { report: CaseReport; caseId: string }) {
  const [, setMode] = useViewMode();
  // Tidy first: the person's own reading copy, lined up -- and then the
  // question the pitch asks on this screen: is what the shipper sends ever
  // this tidy? Raw, one click away, is the answer.
  const [view, setView] = useState<DocView>("tidy");
  const fields = Object.keys(FIELD_LABELS);
  return (
    <motion.div className="flex flex-col gap-4" initial="hidden" animate="show" variants={stagger()}>
      <motion.div className="flex flex-col gap-1" variants={fadeUp}>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-mono text-lg font-semibold">{report.email_id}</h2>
          <span className="text-xs text-muted-foreground">as it arrived</span>
        </div>
        {report.inbox?.subject && <div className="text-sm font-medium">{report.inbox.subject}</div>}
        <div className="text-xs text-muted-foreground">
          {report.sender || "unknown sender"}
          {report.inbox && report.inbox.attachments.length > 0 && (
            <>
              {" · "}
              {report.inbox.attachments.length} attachment{report.inbox.attachments.length === 1 ? "" : "s"}:{" "}
              <span className="font-mono">{report.inbox.attachments.join(", ")}</span>
            </>
          )}
        </div>
      </motion.div>

      <motion.div className="flex flex-col gap-2" variants={fadeUp}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">The two documents, as attached</span>
          <div className="flex items-center rounded-full border p-0.5 text-xs" role="group" aria-label="How to show the documents">
            {(["tidy", "raw"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                aria-pressed={view === v}
                className={cn(
                  "rounded-full px-2.5 py-0.5 transition-colors",
                  view === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {v === "tidy" ? "Tidy" : "Raw"}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <DocumentPane caseId={caseId} side="si" report={report} view={view} />
          <DocumentPane caseId={caseId} side="bl" report={report} view={view} />
        </div>
        <p className="text-xs text-muted-foreground">{DOC_VIEW_TEXT}</p>
      </motion.div>

      {/* The seven fields, blank: this is the table a person fills in by
          reading both documents above, for every pair, before anything can
          be said about the shipment. */}
      <motion.div className="flex flex-col gap-2 rounded-lg border bg-card p-3" variants={fadeUp}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {fields.length} fields to read out and compare, by hand
          </span>
          <span className="text-xs text-muted-foreground">Sentinel took {report.duration_ms} ms on this pair.</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="py-1.5 pr-3">Field</th>
                <th className="py-1.5 pr-3">On the SI</th>
                <th className="py-1.5 pr-3">On the BL</th>
                <th className="py-1.5">Same?</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f} className="border-b last:border-0">
                  <td className="py-1.5 pr-3">{FIELD_LABELS[f]}</td>
                  {["si", "bl", "same"].map((col) => (
                    <td key={col} className={col === "same" ? "py-1.5" : "py-1.5 pr-3"}>
                      <span className="block h-6 w-full max-w-48 rounded border border-dashed text-muted-foreground/60" aria-label="blank, to be read by hand" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <p className="text-xs text-muted-foreground">Read both, copy out 7 fields, compare — for every pair in the inbox.</p>
          <Button size="sm" onClick={() => setMode("with")}>
            <Sparkles className="size-4" />
            See what Sentinel read
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
