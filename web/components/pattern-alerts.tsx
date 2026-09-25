"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ChevronDown, ChevronRight, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { fadeUp, stagger } from "@/lib/motion";
import { motion } from "motion/react";
import { FIELD_LABELS } from "@/lib/labels";
import type { CaseSummary } from "@/lib/api";
import { buildPatternDraft, formatReplyDraft, mailtoHref, type ReplyDraft } from "@/lib/reply-draft";
import { getPatternContactedAt, markPatternContacted } from "@/lib/pattern-contact";
import { timeAgo } from "@/lib/format-time";
import { cn } from "@/lib/utils";

/** Below this, one or two stray cases sharing a shipper and a field is not
 *  yet a pattern worth interrupting a triage screen for. */
const MIN_PATTERN_SIZE = 2;
/** Cards, not a scrollable list — a screen with more than this many patterns
 *  needs the batch view backlog item docs/ROADMAP.md already names, not a
 *  longer version of this one. */
const MAX_PATTERNS_SHOWN = 6;

interface Pattern {
  shipper: string;
  field: string;
  emailIds: string[];
  /** Deduplicated, non-empty senders off the cases in this group — a real
   *  forwarded thread can carry more than one signature, so this is
   *  "who actually sent one of these", not a single canonical contact. */
  senders: string[];
}

function groupIntoPatterns(cases: CaseSummary[]): Pattern[] {
  // (shipper, field) -> email ids + senders. A case with two defect fields
  // contributes to two groups, which is correct: "this shipper mismatches
  // on both POD and gross weight" is two separate, separately-actionable
  // patterns, not one that happens to have two field names attached.
  const groups = new Map<string, { shipper: string; field: string; emailIds: string[]; senders: Set<string> }>();
  for (const c of cases) {
    if (!c.shipper || !c.has_defect) continue;
    for (const field of c.defect_fields) {
      const key = `${c.shipper}\u0000${field}`;
      const existing = groups.get(key);
      if (existing) {
        existing.emailIds.push(c.email_id);
        if (c.sender) existing.senders.add(c.sender);
      } else {
        groups.set(key, { shipper: c.shipper, field, emailIds: [c.email_id], senders: new Set(c.sender ? [c.sender] : []) });
      }
    }
  }
  return Array.from(groups.values())
    .filter((g) => g.emailIds.length >= MIN_PATTERN_SIZE)
    .sort((a, b) => b.emailIds.length - a.emailIds.length)
    .slice(0, MAX_PATTERNS_SHOWN)
    .map((g) => ({ ...g, senders: Array.from(g.senders) }));
}

/** "Twelve emails from this shipper all mismatch on port of discharge" is a
 *  different and more valuable statement than twelve separate reports —
 *  docs/ROADMAP.md's own backlog line for this. Reads the case list already
 *  fetched for the table below; no extra request. */
