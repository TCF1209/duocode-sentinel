import type { CaseSummary } from "@/lib/api";

/**
 * What this inbox would cost a person, for the "Before Sentinel" view.
 *
 * The two rates are the team's own estimates, the ones already written into
 * docs/PITCH_DAY.md after the mentor session of 24 Sep ("≈4 min a pair, 20 s
 * an email") and labelled as estimates wherever they are shown -- the mentor
 * asked for the number and asked that it be called what it is. One place
 * for both, so the page and the pitch can never drift apart.
 */
export const SECONDS_TO_READ_ONE_EMAIL = 20;
export const MINUTES_TO_CHECK_ONE_PAIR = 4;
export const FIELDS_PER_PAIR = 7;

export interface ManualWorkload {
  emails: number;
  /** SI/BL pairs (hasPair) -- the ones a person would have to find among
   *  the emails, then check field by field. */
  pairs: number;
  fields: number;
  hours: number;
}

/** A comparison request that arrived with a pair to check: two documents
 *  attached. Most of the rest ask for the draft BL ("please send the draft
 *  BL for checking") and carry nothing, so there is no pair to check yet --
 *  124 of the 220 in the graded inbox have one. Read off the email's own
 *  attachment list, what a person would see, not off Sentinel's reading.
 *  `?.`: an API from before `attachments` existed leaves it out. */
export function hasPair(c: CaseSummary): boolean {
  return c.category === "BL_COMPARISON" && (c.attachments?.length ?? 0) >= 2;
}

export function manualWorkload(cases: CaseSummary[]): ManualWorkload {
  const emails = cases.length;
  const pairs = cases.filter(hasPair).length;
  const seconds = emails * SECONDS_TO_READ_ONE_EMAIL + pairs * MINUTES_TO_CHECK_ONE_PAIR * 60;
  return { emails, pairs, fields: pairs * FIELDS_PER_PAIR, hours: seconds / 3600 };
}

export function formatHours(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  return `${hours.toFixed(1)} h`;
}

/** "38 s", "66 min", "14.7 h" -- the same duration at whichever unit reads
 *  at a glance, for the visitor's own measured pace projected over the
 *  inbox (run-page-view.tsx). */
export function formatSeconds(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`;
  return formatHours(seconds / 3600);
}
