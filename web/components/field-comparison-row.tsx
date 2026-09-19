import type { FieldComparisonReport, FieldValueReport } from "@/lib/api";
import { cn } from "@/lib/utils";
import { VerdictBadge } from "@/components/status-badges";

const FIELD_LABELS: Record<string, string> = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify Party",
  port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge",
  container_count: "Container Count",
  gross_weight_kg: "Gross Weight (kg)",
};

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
              <span className="ml-1 rounded bg-violet-100 px-1 py-0.5 text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                {value.extractor}
              </span>
            )}
          </div>
          <div className="mt-1 italic">&ldquo;{value.evidence.snippet.trim()}&rdquo;</div>
        </div>
      )}
    </div>
  );
}

export function FieldComparisonRow({ comparison }: { comparison: FieldComparisonReport }) {
  const mismatched = comparison.verdict === "MISMATCH";
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        mismatched && "border-red-300 bg-red-50/60 dark:border-red-900 dark:bg-red-950/30",
      )}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="font-medium">{FIELD_LABELS[comparison.field] ?? comparison.field}</div>
        <VerdictBadge verdict={comparison.verdict} />
      </div>
      {comparison.reason && <p className="mb-2 text-xs text-muted-foreground">{comparison.reason}</p>}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Side value={comparison.si} side="SI" />
        <Side value={comparison.bl} side="BL" />
      </div>
    </div>
  );
}
