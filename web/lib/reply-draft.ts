import type { CaseReport } from "@/lib/api";
import { FIELD_LABELS, reviewReasonClause } from "@/lib/labels";

export interface ReplyDraft {
  subject: string;
  body: string;
}

/**
 * A plain-text reply draft listing the discrepancies found, built entirely
 * from data already in the report — no extra API call, no model call. This
 * is a formatting convenience for an operator, not a generated decision:
 * every figure it quotes is the field extraction already shown on the page.
 *
 * Reads the *effective* outcome when the case has been reviewed, not the
 * system's original call. `report.status`/`defect_fields` deliberately stay
 * the system's own answer everywhere else on this page — lib/api.ts's own
 * comment on `effective` says so, "so a card can show both" — but this
 * draft is the one artifact that leaves that context and goes to someone
 * outside the review queue. They have no way to see that a reviewer already
 * corrected what the system said, so the draft has to say what is actually
 * true now, not what the system guessed before a human looked at it.
 * `effective` is only ever present once a case has been reviewed
 * (`GET /cases/{id}`); on `/compare`, where nothing is stored and nothing
 * can be reviewed, it is always absent, and this falls back to the system's
 * own answer exactly as before.
 *
 * Returns `{subject, body}` rather than one flat string so a caller can feed
 * either half to a `mailto:` link without parsing a "Subject: ..." line back
 * out of it; `ReplyDraftPanel` joins them for the on-screen textarea, which
 * is the only place the combined form is what's actually wanted.
 */
export function buildReplyDraft(report: CaseReport, reference = report.email_id): ReplyDraft {
  const status = report.effective?.status ?? report.status;
  const reviewReason = report.effective?.review_reason ?? report.review_reason;
  const defectFields = report.effective?.defect_fields ?? report.defect_fields;

  if (status === "OK") {
    return {
      subject: `Re: ${reference} — SI/BL checked, no discrepancy`,
      body: [
        "Hello,",
        "",
        "We compared the draft Bill of Lading against the Shipping Instruction for " +
          `${reference} across all seven fields. No mismatch was found.`,
        "",
        "Regards,",
      ].join("\n"),
    };
  }

  if (status === "NEEDS_REVIEW") {
    const reason = reviewReason
      ? reviewReasonClause(reviewReason)
      : "we could not complete an automated check";
    return {
      subject: `Re: ${reference} — action needed before we can check this`,
      body: [
        "Hello,",
        "",
        `We were not able to complete an automated comparison because ${reason}. ` +
          "Could you please re-send the affected document(s) so we can complete the check?",
        "",
        "Regards,",
      ].join("\n"),
    };
  }

  const lines = report.fields
    .filter((f) => defectFields.includes(f.field))
    .map((f) => {
      const label = FIELD_LABELS[f.field] ?? f.field;
      return `  - ${label}: SI says "${f.si.raw ?? "?"}", draft BL says "${f.bl.raw ?? "?"}"`;
    });

  return {
    subject: `Re: ${reference} — discrepancy found between SI and draft BL`,
    body: [
      "Hello,",
      "",
      `We compared the draft Bill of Lading against the Shipping Instruction for ${reference} ` +
        `and found ${defectFields.length} field(s) that do not match:`,
      "",
      ...lines,
      "",
      "Could you please confirm which value is correct so we can finalise the Bill of Lading?",
      "",
      "Regards,",
    ].join("\n"),
  };
}

/** `Subject: ...\n\n<body>` — the form the on-screen textarea has always
 *  shown, kept as one function so the two callers (the panel's initial
 *  value, and re-deriving it is never needed elsewhere) can't drift. */
export function formatReplyDraft(draft: ReplyDraft): string {
  return `Subject: ${draft.subject}\n\n${draft.body}`;
}

/** A `mailto:` URL a human still has to review and press send on, in their
 *  own already-authenticated mail client — Sentinel never transmits
 *  anything itself. `undefined` when there is no known recipient (e.g. a
 *  /compare upload, which has no inbox record to read a sender from). */
export function mailtoHref(to: string | undefined | null, draft: ReplyDraft): string | undefined {
  if (!to) return undefined;
  const params = new URLSearchParams({ subject: draft.subject, body: draft.body });
  return `mailto:${encodeURIComponent(to)}?${params.toString()}`;
}
