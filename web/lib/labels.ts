import type { CaseStatus, Category, ReviewReason } from "@/lib/api";

/**
 * The one place backend field/category/reason codes turn into words a
 * person reads. Used by the case report, the run table's Defects column,
 * the metrics charts, and the reply-draft generator — before this existed,
 * three of those four had their own hand-copied version of the same map,
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

// "OK" reads as a chat acknowledgement, not the outcome of a 7-field
// verification — "Matched" says what actually happened, and pairs with
// "Mismatch" the same way the two outcomes already pair everywhere else
// (VerdictBadge already uses MATCH/MISMATCH per field). NEEDS_REVIEW gets a
// space instead of shipping its underscore straight into a badge.
export const STATUS_LABELS: Record<CaseStatus, string> = {
  // "No mismatch detected" is the problem statement's own phrase for a clean
  // pair, and judges told the mentors they dislike "Matched/Mismatched" as a
  // pair of labels -- "matched" reads as a claim about the tool rather than
  // about the documents. Every status word in the app comes from this map.
  OK: "No mismatch",
  MISMATCH: "Mismatch",
  NEEDS_REVIEW: "Needs review",
};

// Full standalone sentences, for the case report's review banner. Also the
// source of the reply-draft email's mid-sentence clause (via
// `reviewReasonClause` below) and the metrics chart's tooltip, instead of
// each of those keeping its own independently-worded copy.
export const REVIEW_REASON_TEXT: Record<ReviewReason, string> = {
  wrong_doc_type: "An attachment doesn't look like the document type it claims to be.",
  missing_attachment: "An expected document is missing from this email.",
  unreadable: "A document couldn't be read.",
  missing_value: "One or more required fields are blank, or printed under a label Sentinel could not recognise.",
};

/** "An expected document is missing from this email." -> "an expected document is missing from this email" */
export function reviewReasonClause(reason: ReviewReason): string {
  const sentence = REVIEW_REASON_TEXT[reason];
  return sentence.charAt(0).toLowerCase() + sentence.slice(1).replace(/\.$/, "");
}

// Short form of the same four reasons, for chart axes/legends where the
// full sentence above doesn't fit.
export const REVIEW_REASON_LABELS: Record<ReviewReason, string> = {
  wrong_doc_type: "Wrong document type",
  missing_attachment: "Missing attachment",
  unreadable: "Unreadable document",
  missing_value: "Missing value",
};
