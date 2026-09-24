"use client";

import { useRef, useState, type ReactNode } from "react";
import { LockKeyhole, Mail, Sparkles, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, polishReplyWording, type CaseReport, type ReplyTone } from "@/lib/api";
import { fetchHealth } from "@/lib/health";
import {
  assembleBody,
  buildReplyDraft,
  canDraftReply,
  formatReplyDraft,
  mailtoHref,
  type DraftParts,
  type ReplyDraft,
} from "@/lib/reply-draft";
import { cn } from "@/lib/utils";

type AiNote = { kind: "adopted" | "refused" | "unavailable"; text: string };

const TONES: { value: ReplyTone; label: string }[] = [
  { value: "formal", label: "Formal" },
  { value: "warm", label: "Warm" },
  { value: "brief", label: "Brief" },
];

/**
 * Callers key this on `replyDraftKey(report)`, so a review, a correction or a
 * re-check remounts it: an open draft never goes on describing the outcome it
 * replaced, and nothing from the old draft's AI state carries over.
 */
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

  // The rules' own parts, kept so the AI wording can always be undone, and
  // so every rewording starts from the template rather than from the last
  // rewrite (which would drift a little further each press).
  const [template, setTemplate] = useState<DraftParts | null>(null);
  const [aiWorded, setAiWorded] = useState(false);
  const [aiNote, setAiNote] = useState<AiNote | null>(null);
  const [tone, setTone] = useState<ReplyTone>("formal");
  const [polishing, setPolishing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // null until GET / answers. The wording pass needs a key on the server;
  // without one the button is not offered and the template is the draft,
  // which is complete on its own (CLAUDE.md rule 5).
  const [modelAvailable, setModelAvailable] = useState<boolean | null>(null);
  // The labelled view is only true while the body is exactly what the parts
  // assemble to. Once someone types in it, the textarea is the draft.
  const [editing, setEditing] = useState(false);
  const [editedByHand, setEditedByHand] = useState(false);
  // Bumped by anything that makes an in-flight rewording stale (Hide, a new
  // draft, Back to template), so its answer is dropped instead of reopening
  // the panel or overwriting what is on screen now.
  const generation = useRef(0);

  if (!canDraftReply(report)) return null;

  if (draft === null) {
    return (
      <Button
        size="sm"
        onClick={() => {
          generation.current += 1;
          const d = buildReplyDraft(report);
          setDraft(d);
          setTemplate(d.parts ?? null);
          setTo(report.sender);
          setAiWorded(false);
          setAiNote(null);
          setPolishing(false);
          setEditing(false);
          setEditedByHand(false);
          fetchHealth()
            .then((h) => setModelAvailable(h.model_available === true))
            .catch(() => setModelAvailable(false));
        }}
      >
        <Mail className="size-4" />
        Draft reply to counterparty
      </Button>
    );
  }

  const href = mailtoHref(to, draft);
  const parts = draft.parts;
  const stays = aiWorded ? "The previous wording stays." : "The template wording stands.";

  async function reword() {
    if (!template) return;
    const mine = ++generation.current;
    setPolishing(true);
    setAiNote(null);
    setAttempt((n) => n + 1);
    try {
      const r = await polishReplyWording({
        situation: template.situation,
        tone,
        greeting: template.greeting,
        closing: template.closing,
        attempt: Math.min(attempt, 20),
      });
      if (mine !== generation.current) return;
      if (r.adopted) {
        setDraft((cur) => {
          if (!cur?.parts) return cur;
          const next = { ...cur.parts, greeting: r.greeting, closing: r.closing };
          return { ...cur, parts: next, body: assembleBody(next) };
        });
        setAiWorded(true);
        setAiNote({
          kind: "adopted",
          text: "The AI reworded the greeting and the closing. Everything between them is unchanged.",
        });
      } else {
        setAiNote({
          kind: "refused",
          text: `The AI's wording was not used: ${r.rejected_reason ?? "it read as a value or a claim"}. ${stays}`,
        });
      }
    } catch (e) {
      if (mine !== generation.current) return;
      setAiNote({
        kind: "unavailable",
        text:
          e instanceof ApiError && e.status === 503
            ? `No model is available on this server right now. ${stays}`
            : `The AI could not be reached (${e instanceof Error ? e.message : String(e)}). ${stays}`,
      });
    } finally {
      if (mine === generation.current) setPolishing(false);
    }
  }

  function undoAi() {
    if (!template) return;
    generation.current += 1;
    setDraft((cur) => (cur ? { ...cur, parts: template, body: assembleBody(template) } : cur));
    setAiWorded(false);
    setAiNote(null);
    setPolishing(false);
  }

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
          disabled={polishing}
          onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
          className="w-full rounded-md border bg-background px-2 py-1 text-sm disabled:opacity-60"
        />
      </label>

      {parts && !editing && !editedByHand ? (
        <StructuredBody parts={parts} aiWorded={aiWorded} />
      ) : (
        <Textarea
          value={draft.body}
          disabled={polishing}
          onChange={(e) => {
            setDraft({ ...draft, body: e.target.value });
            setEditedByHand(true);
          }}
          rows={12}
          className="font-mono text-xs"
        />
      )}

      {/* The one place a model touches this draft, and only its courtesy.
          Offered while the draft is still the rules' own structure: after a
          hand edit there is no telling which text is a fact any more. */}
      {parts && template && !editedByHand && modelAvailable && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed px-2 py-1.5">
          <Sparkles className="size-4 text-primary" strokeWidth={1.75} />
          <span className="text-xs text-muted-foreground">Wording by AI</span>
          <select
            value={tone}
            disabled={polishing}
            onChange={(e) => setTone(e.target.value as ReplyTone)}
            className="rounded-md border bg-background px-1.5 py-0.5 text-xs"
            aria-label="Tone"
          >
            {TONES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <Button size="sm" variant="outline" onClick={reword} disabled={polishing || attempt > 20}>
            <Sparkles className={cn("size-4", polishing && "animate-pulse")} />
            {polishing ? "Rewording…" : aiWorded ? "Reword again" : "Reword with AI"}
          </Button>
          {aiWorded && (
            <Button size="sm" variant="ghost" onClick={undoAi} disabled={polishing}>
              <Undo2 className="size-4" />
              Back to template
            </Button>
          )}
        </div>
      )}
      {aiNote && (
        <p className={cn("text-xs", aiNote.kind === "adopted" ? "text-muted-foreground" : "text-warn")}>
          {aiNote.text}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {/* Opens the operator's own mail client with To/Subject/Body already
            filled in. Sentinel never transmits this itself -- the send
            click happens in their own already-authenticated mail app, same
            "draft, never auto-send" rule the Confirm/Correct panel above
            already holds to. */}
        {href && (
          <a href={href}>
            <Button size="sm" disabled={polishing}>
              <Mail className="size-4" />
              Email this
            </Button>
          </a>
        )}
        <Button
          size="sm"
          variant="outline"
          disabled={polishing}
          onClick={async () => {
            await navigator.clipboard.writeText(formatReplyDraft(draft));
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </Button>
        {parts && !editedByHand && (
          <Button size="sm" variant="outline" disabled={polishing} onClick={() => setEditing(!editing)}>
            {editing ? "Show labelled view" : "Edit text"}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            generation.current += 1;
            setPolishing(false);
            setDraft(null);
          }}
        >
          Hide
        </Button>
      </div>
    </div>
  );
}

/**
 * The draft as its parts, each labelled with where it came from. This is the
 * whole design on one screen: what the rules wrote from the documents carries
 * a lock, and the only text a model can have written is tinted and says so.
 */
function StructuredBody({ parts, aiWorded }: { parts: DraftParts; aiWorded: boolean }) {
  const wording = aiWorded ? "wording · AI" : "wording · template";
  return (
    <div className="flex flex-col gap-1.5 rounded-md border bg-background p-2.5 font-mono text-xs leading-relaxed">
      <p>Hello,</p>
      <Part tag={wording} ai={aiWorded}>
        {parts.greeting}
      </Part>
      <Part tag="what happened · locked" locked>
        {parts.context}
      </Part>
      {parts.facts.length > 0 && (
        <Part tag="from the documents · locked" locked>
          {parts.facts.join("\n")}
        </Part>
      )}
      {parts.action && (
        <Part tag="request · locked" locked>
          {parts.action}
        </Part>
      )}
      {parts.closing && (
        <Part tag={wording} ai={aiWorded}>
          {parts.closing}
        </Part>
      )}
      <p>Regards,</p>
    </div>
  );
}

function Part({ tag, ai, locked, children }: { tag: string; ai?: boolean; locked?: boolean; children: ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-sm border-l-2 py-1 pr-2 pl-2.5",
        ai ? "border-primary bg-primary/5" : locked ? "border-muted-foreground/40 bg-muted/40" : "border-border",
      )}
    >
      <div className="mb-0.5 flex items-center gap-1 font-sans text-[10px] tracking-wide text-muted-foreground uppercase">
        {locked && <LockKeyhole className="size-3" strokeWidth={2} />}
        {ai && <Sparkles className="size-3 text-primary" strokeWidth={2} />}
        {tag}
      </div>
      <div className="whitespace-pre-wrap">{children}</div>
    </div>
  );
}
