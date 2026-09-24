const KEY_PREFIX = "sentinel:pattern-contacted:";

function storageKey(shipper: string, field: string): string {
  return KEY_PREFIX + shipper + "\u0000" + field;
}

/**
 * Records that an operator opened a mail client to follow up on this
 * (shipper, field) pattern -- browser-local only, which matches the rest of
 * this system's persistence level: the backend `Store` is in-memory and
 * empty on every restart too (docs/STATUS.md), so a marker that only
 * outlives the current browser session is not an extra shortfall next to
 * that.
 *
 * Deliberately separate from case review state: sending a follow-up email
 * does not mean the shipper actually fixed anything, so it must not make a
 * pattern disappear from "Patterns worth a second look" the way a genuine
 * correction does (see store.effective_outcome, threaded through to
 * CaseSummary.has_defect) -- it only annotates that a pattern still shown
 * has already been followed up on, so an operator does not re-email it
 * having forgotten they already did.
 *
 * Also inherently approximate in one way that can't be fixed client-side:
 * a mailto: link hands off to the operator's own mail client and this page
 * never hears back from it, so this can only ever record "a draft was
 * opened," not "a message was actually sent" -- lib/reply-draft.ts's own
 * comment on buildReplyDraft notes the same limit for the single-case
 * draft.
 */
export function markPatternContacted(shipper: string, field: string): void {
  try {
    localStorage.setItem(storageKey(shipper, field), String(Date.now()));
  } catch {
    // localStorage unavailable (private mode etc.) -- the marker is a nicety, not required
  }
}

export function getPatternContactedAt(shipper: string, field: string): number | null {
  try {
    const raw = localStorage.getItem(storageKey(shipper, field));
    return raw === null ? null : Number(raw);
  } catch {
    return null;
  }
}
