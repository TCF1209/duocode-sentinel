import { Badge } from "@/components/ui/badge";
import type { CaseStatus, Category, DecidedBy, Verdict } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<CaseStatus, string> = {
  OK: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  MISMATCH: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  NEEDS_REVIEW: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
};

export function StatusBadge({ status }: { status: CaseStatus }) {
  return <Badge className={cn("border-0", STATUS_STYLE[status])}>{status}</Badge>;
}

const VERDICT_STYLE: Record<Verdict, string> = {
  MATCH: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  MISMATCH: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  UNCOMPARABLE: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <Badge className={cn("border-0", VERDICT_STYLE[verdict])}>{verdict}</Badge>;
}

export function DecidedByBadge({ decidedBy }: { decidedBy: DecidedBy }) {
  return (
    <Badge variant="outline" className={decidedBy === "llm" ? "border-violet-400 text-violet-700 dark:text-violet-300" : ""}>
      {decidedBy === "llm" ? "LLM" : "rule"}
    </Badge>
  );
}

export function CategoryBadge({ category }: { category: Category }) {
  return <Badge variant="secondary">{category}</Badge>;
}
