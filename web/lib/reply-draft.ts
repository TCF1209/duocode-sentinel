import type { CaseReport } from "@/lib/api";
import { FIELD_LABELS, reviewReasonClause } from "@/lib/labels";

/**
 * A plain-text reply draft listing the discrepancies found, built entirely
 * from data already in the report — no extra API call, no model call. This
 * is a formatting convenience for an operator, not a generated decision:
 * every figure it quotes is the field extraction already shown on the page.
 */
export function buildReplyDraft(report: CaseReport, reference = report.email_id): string {
  if (report.status === "OK") {
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

  if (report.status === "NEEDS_REVIEW") {
    const reason = report.review_reason
      ? reviewReasonClause(report.review_reason)
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
    .filter((f) => f.verdict === "MISMATCH")
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
      `and found ${report.defect_fields.length} field(s) that do not match:`,
    "",
    ...lines,
    "",
    "Could you please confirm which value is correct so we can finalise the Bill of Lading?",
    "",
    "Regards,",
  ].join("\n");
}
