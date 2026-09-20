import Link from "next/link";
import { ArrowLeft } from "lucide-react";

/**
 * A bordered chip, not a plain underlined text link — a "back to X" that
 * blends into the page like any other sentence reads as decoration, not a
 * button, and gets skipped. Shared by every page one level below a list
 * (a run's case table, a run's metrics, a single case) so all of them read
 * the same way instead of each inventing its own back-link treatment.
 */
export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="inline-flex w-fit items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
    >
      <ArrowLeft className="size-3.5" />
      {label}
    </Link>
  );
}
