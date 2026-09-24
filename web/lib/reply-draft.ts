import type { CaseReport, DocumentReport, FieldComparisonReport, FieldValueReport } from "@/lib/api";
import { FIELD_LABELS } from "@/lib/labels";

/**
 * What a reply is about, chosen by rules from signals the report already
 * holds: the review reason, which attachments arrived and what they are, why
 * a file could not be read, and which fields were blank or differ. No model is
 * involved in choosing it.
 *
 * It exists because one reason is not one reply. "unreadable" covers a file
 * that will not open (ask for a fresh copy) and a clean scan (do NOT ask: a
 * re-send returns the same image). "missing_value" is a customer who left a
 * field blank, where the only safe reply asks and never confirms. A single
 * "please re-send the affected document(s)" was wrong for 8 of the 20
 * escalations on the graded inbox.
 */
export type DraftSituation =
  | "no_discrepancy"
  | "discrepancy"
  | "attachments_missing"
  | "document_missing"
  | "file_unopenable"
  | "scanned_copies"
  | "wrong_document"
  | "values_to_confirm"
  | "review_generic";

/**
 * A reply in the parts it is assembled from, split along the one line that
 * matters: what may be reworded and what may not.
 *
 * `greeting` and `closing` are courtesy ("Thank you for your email.", "Thank
 * you for your patience."). They carry no case value and no claim about the
 * case, so they are the only text the optional wording pass is ever shown or
 * allowed to rewrite.
 *
 * Everything else is locked. `context` says what happened ("We could not
 * open one of the attachments"), `facts` are quoted from the case's own
 * evidence, and `action` is the decision the reply carries ("please confirm
 * the gross weight", "no need to re-send"). A model that rewrote `context`
 * could turn "some fields do not match" into "everything agrees" in words no
 * filter reliably catches, so it is not offered the sentence at all.
 */
export interface DraftParts {
  situation: DraftSituation;
  greeting: string;
  context: string;
  facts: string[];
  action: string;
  closing: string;
}

export interface ReplyDraft {
  subject: string;
  body: string;
  /** Absent on the pattern-level draft, which is not per-case. */
  parts?: DraftParts;
}

const GREETING = "Thank you for your email.";

const SIDE_NAMES = { si: "Shipping Instruction", bl: "draft Bill of Lading" } as const;
type Side = keyof typeof SIDE_NAMES;

const DOC_TYPE_NAMES: Record<string, string> = {
  SHIPPING_INSTRUCTION: "Shipping Instruction",
  BILL_OF_LADING: "draft Bill of Lading",
  COMMERCIAL_INVOICE: "Commercial Invoice",
  PACKING_LIST: "Packing List",
  CERTIFICATE_OF_ORIGIN: "Certificate of Origin",
};

// In-sentence names ("please confirm the gross weight"), where FIELD_LABELS is
// a column heading ("Gross Weight (kg)").
const FIELD_PHRASES: Record<string, string> = {
  shipper: "shipper",
  consignee: "consignee",
  notify_party: "notify party",
  port_of_loading: "port of loading",
  port_of_discharge: "port of discharge",
  container_count: "container count",
  gross_weight_kg: "gross weight",
};

const UNREADABLE_TEXT: Record<string, string> = {
  corrupt: "the file will not open",
  empty_file: "the file arrived empty",
  missing_file: "the file did not come through",
  unsupported: "the file is in a format or size we cannot open",
};

// A field the reply asks the customer about: blank, unreadable as a value, or
// differing only in characters a scan confuses. Not "si_missing"/"bl_missing":
// those mean no label in the document was recognised as the field, and the
// gate says the value may well be there under a wording the label table has
// never seen. That is ours to read off the document, not the customer's to
// supply, so it never reaches the reply.
const ASK_REASONS = new Set(["si_blank", "bl_blank", "si_unparseable", "bl_unparseable", "ocr_confusable"]);

const fileName = (doc: DocumentReport) => doc.path.split(/[\\/]/).pop() || doc.path;
const phrase = (field: string) => FIELD_PHRASES[field] ?? field.replace(/_/g, " ");
const label = (field: string) => FIELD_LABELS[field] ?? field;
const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function docTypeName(docType: string): string {
  if (DOC_TYPE_NAMES[docType]) return DOC_TYPE_NAMES[docType];
  return docType && docType !== "UNKNOWN"
    ? docType.toLowerCase().replace(/_/g, " ")
    : "a document we could not identify";
}

