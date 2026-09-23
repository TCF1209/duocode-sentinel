"use client";

import { useState } from "react";
import { Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { CaseReport } from "@/lib/api";
import { buildReplyDraft, formatReplyDraft, mailtoHref, type ReplyDraft } from "@/lib/reply-draft";

export function ReplyDraftPanel({ report }: { report: CaseReport }) {
  const [draft, setDraft] = useState<ReplyDraft | null>(null);
  // Separate from `report.sender`, and always editable: the extracted "from"
  // address is a strong default, not a guarantee it is the right person on
  // a real forwarded thread (email_031's own body has three different
  // signatures on it) -- the operator gets the last word on who this
  // actually goes to, same as everything else this panel drafts rather
  // than decides.
  const [to, setTo] = useState("");
  const [copied, setCopied] = useState(false);

  if (draft === null) {
    return (
      <Button
        size="sm"
        onClick={() => {
          setDraft(buildReplyDraft(report));
          setTo(report.sender);
        }}
      >
        <Mail className="size-4" />
        Draft reply to counterparty
      </Button>
    );
  }

  const href = mailtoHref(to, draft);

  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-card p-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="w-16 shrink-0 text-muted-foreground">To</span>
        <input
          type="email"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder={report.sender ? undefined : "No sender on this case — enter an address to enable Email this"}
          className="w-full rounded-md border bg-background px-2 py-1 text-sm"
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <span className="w-16 shrink-0 text-muted-foreground">Subject</span>
        <input
          type="text"
          value={draft.subject}
          onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
          className="w-full rounded-md border bg-background px-2 py-1 text-sm"
        />
      </label>
      <Textarea
        value={draft.body}
        onChange={(e) => setDraft({ ...draft, body: e.target.value })}
        rows={9}
        className="font-mono text-xs"
      />
      <div className="flex flex-wrap gap-2">
        {/* Opens the operator's own mail client with To/Subject/Body already
            filled in. Sentinel never transmits this itself -- the send
            click happens in their own already-authenticated mail app, same
            "draft, never auto-send" rule the Confirm/Correct panel above
            already holds to. */}
        {href && (
          <a href={href}>
            <Button size="sm">
              <Mail className="size-4" />
              Email this
            </Button>
          </a>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={async () => {
            await navigator.clipboard.writeText(formatReplyDraft(draft));
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
