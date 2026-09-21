import Link from "next/link";
import { useCountUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * The count-up number card — extracted out of the Home page so /demo's
 * Impact step renders the exact same card for the exact same numbers,
 * instead of a second hand-copied version that could start looking
 * different the moment one of them got a style tweak.
 */
const STAT_ACCENT = {
  primary: "text-primary",
  danger: "text-danger",
  warn: "text-warn",
} as const;

export function BigStat({
  label,
  value,
  accent,
  href,
}: {
  label: string;
  value: number;
  accent: keyof typeof STAT_ACCENT;
  href: string;
}) {
  const display = useCountUp(value);
  return (
    <Link
      href={href}
      className="group rounded-xl border bg-card p-5 transition-colors hover:border-primary/40 hover:bg-muted/40"
    >
      <div className={cn("font-heading text-4xl font-semibold tabular-nums", STAT_ACCENT[accent])}>{display}</div>
      <div className="mt-1 flex items-center gap-1 text-sm text-muted-foreground">
        {label}
        <span className="opacity-0 transition-opacity group-hover:opacity-100">→</span>
      </div>
    </Link>
  );
}

export function MiniStat({ label, value, href }: { label: string; value: number; href: string }) {
  const display = useCountUp(value);
  return (
    <Link
      href={href}
      className="rounded-lg border bg-card px-3 py-2 text-center transition-colors hover:border-primary/40 hover:bg-muted/40"
    >
      <div className="font-heading text-lg font-semibold tabular-nums">{display}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </Link>
  );
}
