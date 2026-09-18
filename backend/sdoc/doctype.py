"""Document-type classification — what a file *is*, not what it is called.

The filename is a hint and nothing more.  In this inbox an attachment called
``email_501_BL.txt`` turns out to be a Commercial Invoice, and the pipeline has
to notice: comparing a Shipping Instruction against an invoice produces seven
"mismatches" that are really one wrong attachment.  That case ends in
``NEEDS_REVIEW / wrong_doc_type``, never in ``MISMATCH``.

Why a weighted scorer and not a chain of ``if`` statements
----------------------------------------------------------
Every individual signal in these documents lies at least once:

* the PDF Shipping Instruction is **titled** ``BILL OF LADING INSTRUCTION``;
* that same PDF SI prints ``B/L NUMBER:`` in its header, so "carries a B/L
  number" does *not* separate a BL from an SI in this set;
* the .xlsx SI says ``BL INSTRUCTION`` while the .xlsx BL says
  ``BILL OF LADING`` — one word apart, in a cell, not a title bar;
* the misfiled Commercial Invoice contains the literal words
  ``SHIPPING INSTRUCTION`` (inside a "this is not a shipping instruction"
  disclaimer), so a bare substring test on the body flips it to DOC_SI.

A scorer lets each signal contribute what it is actually worth, lets the
strong evidence (the title block) outvote the weak evidence (a field label
that both templates share), and — because every fired signal is recorded —
lets a human see *why* a document was called what it was called.

The key disambiguation
----------------------
**If the header says INSTRUCTION, it is an SI, even when it also says BILL OF
LADING.**  An SI is an instruction to a carrier to *produce* a BL, so its title
legitimately names the document it asks for.  Getting this backwards is silent
and expensive: the reference document and the document under test swap places,
and every planted discrepancy is then read in the wrong direction.

Deliberately not used: the generator prints a ``*** THIS IS A COMMERCIAL
INVOICE - NOT A SHIPPING INSTRUCTION ***`` banner at the foot of the misfiled
attachments.  Keying off that banner would score well here and fail on any
real document, so the title block and the field vocabulary carry the decision
and the banner is ignored — it sits outside the title zone and matches no
label pattern.

No network, no model, no API key: this is regex over normalised text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import labels
from .normalize import basic
from .schema import (
    DOC_BL,
    DOC_COO,
    DOC_INVOICE,
    DOC_PACKING_LIST,
    DOC_SI,
    DOC_UNKNOWN,
    ParsedDoc,
)

# The types this module can score. DOC_UNKNOWN is an outcome, not a candidate.
DOC_TYPES: tuple[str, ...] = (
    DOC_SI,
    DOC_BL,
    DOC_INVOICE,
    DOC_PACKING_LIST,
    DOC_COO,
)

# Types that can never be half of a comparable {SI, BL} pair.
NON_PAIR_TYPES: frozenset[str] = frozenset({DOC_INVOICE, DOC_PACKING_LIST, DOC_COO})

# --------------------------------------------------------------------------
# Tuning constants — all of the classifier's judgement lives here.
# --------------------------------------------------------------------------
# How far into the document the "title block" reaches, counted in non-empty
# lines. The .xlsx templates put the exporter's name on row 1 and the document
# title on row 2, and the .txt/.pdf/.docx templates put the title on line 1
# followed by the reference numbers, so a handful of lines covers every layout
# we have seen. Keeping the zone small is what stops a disclaimer or a remarks
# paragraph deep in the body from being read as a title.
TITLE_ZONE_LINES = 6

# A title is worth far more than any single field label, because the field
# vocabulary is deliberately shared between the SI and the BL templates.
TITLE_WEIGHT = 5.0

# A winner needs enough absolute evidence to be worth believing...
MIN_SCORE = 2.0
# ...and enough daylight over the runner-up that the two are not a coin toss.
MIN_MARGIN = 1.5

# A heuristic never earns absolute certainty, however clean the evidence.
MAX_CONFIDENCE = 0.99

# Above this, downstream stages may act on the type (e.g. declare a document
# the wrong kind entirely). Below it we stay quiet and let the reading /
# escalation paths handle the case.
CONFIDENT = 0.5


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DocTypeResult:
    """What the classifier decided, and the evidence it decided it on."""

    doc_type: str
    confidence: float
    signals: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Title signals
#
# Matched as a prefix of a normalised line inside the title zone. Longest
# phrase first, so "BILL OF LADING INSTRUCTION" is decided before the
# "BILL OF LADING" it contains — that single ordering is the whole SI/BL trap.
#
# Phrases are written in normalize.basic() form (upper case, ASCII
# alphanumerics, single spaced), which is also how the document's lines are
# normalised before matching. That is what lets the .docx heading
# "BILL OF LADING (DRAFT)" and the .xlsx cell "BL INSTRUCTION\t3658202970"
# be compared with the same table.
# --------------------------------------------------------------------------
_TITLE_PHRASES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            # --- Shipping Instruction ---------------------------------------
            ("SHIPPING INSTRUCTION", DOC_SI),
            ("SHIPPING INSTRUCTIONS", DOC_SI),
            ("SHIPPERS INSTRUCTION", DOC_SI),
            # The PDF template's own title. It names the document it asks the
            # carrier to produce; it is not itself a bill of lading.
            ("BILL OF LADING INSTRUCTION", DOC_SI),
            ("BILL OF LADING INSTRUCTIONS", DOC_SI),
            # The .xlsx template abbreviates the same heading in a cell.
            ("BL INSTRUCTION", DOC_SI),
            ("B L INSTRUCTION", DOC_SI),
            # --- Bill of Lading ----------------------------------------------
            ("DRAFT BILL OF LADING", DOC_BL),
            ("OCEAN BILL OF LADING", DOC_BL),
            ("HOUSE BILL OF LADING", DOC_BL),
            ("BILL OF LADING", DOC_BL),
            # --- the three documents that must never be treated as a BL ------
            # Bare "INVOICE" is excluded on purpose: "Invoice No." is a line in
            # the invoice's own header and would match it as a second title.
            ("COMMERCIAL INVOICE", DOC_INVOICE),
            ("PROFORMA INVOICE", DOC_INVOICE),
            ("TAX INVOICE", DOC_INVOICE),
            ("PACKING LIST", DOC_PACKING_LIST),
            ("CERTIFICATE OF ORIGIN", DOC_COO),
        ),
        key=lambda pair: -len(pair[0]),
    )
)

_INSTRUCTION_RE = re.compile(r"\bINSTRUCTIONS?\b")


# --------------------------------------------------------------------------
# Field-vocabulary signals
#
# Each is worth much less than a title: individually they are suggestive, but
# a document that carries four or five of them is that kind of document even
# if its heading was lost in conversion.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class _Signal:
    name: str                       # what the reviewer sees
    doc_type: str
    weight: float
    pattern: re.Pattern[str]
    line_start: bool = True         # anchored label, vs. free text anywhere


_SIGNALS: tuple[_Signal, ...] = (
    # ---- Bill of Lading ---------------------------------------------------
    # Weak on purpose. Every .pdf SI in this set pre-prints "B/L NUMBER:" in
    # its header — the carrier's reference exists before the draft does — so a
    # B/L number is evidence of a BL only in the absence of a louder signal.
    _Signal(
        "label:B/L No.",
        DOC_BL,
        0.9,
        re.compile(r"^(?:B L|BL|BILL OF LADING)\s+(?:NO|NOS|NUMBER|NBR)\b"),
    ),

    # ---- Commercial Invoice ----------------------------------------------
    # None of these words appear anywhere in the 187 genuine SI/BL attachments;
    # they are the invoice's own commercial vocabulary. "Seller" and "Buyer"
    # are anchored to the start of a line because the SI label
    # "Shipper (Principal or Seller)" contains the word Seller.
    _Signal("label:Invoice No.", DOC_INVOICE, 1.2,
            re.compile(r"^INVOICE\s+(?:NO|NOS|NUMBER|DATE)\b")),
    _Signal("label:Seller", DOC_INVOICE, 0.8, re.compile(r"^SELLER\b")),
    _Signal("label:Buyer", DOC_INVOICE, 0.8, re.compile(r"^BUYER\b")),
    _Signal("label:Total Amount", DOC_INVOICE, 1.0,
            re.compile(r"^TOTAL\s+AMOUNT\b")),
    _Signal("label:Payment Terms", DOC_INVOICE, 1.0,
            re.compile(r"^PAYMENT\s+TERMS?\b")),
    _Signal("label:Incoterms", DOC_INVOICE, 1.0, re.compile(r"^INCOTERMS?\b")),
    # A price column only ever belongs to a commercial document; a transport
    # document states quantities and weights, never money per unit.
    _Signal("text:Unit Price", DOC_INVOICE, 0.8,
            re.compile(r"\bUNIT\s+PRICE\b"), line_start=False),

    # ---- Packing List -----------------------------------------------------
    # The packing list is a carton table, so its identifying vocabulary sits in
    # a column header mid-line rather than at the start of a label line.
    _Signal("text:Carton No.", DOC_PACKING_LIST, 1.5,
            re.compile(r"\bCARTONS?\s+(?:NO|NOS|NUMBER)\b"), line_start=False),
    _Signal("text:Dimensions", DOC_PACKING_LIST, 1.0,
            re.compile(r"\bDIMENSIONS?\b"), line_start=False),
    # Net weight next to gross weight is the packing list's signature. It is
    # the weakest of the three: a Shipping Instruction may also quote a net
    # weight (several in this set do, as a blank "NET WEIGHT: ___ MTS" line).
    _Signal("text:Net Wt", DOC_PACKING_LIST, 0.5,
            re.compile(r"\bNET\s+(?:WT|WEIGHT)\b"), line_start=False),

    # ---- Certificate of Origin -------------------------------------------
    _Signal("label:Certificate No.", DOC_COO, 1.2,
            re.compile(r"^CERTIFICATES?\s+(?:NO|NOS|NUMBER)\b")),
    _Signal("label:Country of Origin", DOC_COO, 1.2,
            re.compile(r"^COUNTRY\s+OF\s+ORIGIN\b")),
    _Signal("label:Issuing Authority", DOC_COO, 1.0,
            re.compile(r"^ISSUING\s+AUTHORITY\b")),
    # A CoO names an "Exporter" where an SI names a "Shipper/Exporter", so the
    # anchor at the start of the line is doing the real work here.
    _Signal("label:Exporter", DOC_COO, 0.5, re.compile(r"^EXPORTERS?\b")),
)

# Port vocabulary is taken from labels.py rather than restated here, so that a
# port synonym added there ("Discharge Port", "POL", ...) is automatically
# understood by this module too.
_PORT_PHRASES: tuple[str, ...] = tuple(
    sorted(
        {
            basic(variant)
            for fname in ("port_of_loading", "port_of_discharge")
            for variant in labels.SYNONYMS[fname]
            if basic(variant)
        },
        key=len,
        reverse=True,
    )
)
_PORT_RE = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(p) for p in _PORT_PHRASES)
)
# Vessel labels live in labels.IGNORE_LABELS because they are never compared;
# here we only need to know whether the document mentions carriage at all.
_VESSEL_RE = re.compile(r"\b(?:VESSEL|VOYAGE|VOY|OCEAN CARRIER|EXPORT CARRIER)\b")

# "Booking Ref", "BOOKING NO." — present on an SI before any B/L exists.
_BOOKING_RE = re.compile(r"^BOOKING\s+(?:REF|REFERENCE|NO|NOS|NUMBER)\b")

# Structural signal names, kept as constants so tests and the UI agree.
SIG_NO_BL_NUMBER = "structure:booking reference, no B/L number"
SIG_NO_TRANSPORT = "structure:no port or vessel details"


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def _normalised_lines(text: str) -> list[str]:
    """Document lines in normalize.basic() form, decoration dropped.

    Working line by line (rather than on one flattened blob) is what makes an
    anchored label signal possible: "Shipper (Principal or Seller)" must not
    count as the invoice's "Seller:" label, and only the line boundary tells
    them apart. Lines that normalise to nothing — the ``=====`` rule the
    templates draw under their title, blank rows in a sheet — disappear, so the
    title zone is counted in real content.
    """
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = basic(raw)
        if line:
            out.append(line)
    return out


def _title_signal(lines: list[str]) -> Optional[tuple[str, str]]:
    """The document's own heading, as (signal_name, doc_type), if it has one.

    Only the first title-shaped line in the title zone counts: a document has
    one title, and the .xlsx layout proves the title is not always line 1.
    """
    zone = lines[:TITLE_ZONE_LINES]

    # THE KEY DISAMBIGUATION. An SI is an instruction to produce a BL, so an
    # SI header may legitimately contain the words "BILL OF LADING". The
    # reverse is never true: a bill of lading does not instruct anyone. So if
    # the word INSTRUCTION appears anywhere in the header block, BL credit for
    # that header is redirected to SI. Scoped to the title zone on purpose —
    # the misfiled Commercial Invoice says "NOT A SHIPPING INSTRUCTION" in its
    # footer, and a whole-document substring test would be fooled by it.
    instructional = any(_INSTRUCTION_RE.search(line) for line in zone)

    for line in zone:
        for phrase, doc_type in _TITLE_PHRASES:
            if line == phrase or line.startswith(phrase + " "):
                if doc_type == DOC_BL and instructional:
                    return f"title:{phrase}+INSTRUCTION", DOC_SI
                return f"title:{phrase}", doc_type
    return None


def score_document(text: str) -> DocTypeResult:
    """Classify raw document text. Pure — no I/O, no mutation, no network.

    >>> score_document("SHIPPING INSTRUCTION\\nBooking Ref: X1").doc_type
    'SHIPPING_INSTRUCTION'
    >>> score_document("BILL OF LADING INSTRUCTION\\nB/L NUMBER: X").doc_type
    'SHIPPING_INSTRUCTION'
    """
    lines = _normalised_lines(text)
    scores: dict[str, float] = {t: 0.0 for t in DOC_TYPES}
    signals: list[str] = []
    fired: set[str] = set()

    def award(name: str, doc_type: str, weight: float) -> None:
        # A signal counts once however many lines repeat it: two "Invoice No."
        # lines are one piece of evidence, not two.
        if name in fired:
            return
        fired.add(name)
        signals.append(name)
        scores[doc_type] += weight

    title = _title_signal(lines)
    if title is not None:
        award(title[0], title[1], TITLE_WEIGHT)

    flat = " ".join(lines)
    for sig in _SIGNALS:
        if sig.line_start:
            hit = any(sig.pattern.match(line) for line in lines)
        else:
            hit = bool(sig.pattern.search(flat))
        if hit:
            award(sig.name, sig.doc_type, sig.weight)

    # ---- structural signals ----------------------------------------------
    # An SI is raised against a booking; the B/L number does not exist yet.
    # This only discriminates where the template does not pre-print a B/L
    # number — which is why it is a modest 0.8 and not a decisive rule.
    has_bl_number = "label:B/L No." in fired
    has_booking = any(_BOOKING_RE.match(line) for line in lines)
    if has_booking and not has_bl_number:
        award(SIG_NO_BL_NUMBER, DOC_SI, 0.8)

    # A packing list describes what is inside the cartons; the carriage — ports,
    # vessel, voyage — belongs on the SI and the BL. Absence of transport detail
    # is only meaningful once the carton vocabulary has already appeared,
    # otherwise every short or badly-read document would drift towards
    # PACKING_LIST on the strength of what it does *not* say.
    if "text:Carton No." in fired:
        if not _PORT_RE.search(flat) and not _VESSEL_RE.search(flat):
            award(SIG_NO_TRANSPORT, DOC_PACKING_LIST, 0.8)

    # ---- decide ----------------------------------------------------------
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], DOC_TYPES.index(kv[0])))
    best_type, best_score = ranked[0]
    runner_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - runner_score

    if best_score < MIN_SCORE or margin < MIN_MARGIN:
        # Not enough evidence, or two readings of the same document that we
        # cannot separate. Say so instead of guessing: an UNKNOWN document is
        # handled as a reading problem downstream, and a wrong guess here would
        # silently swap the reference document for the document under test.
        return DocTypeResult(DOC_UNKNOWN, 0.0, signals, scores)

    # Confidence is the share of the winner's score that the runner-up cannot
    # account for: a clean title with nothing arguing back scores ~1.0, while
    # the .pdf SI (title SI 5.0, but a B/L number arguing 0.9 for BL) lands
    # around 0.82 — believable, not certain.
    confidence = min(MAX_CONFIDENCE, margin / best_score)
    return DocTypeResult(best_type, round(confidence, 3), signals, scores)


# --------------------------------------------------------------------------
# Applying it to a document we have read
# --------------------------------------------------------------------------
def classify_document(doc: ParsedDoc) -> DocTypeResult:
    """Classify a ParsedDoc, recording the outcome on the document itself.

    An unreadable document is not a classification failure — it is an
    `unreadable` escalation that another stage owns — so it comes back as
    DOC_UNKNOWN with zero confidence rather than raising.
    """
    if doc is None:                                   # defensive; callers pass a doc
        return DocTypeResult(DOC_UNKNOWN, 0.0, [], {})

    if not doc.readable:
        doc.doc_type = DOC_UNKNOWN
        doc.doc_type_confidence = 0.0
        reason = doc.unreadable_reason or "unreadable"
        _note(doc, f"doc type: not classified ({reason})")
        return DocTypeResult(DOC_UNKNOWN, 0.0, [], {})

    result = score_document(doc.text)
    doc.doc_type = result.doc_type
    doc.doc_type_confidence = result.confidence

    # Keep the note short — the full signal list lives on the result and in the
    # audit report; this is the one line a reviewer skims.
    top = ", ".join(result.signals[:3]) or "no signal"
    _note(doc, f"doc type: {result.doc_type} ({result.confidence:.2f}) via {top}")
    return result


def _note(doc: ParsedDoc, text: str) -> None:
    """Append a note, without repeating one we have already written."""
    if text not in doc.notes:
        doc.notes.append(text)


# --------------------------------------------------------------------------
# Is this pair comparable at all?
# --------------------------------------------------------------------------
def _effective_type(doc: Optional[ParsedDoc]) -> tuple[Optional[str], float]:
    """(doc_type, confidence) for a document, classifying it if need be.

    Never mutates the document and never raises: `pair_problem` is called on
    the escalation path, where an exception would turn a reviewable case into a
    crashed one.
    """
    if doc is None:
        return None, 0.0
    try:
        if not doc.readable:
            return DOC_UNKNOWN, 0.0
        if doc.doc_type and doc.doc_type != DOC_UNKNOWN:
            return doc.doc_type, float(doc.doc_type_confidence or 0.0)
        result = score_document(doc.text)
        return result.doc_type, result.confidence
    except Exception:                                  # pragma: no cover
        return DOC_UNKNOWN, 0.0


def pair_problem(si: Optional[ParsedDoc], bl: Optional[ParsedDoc]) -> Optional[str]:
    """None when {si, bl} is a usable SI+BL pair, else the review reason.

    Returns ``"wrong_doc_type"`` when the sender attached something that can
    never be half of a comparison — a Commercial Invoice, a Packing List, a
    Certificate of Origin — or when both attachments are the same kind of
    document (two SIs, or two BLs), which is the same defect wearing a
    different hat: there is no counterpart to compare against.

    A document we merely could not *recognise* is not reported here. An
    unfamiliar layout is a reading problem — it surfaces as `unreadable` or as
    missing values — and calling it the wrong document type on no evidence
    would cost precision for nothing. So an UNKNOWN-but-readable attachment,
    whose filename role hint is all we have, is left alone.

    A swapped pair (the SI-named file is the BL and vice versa) is *not* a
    problem: the set is still {SI, BL} and the orchestrator can trust the
    content over the filename. That is the whole point of this module.
    """
    try:
        si_type, si_conf = _effective_type(si)
        bl_type, bl_conf = _effective_type(bl)

        # A missing half is `missing_attachment`, decided from the email, not
        # from the documents. Not ours to report.
        if si_type is None or bl_type is None:
            return None

        for doc_type, conf in ((si_type, si_conf), (bl_type, bl_conf)):
            if doc_type in NON_PAIR_TYPES and conf >= CONFIDENT:
                return "wrong_doc_type"

        # Two of the same kind: nothing to compare the document against.
        if (
            si_type == bl_type
            and si_type in (DOC_SI, DOC_BL)
            and si_conf >= CONFIDENT
            and bl_conf >= CONFIDENT
        ):
            return "wrong_doc_type"

        return None
    except Exception:                                  # pragma: no cover
        return None


__all__ = [
    "DocTypeResult",
    "score_document",
    "classify_document",
    "pair_problem",
    "DOC_TYPES",
    "NON_PAIR_TYPES",
    "CONFIDENT",
]
