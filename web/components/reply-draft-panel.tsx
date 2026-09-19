"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { CaseReport } from "@/lib/api";
import { buildReplyDraft } from "@/lib/reply-draft";

export function ReplyDraftPanel({ report }: { report: CaseReport }) {
  const [draft, setDraft] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (draft === null) {
    return (
      <Button variant="outline" size="sm" onClick={() => setDraft(buildReplyDraft(report))}>
        Draft reply to counterparty
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={10} className="font-mono text-xs" />
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={async () => {
            await navigator.clipboard.writeText(draft);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
          Hide
        </Button>
      </div>
    </div>
  );
}
