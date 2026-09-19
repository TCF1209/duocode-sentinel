"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CaseReportView } from "@/components/case-report-view";
import { ApiError, compareUploads, type CaseReport } from "@/lib/api";

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
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Compare your own documents</h1>
        <p className="text-sm text-muted-foreground">
          Upload a Shipping Instruction and a draft Bill of Lading. This runs the same reader, extraction,
          comparison and evidence-gate stages as the graded inbox — nothing is replayed from a stored answer.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-end">
          <FilePicker label="Shipping Instruction (SI)" file={si} onChange={setSi} />
          <FilePicker label="Draft Bill of Lading (BL)" file={bl} onChange={setBl} />
          <Button onClick={submit} disabled={!si || !bl || busy}>
            {busy ? "Comparing…" : "Compare"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      {report && (
        <Card>
          <CardContent className="p-6">
            <CaseReportView report={report} />
          </CardContent>
        </Card>
      )}
    </div>
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
  return (
    <label className="flex flex-1 flex-col gap-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <input
        type="file"
        accept=".txt,.pdf,.docx,.xlsx,.csv"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        className="rounded-md border p-2 text-sm file:mr-2 file:rounded file:border-0 file:bg-muted file:px-2 file:py-1"
      />
      {file && <span className="text-xs text-muted-foreground">{file.name}</span>}
    </label>
  );
}
