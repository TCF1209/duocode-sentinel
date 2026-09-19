"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createRun, listRuns, type RunStatus } from "@/lib/api";
import { toast } from "sonner";

export default function HomePage() {
  const [runs, setRuns] = useState<RunStatus[] | null>(null);
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(() => {
    listRuns()
      .then(setRuns)
      .catch((e) => toast.error(`Could not load runs: ${e.message}`));
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  async function start() {
    setStarting(true);
    try {
      const { run_id } = await createRun({ use_llm: false });
      toast.success(`Started ${run_id}`);
      refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
          <p className="text-sm text-muted-foreground">
            Sentinel processes the bundled demo inbox (<code>SENTINEL_DATA_ROOT</code> on the API) email by email.
          </p>
        </div>
        <Button onClick={start} disabled={starting}>
          {starting ? "Starting…" : "Start a run"}
        </Button>
      </div>

      {runs === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : runs.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No runs yet. Start one, or try{" "}
            <Link href="/compare" className="underline">
              the upload demo
            </Link>{" "}
            with your own documents.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {runs.map((r) => (
            <Link key={r.run_id} href={`/runs/${r.run_id}`}>
              <Card className="transition-colors hover:bg-muted/40">
                <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="font-mono text-sm">{r.run_id}</CardTitle>
                  <RunStatusPill status={r.status} />
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {r.processed} / {r.total_emails} emails
                  {r.llm_enabled ? " · model fallback on" : " · rules only"}
                  {r.error && <span className="ml-2 text-red-600">{r.error}</span>}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function RunStatusPill({ status }: { status: RunStatus["status"] }) {
  if (status === "running") return <Badge className="border-0 bg-amber-100 text-amber-900">running…</Badge>;
  if (status === "failed") return <Badge className="border-0 bg-red-100 text-red-800">failed</Badge>;
  return <Badge className="border-0 bg-emerald-100 text-emerald-800">done</Badge>;
}
