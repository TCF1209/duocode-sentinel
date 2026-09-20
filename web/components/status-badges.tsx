import { Badge } from "@/components/ui/badge";
import type { CaseStatus, Category, DecidedBy, RunStatus, Verdict } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<CaseStatus, string> = {
  OK: "bg-ok-bg text-ok",
  MISMATCH: "bg-danger-bg text-danger",
  NEEDS_REVIEW: "bg-warn-bg text-warn",
};

const STATUS_DOT: Record<CaseStatus, string> = {
  OK: "bg-ok",
  MISMATCH: "bg-danger",
  NEEDS_REVIEW: "bg-warn",
};

// The same OK/MISMATCH/NEEDS_REVIEW colors as raw CSS custom-property
// references, for consumers that can't take a Tailwind class — Recharts
// `<Cell fill>` takes a color string, not a className. Keyed by the actual
// CaseStatus type (not a loose Record<string, string>) so a status this
// doesn't cover is a type error, not a silent `?? "var(--muted-foreground)"`
// fallback at the call site.
export const STATUS_COLOR_VAR: Record<CaseStatus, string> = {
  OK: "var(--ok)",
  MISMATCH: "var(--danger)",
  NEEDS_REVIEW: "var(--warn)",
};

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <Badge className={cn("gap-1.5 border-0 font-medium", STATUS_STYLE[status])}>
      <span className={cn("size-1.5 rounded-full", STATUS_DOT[status])} />
      {STATUS_LABELS[status]}
    </Badge>
  );
}

const VERDICT_STYLE: Record<Verdict, string> = {
  MATCH: "bg-ok-bg text-ok",
  MISMATCH: "bg-danger-bg text-danger",
  // Warn, not neutral: an uncomparable field is not "nothing to see here" —
  // it's the reason the case likely needs a human, same as NEEDS_REVIEW.
  UNCOMPARABLE: "bg-warn-bg text-warn",
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <Badge className={cn("border-0 font-medium", VERDICT_STYLE[verdict])}>{verdict}</Badge>;
}

export function DecidedByBadge({ decidedBy }: { decidedBy: DecidedBy }) {
  return (
    <Badge className={cn("border-0 font-medium", decidedBy === "llm" ? "bg-ai-bg text-ai" : "bg-muted text-muted-foreground")}>
      {decidedBy === "llm" ? "LLM" : "rule"}
    </Badge>
  );
}

export function CategoryBadge({ category }: { category: Category }) {
  return <Badge variant="secondary">{category}</Badge>;
}

const RUN_STATUS_STYLE: Record<RunStatus["status"], string> = {
  running: "bg-warn-bg text-warn",
  failed: "bg-danger-bg text-danger",
  done: "bg-ok-bg text-ok",
};

const RUN_STATUS_LABEL: Record<RunStatus["status"], string> = {
  running: "running…",
  failed: "failed",
  done: "done",
};

export function RunStatusPill({ status }: { status: RunStatus["status"] }) {
  return <Badge className={cn("border-0 font-medium", RUN_STATUS_STYLE[status])}>{RUN_STATUS_LABEL[status]}</Badge>;
}
