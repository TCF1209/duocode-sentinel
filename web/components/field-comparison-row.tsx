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
      {/* Not font-mono: the source data is almost always an already-
          upper-case company name, and monospace on a long upper-case run
          is one of the harder combinations to actually read at a glance —
          it is built for fixed-width tokens (an email id, a line number),
          not a party name. A proportional font reads names the way a
          person reading the real document would. The text itself is
          untouched either way — only the typeface changes, never the
          case, since the case is part of what "exact evidence" means
          here. */}
      <div className="mt-1 text-sm font-medium">{value.raw}</div>
      {value.evidence && (
        <div className="mt-2 border-t pt-2 text-xs text-muted-foreground">
          <div>
            {value.evidence.doc} &middot; {value.evidence.locator} &middot; label &quot;{value.evidence.label}&quot;
            {value.extractor !== "rule" && (
              <span className="ml-1 rounded bg-ai-bg px-1 py-0.5 text-ai">{value.extractor}</span>
            )}
          </div>
          {/* A left border reads as "this is a quote" on its own, so the
              snippet no longer needs a distinct typeface to tell it apart
              from the value above — freeing it from font-mono fixes the
              same crowding here, and the two are visually distinct now by
              role (bordered quote vs. plain value) rather than by both
              fighting for attention in the same dense typeface. */}
          <div className="mt-1.5 border-l-2 border-muted-foreground/25 pl-2 italic">
            &ldquo;{value.evidence.snippet.trim()}&rdquo;
          </div>
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

// Most uncomparable reasons are a state ("BL missing") and read fine as a
// label. This one is a claim about the two values, and "Ocr confusable" tells
// a reviewer nothing about what to do -- they need to know that both readings
// are there and that the difference is in glyphs a scanner mixes up.
const REASON_TEXT: Record<string, string> = {
  ocr_confusable:
    "Same length, differing only in characters OCR confuses (O/0, I/1, S/5, B/8) -- likely one value read two ways. Check both against the pages.",
};

// "bl_missing" -> "BL missing", not "Bl missing" -- si/bl are the document
// acronyms this whole app is built around, so a generic capitalize-first-
// letter reads like a typo of them.
function formatReason(reason: string) {
  const override = REASON_TEXT[reason];
  if (override) return override;
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