/** What a received file actually is, from its content rather than the slot
 *  it was put in: with one attachment, the slot is only a guess. */
function describeDoc(doc: DocumentReport): string {
  if (!doc.readable) {
    return doc.unreadable_reason === "no_text_layer" ? "a scanned document" : "a file we could not open";
  }
  return docTypeName(doc.doc_type);
}

function joinAnd(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** The body, in the one order every draft uses. */
export function assembleBody(parts: DraftParts): string {
  const lines = ["Hello,", "", `${parts.greeting} ${parts.context}`.trim()];
  if (parts.facts.length) lines.push("", ...parts.facts);
  if (parts.action) lines.push("", parts.action);
  if (parts.closing) lines.push("", parts.closing);
  lines.push("", "Regards,");
  return lines.join("\n");
}

/**
 * Threads under the customer's own subject when the inbox record has one. The
 * dataset writes "RE_"/"FW_" where a mail client writes "Re:", so those are
 * stripped rather than stacked. Falls back to Sentinel's reference on
 * /compare, where there is no email and so no subject.
 */
function replySubject(report: CaseReport, reference: string, fallback: string): string {
  const original = (report.subject ?? "").trim();
  if (original) return `Re: ${original.replace(/^((re|fw|fwd)\s*[:_]\s*)+/i, "")}`;
  return `Re: ${reference} — ${fallback}`;
}

/** `"N/A"` → ` (it reads "N/A")`; an empty cell says nothing extra. */
function readsAs(side: FieldValueReport): string {
  const raw = (side.raw ?? "").trim();
  return raw ? ` (it reads "${raw}")` : "";
}

function otherSide(f: FieldComparisonReport, side: Side): string {
  const v = f[side];
  const raw = (v.raw ?? "").trim();
  if (v.present && !v.blank && raw) return `the ${SIDE_NAMES[side]} shows "${raw}"`;
  return `it is not given on the ${SIDE_NAMES[side]} either`;
}

/** One locked line for a field the reply asks about. */
function questionLine(f: FieldComparisonReport): string {
  const name = label(f.field);
  switch (f.reason) {
    case "si_blank":
      return `  - ${name}: left blank on the Shipping Instruction${readsAs(f.si)}; ${otherSide(f, "bl")}.`;
    case "bl_blank":
      return `  - ${name}: left blank on the draft Bill of Lading${readsAs(f.bl)}; ${otherSide(f, "si")}.`;
    case "si_unparseable":
      return (
        `  - ${name}: the Shipping Instruction shows "${f.si.raw ?? ""}", which we could not read as a ` +
        `value; ${otherSide(f, "bl")}.`
      );
    case "bl_unparseable":
      return (
        `  - ${name}: the draft Bill of Lading shows "${f.bl.raw ?? ""}", which we could not read as a ` +
        `value; ${otherSide(f, "si")}.`
      );
    default: // ocr_confusable
      return (
        `  - ${name}: the Shipping Instruction shows "${f.si.raw ?? ""}" and the draft Bill of Lading ` +
        `shows "${f.bl.raw ?? ""}"; they differ only in characters that are easy to misread on a scan.`
      );
  }
}

function mismatchLine(f: FieldComparisonReport): string {
  return (
    `  - ${label(f.field)}: the Shipping Instruction shows "${f.si.raw ?? "?"}"; ` +
    `the draft Bill of Lading shows "${f.bl.raw ?? "?"}".`
  );
}

/**
 * The reply for a case that needs the customer's word on some fields.
 *
 * Every field the reply is about is listed, including a real mismatch that
 * sits beside a blank one: the gate escalates on the blank before it looks at
 * the mismatch, but the mismatch is still on the document, and a reply that
 * asked only about the blank and then said "the other fields agree" would
 * read as a clean bill of health for a BL that has a wrong consignee on it.
 */
function valuesToConfirm(report: CaseReport): DraftParts | null {
  const asked = report.fields.filter((f) => f.verdict === "UNCOMPARABLE" && ASK_REASONS.has(f.reason ?? ""));
  const differing = report.fields.filter((f) => f.verdict === "MISMATCH");
  if (!asked.length && !differing.length) return null;
  const unread = report.fields.filter((f) => f.verdict === "UNCOMPARABLE" && !ASK_REASONS.has(f.reason ?? ""));
  const agreed = report.fields.filter((f) => f.verdict === "MATCH").length;

  let agreedLine: string[] = [];
  if (agreed && unread.length) {
    agreedLine = [`  - ${agreed} of the other fields agree between the two documents; our team is checking the rest by hand.`];
  } else if (agreed === 1) {
    agreedLine = ["  - The other field agrees between the two documents."];
  } else if (agreed) {
    agreedLine = [`  - The other ${agreed} fields agree between the two documents.`];
  }

  const asks: string[] = [];
  if (asked.length) asks.push(`confirm the ${joinAnd(asked.map((f) => phrase(f.field)))}`);
  if (differing.length) asks.push(`tell us which value is correct for the ${joinAnd(differing.map((f) => phrase(f.field)))}`);

  return {
    situation: "values_to_confirm",
    greeting: GREETING,
    context: "We compared the draft Bill of Lading against the Shipping Instruction, and some fields need your confirmation.",
    facts: [...asked.map(questionLine), ...differing.map(mismatchLine), ...agreedLine],
    // The sender of these emails writes that "the customer" left the fields
    // blank, so they may not hold the answer themselves; asking them to check
    // with the customer reads right either way. The draft BL's value is quoted
    // above as what the draft says, and deliberately never confirmed: nobody
    // declared it, and confirming it is how a document of title gets a party
    // or a port no one asked for.
    action:
      `Could you please check with the customer and ${joinAnd(asks)} before we release the Bill of Lading? ` +
      "We have not assumed the draft Bill of Lading is right.",
    closing: "Thank you.",
  };
}

function reviewParts(report: CaseReport, reviewReason: string | null): DraftParts {
  const sides = (["si", "bl"] as const)
    .map((side) => ({ side, doc: report.documents[side] }))
    .filter((x): x is { side: Side; doc: DocumentReport } => x.doc !== null);
  const present = new Set(sides.filter(({ doc }) => doc.readable).map(({ doc }) => doc.doc_type));
  const needed = [
    ...(present.has("SHIPPING_INSTRUCTION") ? [] : [SIDE_NAMES.si]),
    ...(present.has("BILL_OF_LADING") ? [] : [SIDE_NAMES.bl]),
  ];
  const askFor = joinAnd(needed.length ? needed : [SIDE_NAMES.si, SIDE_NAMES.bl]);

  if (reviewReason === "missing_attachment") {
    if (!sides.length) {
      return {
        situation: "attachments_missing",
        greeting: GREETING,
        context: "Unfortunately, no attachments reached us with it.",
        facts: ["  - Attachments received: none."],
        action:
          "Could you please re-send it with both the Shipping Instruction and the draft Bill of Lading attached?",
        closing: "Thank you.",
      };
    }
    return {
      situation: "document_missing",
      greeting: GREETING,
      context: "We need both the Shipping Instruction and the draft Bill of Lading for the check, and only one came through.",
      facts: [
        ...sides.map(({ doc }) => `  - Received: ${capitalise(describeDoc(doc))} (${fileName(doc)}).`),
        ...needed.map((name) => `  - Still needed: ${name}.`),
      ],
      action: `Could you please send the ${askFor} so we can compare the two?`,
      closing: "Thank you.",
    };
  }

  if (reviewReason === "unreadable") {
    const unread = sides.filter(({ doc }) => !doc.readable);
    const scanned = unread.filter(({ doc }) => doc.unreadable_reason === "no_text_layer");
    const broken = unread.filter(({ doc }) => doc.unreadable_reason !== "no_text_layer");
    const scanLines = scanned.map(
      ({ side, doc }) => `  - ${capitalise(SIDE_NAMES[side])} (${fileName(doc)}): a scanned image, which we read by hand.`,
    );
    if (broken.length) {
      // "Export it again" is advice for a damaged file. A file that never
      // arrived, or one too large or of a type we cannot read, is not fixed
      // by re-exporting it, so the hint is only given where it helps.
      const damaged = broken.every(({ doc }) => ["corrupt", "empty_file"].includes(doc.unreadable_reason ?? ""));
      return {
        situation: "file_unopenable",
        greeting: GREETING,
        context:
          broken.length === 1
            ? "We could not open one of the attachments, so the check is on hold."
            : "We could not open some of the attachments, so the check is on hold.",
        facts: [
          ...broken.map(
            ({ side, doc }) =>
              `  - ${capitalise(SIDE_NAMES[side])} (${fileName(doc)}): ` +
              `${UNREADABLE_TEXT[doc.unreadable_reason ?? ""] ?? "we could not read the file"}.`,
          ),
          ...scanLines,
        ],
        action:
          `Could you please send a fresh copy of the ${joinAnd(broken.map(({ side }) => SIDE_NAMES[side]))}?` +
          (damaged ? " Exporting it again from the original usually fixes this; forwarding the same file will not." : ""),
        closing: "Thank you.",
      };
    }
    if (scanned.length) {
      // A scan is legible to a person, so asking for it again only gets the
      // same image back. This reply holds the thread while someone reads it;
      // the result goes out in a second email. The model's transcript of the
      // scan is never quoted here: on email_512 it read "AL GURG" as "ALGURG"
      // at 0.95 confidence.
      return {
        situation: "scanned_copies",
        greeting: GREETING,
        context:
          scanned.length === 1
            ? "One of the documents came through as a scanned image, which we check by hand rather than automatically."
            : "The documents came through as scanned images, which we check by hand rather than automatically.",
        facts: scanLines,
        action:
          `There is no need to re-send ${scanned.length === 1 ? "it" : "them"}. ` +
          "We will check manually and come back to you with the result.",
        closing: "Thank you for your patience.",
      };
    }
    // Readable files, but a value that differs only in scan-confusable
    // characters: a question about that value, not about a file.
    const asked = valuesToConfirm(report);
    if (asked) return asked;
  }

  if (reviewReason === "wrong_doc_type") {
    return {
      situation: "wrong_document",
      greeting: GREETING,
      context: "One of the attachments is not the document we need for this check.",
      facts: [
        ...sides.map(({ doc }) => `  - Received: ${capitalise(describeDoc(doc))} (${fileName(doc)}).`),
        ...needed.map((name) => `  - Still needed: ${name}.`),
      ],
      action: `Could you please send the ${askFor} so we can compare the two?`,
      closing: "Thank you.",
    };
  }

  if (reviewReason === "missing_value") {
    const asked = valuesToConfirm(report);
    if (asked) return asked;
  }

  // Nothing the customer can act on is known (for example, every open field
  // is one whose label we did not recognise): say a person is on it and ask
  // for nothing, rather than guess at a request that may be the wrong one.
  return {
    situation: "review_generic",
    greeting: GREETING,
    context: "We were not able to complete the check automatically, and a member of our team is looking at it.",
    facts: [],
    action: "We will come back to you shortly.",
    closing: "Thank you for your patience.",
  };
}

/**
 * Whether a per-case reply makes sense at all. "We compared the draft Bill of
 * Lading against the Shipping Instruction" is only true of a comparison
 * request with both documents in hand. Every other category, and a request to
 * *issue* a draft (which arrives with nothing to compare), gets no draft
 * rather than a false one.
 */
export function canDraftReply(report: CaseReport): boolean {
  if (report.category !== "BL_COMPARISON") return false;
  const status = report.effective?.status ?? report.status;
  if (status !== "OK") return true;
  return Boolean(report.documents.si && report.documents.bl && report.fields.length);
}

/** Changes whenever the outcome a draft is built from changes (a review, a
 *  correction, a re-check), so a caller can key the panel on it and an open
 *  draft never goes on describing the outcome it replaced. */
export function replyDraftKey(report: CaseReport): string {
  const e = report.effective ?? report;
  return [
    report.email_id,
    e.status,
    e.review_reason ?? "",
    [...e.defect_fields].sort().join(","),
    report.recheck?.count ?? 0,
  ].join("|");
}

/**
 * A plain-text reply draft built entirely from data already in the report —
 * no extra API call, no model call. This is a formatting convenience for an
 * operator, not a generated decision: every figure it quotes is the field
 * extraction already shown on the page. A person sends it, from their own
 * mail client (`mailtoHref`); Sentinel never does.
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
 * Returns `{subject, body, parts}` rather than one flat string so a caller can
 * feed either half to a `mailto:` link without parsing a "Subject: ..." line
 * back out of it, and so the optional wording pass can rewrite the greeting
 * and closing without ever being handed anything else.
 */
export function buildReplyDraft(report: CaseReport, reference = report.email_id): ReplyDraft {
  const status = report.effective?.status ?? report.status;
  const reviewReason = report.effective?.review_reason ?? report.review_reason;
  const defectFields = report.effective?.defect_fields ?? report.defect_fields;

  let parts: DraftParts;
  let fallbackSubject: string;

  if (status === "OK") {
    fallbackSubject = "SI/BL checked, no discrepancy";
    parts = {
      situation: "no_discrepancy",
      greeting: GREETING,
      context: "We compared the draft Bill of Lading against the Shipping Instruction across all seven fields we check.",
      facts: [],
      action: "No mismatch was found.",
      closing: "Thank you.",
    };
  } else if (status === "NEEDS_REVIEW") {
    fallbackSubject = "action needed before we can check this";
    parts = reviewParts(report, reviewReason);
  } else {
    fallbackSubject = "discrepancy found between SI and draft BL";
    parts = {
      situation: "discrepancy",
      greeting: GREETING,
      context: "We compared the draft Bill of Lading against the Shipping Instruction and found fields that do not match.",
      facts: report.fields
        .filter((f) => defectFields.includes(f.field))
        .map((f) => `  - ${label(f.field)}: SI says "${f.si.raw ?? "?"}", draft BL says "${f.bl.raw ?? "?"}"`),
      action: "Could you please confirm which value is correct so we can finalise the Bill of Lading?",
      closing: "Thank you.",
    };
  }

  return { subject: replySubject(report, reference, fallbackSubject), body: assembleBody(parts), parts };
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
 *  /compare upload, which has no inbox record to read a sender from).
 *  `to` may already be a comma-joined list (RFC 6068 allows it) — the
 *  pattern-level draft below passes several addresses this way.
 *
 *  Percent-encoded by hand, not with URLSearchParams: that writes a space as
 *  "+", which is form encoding, and a mail client reads a mailto: URL by
 *  RFC 6068, where "+" is a literal plus. Outlook put "Thank+you+for..." in
 *  the body of every draft. RFC 6068 also wants line breaks as CRLF, and each
 *  address encoded on its own so the commas between them stay separators. */
export function mailtoHref(to: string | undefined | null, draft: ReplyDraft): string | undefined {
  if (!to) return undefined;
  const recipients = to
    .split(",")
    .map((a) => a.trim())
    .filter(Boolean)
    .map(encodeURIComponent)
    .join(",");
  if (!recipients) return undefined;
  const enc = (s: string) => encodeURIComponent(s.replace(/\r?\n/g, "\r\n"));
  return `mailto:${recipients}?subject=${enc(draft.subject)}&body=${enc(draft.body)}`;
}

/**
 * One summary email for a whole pattern — "N cases from this shipper all
 * mismatch on the same field" — instead of N near-identical ones.
 * docs/ROADMAP.md's own backlog line for the pattern view already framed
 * the value this way; this is the same idea applied to the reply-draft
 * feature next to it, not a new one.
 *
 * `emailIds` are Sentinel's own internal case references, the same
 * reference `buildReplyDraft` falls back to when a case has no subject of
 * its own -- kept for consistency with the single-case draft rather than
 * invented fresh here, not because it is necessarily the ideal thing to show
 * an external reader.
 */
export function buildPatternDraft(shipper: string, fieldLabel: string, emailIds: string[]): ReplyDraft {
  return {
    subject: `Recurring mismatch: ${fieldLabel} across ${emailIds.length} shipments`,
    body: [
      "Hello,",
      "",
      `Across ${emailIds.length} recent shipments from ${shipper}, we've found the same field does not ` +
        `match between the Shipping Instruction and the draft Bill of Lading: ${fieldLabel}.`,
      "",
      "Affected bookings:",
      ...emailIds.map((id) => `  - ${id}`),
      "",
      "Could you help us understand whether this is a process issue on your end? Flagging it once, rather " +
        "than case by case, in case it points at something worth fixing at the source.",
      "",
      "Regards,",
    ].join("\n"),
  };
}
