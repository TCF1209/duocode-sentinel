import type { CaseSummary } from "@/lib/api";

/**
 * Which real cases of a run show which feature -- chosen by what each case
 * *is*, never by a hard-coded email id. Feeds the home page's "See it live"
 * tiles (the run page's "Worth opening" strip that used the same picks was
 * removed at the user's ask: it repeated the tiles one screen later).
 *
 * - recheck: the first escalated comparison request that arrived with
 *   nothing attached (re-upload is the whole answer to that, and the
 *   re-check panel offers a sample pair there -- recheck-panel.tsx -- so a
 *   visitor with no files of their own can still watch it work), else one
 *   missing a document, else any escalated one.
 * - scan: the first pair whose scan a vision model read out, else the first
 *   image-only scan. Never just "could not be read": that is as often a
 *   corrupt file, which has nothing to read out -- the tile once opened one.
 *   `scanReadOut` says which of the two it found.
 * - history: the case at the head of the largest same-shipper-same-field
 *   group of mismatches (two or more), where the field card carries
 *   "N other cases from this shipper".
 * - mismatch: the mismatch with the most fields wrong -- two visible
 *   mismatches make a better first case than one.
 *
 * A key is absent when the run has no case of that kind.
 */
export type ShowcaseKey = "recheck" | "scan" | "history" | "mismatch";

export interface Showcases extends Partial<Record<ShowcaseKey, string>> {
  /** Whether `scan` was read out by the model. False in any run made
   *  without it -- the API's own startup run among them -- whose scans
   *  escalate with no transcript on them. */
  scanReadOut: boolean;
}

export function pickShowcases(cases: CaseSummary[]): Showcases {
  const comparisons = cases.filter((c) => c.category === "BL_COMPARISON");
  const escalated = comparisons.filter((c) => c.status === "NEEDS_REVIEW");
  // `?.` because an API from before `attachments` existed leaves it out.
  const recheck =
    escalated.find((c) => c.review_reason === "missing_attachment" && c.attachments?.length === 0) ??
    escalated.find((c) => c.review_reason === "missing_attachment") ??
    escalated[0];
  const readOut = comparisons.find((c) => c.scan_transcribed);
  const scan = readOut ?? comparisons.find((c) => c.scanned);

  let mismatch: CaseSummary | undefined;
  for (const c of comparisons) {
    if (c.status !== "MISMATCH") continue;
    if (!mismatch || c.defect_fields.length > mismatch.defect_fields.length) mismatch = c;
  }

  const groups = new Map<string, string[]>();
  for (const c of comparisons) {
    if (c.status !== "MISMATCH" || !c.shipper) continue;
    for (const f of c.defect_fields) {
      const key = `${c.shipper}\u0000${f}`;
      groups.set(key, [...(groups.get(key) ?? []), c.email_id]);
    }
  }
  const largest = [...groups.values()].filter((ids) => ids.length >= 2).sort((a, b) => b.length - a.length)[0];

  return {
    recheck: recheck?.email_id,
    scan: scan?.email_id,
    scanReadOut: Boolean(readOut),
    history: largest?.[0],
    mismatch: mismatch?.email_id,
  };
}

/** The case page URL a showcase lands on, with the panel to spotlight. */
export function showcaseHref(runId: string, emailId: string, spotlight?: string): string {
  return `/runs/${runId}/cases/${emailId}${spotlight ? `?spotlight=${spotlight}` : ""}`;
}

/** Where the scan showcase goes when no scan in the run was read out: the
 *  Compare page's own scanned pair, loaded with the model switched on, so a
 *  press on Compare reads it out live (compare/page.tsx's `?sample=`). */
export const SAMPLE_SCAN_HREF = "/compare?sample=scanned";