export function PatternAlerts({
  runId,
  cases,
  openRequested = false,
  onOpened,
}: {
  runId: string;
  cases: CaseSummary[];
  /** True when the page was opened *at* this box (/runs/{id}?open=patterns
   *  -- the home page's "Patterns across the inbox" tile): it starts open
   *  and scrolls itself into view once it exists. A query parameter rather
   *  than a hash: the router hands a parameter to the page's first render,
   *  whereas the hash was already gone by the time this component first
   *  rendered (checked live). The run page strips the parameter once it has
   *  been read, so flipping Before/With or coming back from a case does not
   *  open and scroll again. */
  openRequested?: boolean;
  /** Called once the request has been read into this box's state, so the
   *  caller can drop it from the URL. */
  onOpened?: () => void;
}) {
  const patterns = useMemo(() => groupIntoPatterns(cases), [cases]);
  useEffect(() => {
    if (openRequested) onOpened?.();
  }, [openRequested, onOpened]);
  // Collapsed by default, so the case table below is what a reviewer lands
  // on; the heading keeps the count, so a collapsed box still says there is
  // something here, and one click opens it.
  const [collapsed, setCollapsed] = useState(!openRequested);
  // The box is built from a client-side fetch, so it is not there when the
  // page first paints: the scroll waits for the first render that has it.
  const wanted = useRef(openRequested);
  useEffect(() => {
    if (!wanted.current || patterns.length === 0) return;
    wanted.current = false;
    const show = setTimeout(
      () => document.getElementById("patterns")?.scrollIntoView({ behavior: "smooth", block: "start" }),
      250,
    );
    return () => clearTimeout(show);
  }, [patterns.length]);
  if (patterns.length === 0) return null;

  return (
    <motion.div variants={fadeUp}>
      {/* `id` so the home page's "See it live" tile can land here directly
          (/runs/{id}#patterns); scroll-mt clears the sticky nav. */}
      <Card id="patterns" className="scroll-mt-24 border-warn/30">
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              aria-expanded={!collapsed}
              className="flex w-full items-center gap-2 text-left"
            >
              <AlertTriangle className="size-4 text-warn" />
              Patterns worth a second look
              <span className="font-normal text-muted-foreground">({patterns.length})</span>
              <span className="ml-auto flex items-center gap-1 text-xs font-normal text-muted-foreground">
                {collapsed ? "Show" : "Hide"}
                {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
              </span>
            </button>
          </CardTitle>
        </CardHeader>
        {!collapsed && (
          <CardContent>
            <motion.div className="flex flex-col gap-2" initial="hidden" animate="show" variants={stagger()}>
              {patterns.map((p) => (
                <motion.div key={`${p.shipper}\u0000${p.field}`} variants={fadeUp}>
                  <PatternRow runId={runId} pattern={p} />
                </motion.div>
              ))}
            </motion.div>
          </CardContent>
        )}
      </Card>
    </motion.div>
  );
}

function PatternRow({ runId, pattern }: { runId: string; pattern: Pattern }) {
  const [open, setOpen] = useState(false);
  // Read once per mount rather than on every render: nothing outside this
  // component's own "Email this" click (which updates it directly, see
  // onEmailed below) can change it, so there is nothing to re-read for.
  const [contactedAt, setContactedAt] = useState(() => getPatternContactedAt(pattern.shipper, pattern.field));
  const fieldLabel = FIELD_LABELS[pattern.field] ?? pattern.field;

  return (
    <div className="rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 p-3 text-left"
        aria-expanded={open}
      >
        <span className="text-sm">
          <span className="font-medium">{pattern.emailIds.length} cases</span> from{" "}
          <span className="font-medium">{pattern.shipper}</span> with a discrepancy on{" "}
          <span className="font-medium text-warn">{fieldLabel}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {/* Visible on the collapsed row, not just inside the drafting
              panel -- the point is an operator scanning this list at a
              glance can tell "I already followed up here" without opening
              each pattern back up to check. */}
          {contactedAt && <ContactedBadge at={contactedAt} />}
          {open ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-3 border-t p-3">
          <div className="flex flex-wrap gap-2">
            {pattern.emailIds.map((id) => (
              <Link
                key={id}
                href={`/runs/${runId}/cases/${id}`}
                className={cn(
                  "rounded-md border bg-background px-2 py-1 text-xs font-medium text-muted-foreground",
                  "hover:border-primary/40 hover:text-foreground",
                )}
              >
                {id}
              </Link>
            ))}
          </div>
          <PatternDraft pattern={pattern} fieldLabel={fieldLabel} onEmailed={() => setContactedAt(Date.now())} />
        </div>
      )}
    </div>
  );
}

/** "Already followed up," deliberately distinct from the pattern
 *  disappearing: this marks that a message was sent about it, not that the
 *  underlying cases were corrected -- those are different facts (see
 *  lib/pattern-contact.ts), and only a real correction should make a
 *  pattern stop showing here. Ticks its own label every 30s while mounted
 *  so "2 minutes ago" does not go stale sitting on screen; cheap, since at
 *  most MAX_PATTERNS_SHOWN of these exist at once. */
function ContactedBadge({ at }: { at: number }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 30_000);
    return () => clearInterval(id);
  }, []);
  return (
    <span
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-primary/30 bg-primary/5 px-2 py-0.5 text-xs text-primary"
      title="Recorded when a summary email was opened for this pattern in your mail client -- Sentinel hands off to it and has no way to confirm the message was actually sent."
    >
      <Mail className="size-3" />
      Emailed {timeAgo(at)}
    </span>
  );
}

/** One summary email for the whole pattern, not N separate case drafts.
 *  Kept as its own small component rather than reusing ReplyDraftPanel:
 *  the inputs here (a shipper name, several senders, a list of case ids)
 *  are not a CaseReport, and that panel was already verified end to end
 *  earlier tonight -- duplicating the handful of form lines was worth not
 *  reopening it under the same time pressure. */
function PatternDraft({
  pattern,
  fieldLabel,
  onEmailed,
}: {
  pattern: Pattern;
  fieldLabel: string;
  onEmailed: () => void;
}) {
  const [draft, setDraft] = useState<ReplyDraft | null>(null);
  const [to, setTo] = useState("");
  const [copied, setCopied] = useState(false);

  if (draft === null) {
    return (
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          setDraft(buildPatternDraft(pattern.shipper, fieldLabel, pattern.emailIds));
          setTo(pattern.senders.join(", "));
        }}
      >
        <Mail className="size-4" />
        Draft one summary email
      </Button>
    );
  }

  const href = mailtoHref(to, draft);

  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-background p-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="w-16 shrink-0 text-muted-foreground">To</span>
        <input
          type="text"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder="No sender on any case in this group — enter one or more addresses"
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
        rows={8}
        className="font-mono text-xs"
      />
      <div className="flex flex-wrap gap-2">
        {href && (
          <a
            href={href}
            onClick={() => {
              markPatternContacted(pattern.shipper, pattern.field);
              onEmailed();
            }}
          >
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
