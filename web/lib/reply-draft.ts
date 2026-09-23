import type { CaseReport } from "@/lib/api";
import { FIELD_LABELS, reviewReasonClause } from "@/lib/labels";

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
 */
export function buildReplyDraft(report: CaseReport, reference = report.email_id): string {
  const status = report.effective?.status ?? report.status;
  const reviewReason = report.effective?.review_reason ?? report.review_reason;
  const defectFields = report.effective?.defect_fields ?? report.defect_fields;

  if (status === "OK") {
    return [
      `Subject: Re: ${reference} — SI/BL checked, no discrepancy`,
      "",
      "Hello,",
      "",
      "We compared the draft Bill of Lading against the Shipping Instruction for " +
        `${reference} across all seven fields. No mismatch was found.`,
      "",
      "Regards,",
    ].join("\n");
  }

  if (status === "NEEDS_REVIEW") {
    const reason = reviewReason
      ? reviewReasonClause(reviewReason)
      : "we could not complete an automated check";
    return [
      `Subject: Re: ${reference} — action needed before we can check this`,
      "",
      "Hello,",
      "",
      `We were not able to complete an automated comparison because ${reason}. ` +
        "Could you please re-send the affected document(s) so we can complete the check?",
      "",
      "Regards,",
    ].join("\n");
  }

  const lines = report.fields
    .filter((f) => defectFields.includes(f.field))
    .map((f) => {
      const label = FIELD_LABELS[f.field] ?? f.field;
      return `  - ${label}: SI says "${f.si.raw ?? "?"}", draft BL says "${f.bl.raw ?? "?"}"`;
    });

  return [
    `Subject: Re: ${reference} — discrepancy found between SI and draft BL`,
    "",
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
  ].join("\n");
}
