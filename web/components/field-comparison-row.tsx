import type { FieldComparisonReport, FieldValueReport, Verdict } from "@/lib/api";
import { cn } from "@/lib/utils";
import { VerdictBadge } from "@/components/status-badges";
import { FIELD_LABELS } from "@/lib/labels";

function Side({ value, side }: { value: FieldValueReport; side: "SI" | "BL" }) {
  if (!value.present) {
    return (
      <div className="flex-1 rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground/70">{side}</div>
        {value.blank ? "blank / placeholder value" : "not found"}
      </div>
    );
  }
  return (
    <div className="flex-1 rounded-md border p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{side}</div>
      <div className="mt-1 font-mono text-sm">{value.raw}</div>
      {value.evidence && (
        <div className="mt-2 border-t pt-2 text-xs text-muted-foreground">
          <div>
            {value.evidence.doc} &middot; {value.evidence.locator} &middot; label &quot;{value.evidence.label}&quot;
            {value.extractor !== "rule" && (
              <span className="ml-1 rounded bg-ai-bg px-1 py-0.5 text-ai">{value.extractor}</span>
            )}
          </div>
          <div className="mt-1 font-mono italic">&ldquo;{value.evidence.snippet.trim()}&rdquo;</div>
        </div>
      )}
    </div>
  );
}

// Mirrors the ok/warn/danger language used everywhere else: a mismatch is
// danger, an uncomparable field is a warn (it's *why* a case needs review,
// not a dead end), and a clean match stays plain so problem fields are the
// ones that visually jump out while scanning down the list.
const CARD_STYLE: Record<Verdict, string> = {
  MATCH: "bg-card",
  MISMATCH: "border-danger/30 bg-danger-bg/60",
  UNCOMPARABLE: "border-warn/30 bg-warn-bg/60",
};

// "bl_missing" -> "BL missing", not "Bl missing" -- si/bl are the document
// acronyms this whole app is built around, so a generic capitalize-first-
// letter reads like a typo of them.
function formatReason(reason: string) {
  const words = reason.split("_").map((w) => (w === "si" || w === "bl" ? w.toUpperCase() : w));
  const joined = words.join(" ");
  return joined.charAt(0).toUpperCase() + joined.slice(1);
}

export function FieldComparisonRow({ comparison }: { comparison: FieldComparisonReport }) {
  return (
    <div className={cn("rounded-lg border p-3 transition-colors", CARD_STYLE[comparison.verdict])}>
      <div className="mb-2 flex items-center justify-between">
        <div className="font-medium">{FIELD_LABELS[comparison.field] ?? comparison.field}</div>
        <VerdictBadge verdict={comparison.verdict} />
      </div>
      {comparison.reason && <p className="mb-2 text-xs text-muted-foreground">{formatReason(comparison.reason)}</p>}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Side value={comparison.si} side="SI" />
        <Side value={comparison.bl} side="BL" />
      </div>
    </div>
  );
}
