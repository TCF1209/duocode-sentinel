const RTF = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60 * 1000],
  ["month", 30 * 24 * 60 * 60 * 1000],
  ["day", 24 * 60 * 60 * 1000],
  ["hour", 60 * 60 * 1000],
  ["minute", 60 * 1000],
];

/** "2 minutes ago", "just now" -- Intl.RelativeTimeFormat under the hood
 *  rather than hand-rolled plural/singular rules. */
export function timeAgo(ms: number, now = Date.now()): string {
  const diff = now - ms;
  if (diff < 30_000) return "just now";
  for (const [unit, unitMs] of UNITS) {
    if (diff >= unitMs) return RTF.format(-Math.round(diff / unitMs), unit);
  }
  return RTF.format(-Math.round(diff / 1000), "second");
}
