import type { CaseStatus, Category, ReviewReason } from "@/lib/api";

/**
 * The one place backend field/category/reason codes turn into words a
 * person reads. Used by the case report, the run table's "Discrepant
 * fields" column, the metrics charts, and the reply-draft generator —
 * before this existed, three of those four had their own hand-copied
 * version of the same map,
 * and the metrics charts had none, so a backend code could show up
 * formatted in one place and verbatim ("container_count") in another.
 */
export const FIELD_LABELS: Record<string, string> = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify Party",
  port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge",
  container_count: "Container Count",
  gross_weight_kg: "Gross Weight (kg)",
};

export const CATEGORY_LABELS: Record<Category, string> = {
  BL_COMPARISON: "Comparisons",
  SI_REQUEST: "SI requests",
  INVOICE_QUERY: "Invoice queries",
  GENERAL: "General",
  SPAM: "Spam",
};

// The same five, singular, for the badge on one case ("Comparison") --
// CATEGORY_LABELS counts many ("Comparisons 220" on the run page's chips).
// Never the backend code: a badge that says BL_COMPARISON is the one thing
// on a row a first-time visitor cannot read.
export const CATEGORY_BADGE_LABELS: Record<Category, string> = {
  BL_COMPARISON: "Comparison",
  SI_REQUEST: "SI request",
  INVOICE_QUERY: "Invoice query",
  GENERAL: "General",
  SPAM: "Spam",
};

// "OK" reads as a chat acknowledgement, not the outcome of a 7-field
// verification, and a backend code (NEEDS_REVIEW) never goes straight into a
// badge. The case outcome reads "No discrepancy" / "Discrepancy" /
// "Escalated" -- the document-checking terms, a claim about the documents
// rather than about the tool.
export const STATUS_LABELS: Record<CaseStatus, string> = {
  // Every status word in the app comes from this map.
  OK: "No discrepancy",
  MISMATCH: "Discrepancy",
  NEEDS_REVIEW: "Escalated",
};

// Full standalone sentences, for the case report's review banner. Also the
// source of the reply-draft email's mid-sentence clause (via
// `reviewReasonClause` below) and the metrics chart's tooltip, instead of
// each of those keeping its own independently-worded copy.
export const REVIEW_REASON_TEXT: Record<ReviewReason, string> = {
  wrong_doc_type: "An attachment is not the expected SI or draft BL.",
  missing_attachment: "The SI or the draft BL is missing from this email.",
  unreadable: "A document could not be read.",
  missing_value: "One or more fields are blank or carry a label Sentinel does not recognise.",
};

/** "The SI or the draft BL is missing from this email." -> "the SI or the draft BL is missing from this email" */
export function reviewReasonClause(reason: ReviewReason): string {
  const sentence = REVIEW_REASON_TEXT[reason];
  return sentence.charAt(0).toLowerCase() + sentence.slice(1).replace(/\.$/, "");
}

// Short form of the same four reasons, for chart axes/legends where the
// full sentence above doesn't fit.
export const REVIEW_REASON_LABELS: Record<ReviewReason, string> = {
  wrong_doc_type: "Wrong document",
  missing_attachment: "Missing document",
  unreadable: "Unreadable document",
  missing_value: "Blank or unrecognised field",
};
