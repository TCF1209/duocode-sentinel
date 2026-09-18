"""Chunks -> the seven compared fields, each carrying its evidence.

A reader hands us every `Chunk(label, value, locator)` it could recover, in
document order and with no opinion about what any of them mean. This module
turns that into exactly seven `FieldValue`s.

The hard part is not finding a field, it is choosing between several chunks
that all legitimately resolve to the *same* field. A real SI in the set reads:

    CONTAINER NO.        DESCRIPTION  GROSS WEIGHT (KG)     <- table header row
    UJAJ2269312          40'HC PAPERBOARD  23,654           <- per-container row
    ...
    Total Containers:    5 x 40'HC
    TOTAL GROSS WEIGHT:  118,270 KG                         <- the real figure

Taking the first chunk that resolves would report the shipment's gross weight
as one container's 23,654 kg; taking the last would break on a document that
prints a summary block before the table. So every resolved chunk becomes a
scored `Candidate` and the best one wins, with the score and the reason kept
so a reviewer (and the dashboard) can see why the loser lost.

Three rules govern the scoring, and all three come from the documents:

* a value that actually *parses* for its field beats one that does not — a
  gross weight is a positive number, a shipper is a name with letters in it;
* for `gross_weight_kg`, a label containing TOTAL beats one that does not,
  because the per-container column header and the shipment total are labelled
  almost identically ("GROSS WEIGHT (KG)" vs "TOTAL GROSS WEIGHT");
* a blank (`???`, `____MT`, `TBA`) is the weakest candidate but is never
  discarded: it is precisely what makes a case escalate instead of being
  reported as a mismatch (DATA_NOTES §5). Keeping it, with its evidence, is
  how the gate can tell "the document left this empty" apart from "we never
  found this field at all".

Only the entity name is kept, never the address block that follows it
(`normalize.first_segment`): the generator swaps a party name while leaving
the old address in place, so comparing addresses would *mask* the defect
(DATA_NOTES §4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Optional

from .. import labels, normalize
from ..schema import (
    COMPARE_FIELDS,
    NUMERIC_FIELDS,
    Chunk,
    DocFields,
    Evidence,
    FieldValue,
    ParsedDoc,
)

# --------------------------------------------------------------------------
# Scoring weights.
#
# Deliberately far apart rather than finely tuned: each one encodes a
# qualitative statement ("a parseable value always beats an unparseable one"),
# so the gaps must be wide enough that no combination of weaker signals can
# overturn a stronger one.
# --------------------------------------------------------------------------
SCORE_PARSES = 50.0            # the value is usable as this field
SCORE_TOTAL_LABEL = 15.0       # "TOTAL GROSS WEIGHT" vs the table's column header
PENALTY_TABLE_HEADER = -100.0  # the "value" is a row of column headings
PENALTY_BLANK = -80.0          # ??? / ____ / TBA — kept, but only as a last resort

# Evidence is read by a human next to the document; ~120 chars is one line in
# the review queue and still enough to locate the field on the page.
SNIPPET_MAX = 120

# Column headings seen in the container table of the PDF forms. A *value* that
# contains two or more of these is a header row that the column reconstruction
# happened to split as a label/value pair, not a shipping fact. Two are
# required because a genuine value can legitimately contain one of them
# (a goods description, "GROSS WEIGHT" echoed inside a units string).
_TABLE_HEADER_WORDS = (
    "DESCRIPTION",
    "GROSS WEIGHT",
    "NET WEIGHT",
    "CONTAINER NO",
    "MEASUREMENT",
    "MARKS",
    "SEAL NO",
    "PACKAGES",
    "UNIT PRICE",
    "QTY",
)

# A party or a port is a name; it always carries letters. A bare number that
# resolved to one of those slots came from a table cell, not from the form.
_HAS_LETTER = re.compile(r"[A-Z]")

# The shipment total, as opposed to the per-container column header. Matched on
# the normalised label so "TOTAL Gross Weightnn(KGS)" — a real label from the
# set, mangled by the PDF's font — still counts.
_TOTAL_RE = re.compile(r"\bTOTAL\b")


@dataclass
class Candidate:
    """One chunk offered as the value of one field, with its score.

    Exposed by `field_candidates()` for the debug endpoint and the dashboard:
    showing the rejected candidates next to the winner is what lets a reviewer
    confirm in seconds that we read the right line of the document.
    """

    field: str
    chunk: Chunk
    raw: str                                  # first_segment of the chunk value
    normalised: Optional[str] = None
    number: Optional[float] = None
    blank: bool = False
    parsed: bool = False                      # the value is usable as this field
    score: float = 0.0
    reasons: list[str] = dc_field(default_factory=list)
    won: bool = False

    @property
    def order(self) -> int:
        return self.chunk.order

    @property
    def locator(self) -> str:
        return self.chunk.locator

    @property
    def label(self) -> str:
        return self.chunk.label


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def extract_fields(doc: ParsedDoc, doc_role: str) -> DocFields:
    """Read the seven compared fields out of one parsed document.

    `doc_role` is "SI" or "BL" and is stamped into every `Evidence` record, so
    a value can always be traced back to the document it came from.

    The returned `DocFields.fields` always has an entry for every one of
    `COMPARE_FIELDS`. A field we never found comes back as
    `FieldValue(present=False, blank=False, raw=None)` — "we did not find it"
    is information the gate needs, and it is a different state from "the
    document printed this field and left it empty" (`blank=True`).

    An unreadable document (0 bytes, corrupt, image-only scan) yields
    all-absent fields rather than raising: an unreadable attachment is a normal
    state of an ops inbox and must become a review case, not a crash.
    """
    result = DocFields(doc=doc)
    candidates = field_candidates(doc)
    for name in COMPARE_FIELDS:
        ranked = candidates.get(name) or []
        result.fields[name] = _to_field_value(name, ranked[0] if ranked else None,
                                              doc_role)
    return result


def field_candidates(doc: ParsedDoc) -> dict[str, list[Candidate]]:
    """Every chunk that resolved to each field, best first.

    Always returns all seven keys, so a caller can iterate without guarding.
    The list is empty when the document is unreadable or simply does not print
    that field.
    """
    out: dict[str, list[Candidate]] = {name: [] for name in COMPARE_FIELDS}
    if not doc.readable:
        # No chunks to score. The document's own `unreadable_reason` is what
        # the intake stage escalates on.
        return out

    for chunk in doc.chunks:
        name = labels.resolve(chunk.label)
        if name is None or name not in out:
            continue                      # not one of the seven, or ignored
        out[name].append(_score(name, chunk))

    for name, cands in out.items():
        # Tie-break by document order: the form's header block comes before the
        # container table, so the earlier chunk is the field itself whenever
        # two candidates are otherwise indistinguishable.
        cands.sort(key=lambda c: (-c.score, c.chunk.order))
        if not cands:
            continue
        best = cands[0]
        best.won = True
        best.reasons.append(f"won: best of {len(cands)} candidate(s)")
        for loser in cands[1:]:
            loser.reasons.append(
                f"lost to {best.chunk.label!r} at {best.chunk.locator} "
                f"(score {best.score:g} vs {loser.score:g})"
            )
    return out


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def _score(name: str, chunk: Chunk) -> Candidate:
    """Turn one resolved chunk into a scored candidate for `name`."""
    # Only the first segment is ever the value: the entity name is the first
    # line, and .xlsx packs "NAME | ADDRESS" into a single cell.
    raw = normalize.first_segment(chunk.value)
    normalised, number = normalize.normalise_field(name, raw)
    blank = normalize.is_blank(raw)
    parsed = _parses(name, normalised, number)

    cand = Candidate(field=name, chunk=chunk, raw=raw, normalised=normalised,
                     number=number, blank=blank, parsed=parsed)

    if parsed:
        cand.score += SCORE_PARSES
        cand.reasons.append(f"+{SCORE_PARSES:g} value parses as {name}")
    else:
        cand.reasons.append(f"0 value does not parse as {name}")

    if name == "gross_weight_kg" and _TOTAL_RE.search(normalize.basic(chunk.label)):
        # The per-container rows and the shipment total sit under near-identical
        # labels; only the total is the shipment's gross weight.
        cand.score += SCORE_TOTAL_LABEL
        cand.reasons.append(f"+{SCORE_TOTAL_LABEL:g} label names a TOTAL")

    if _looks_like_table_header(raw):
        cand.score += PENALTY_TABLE_HEADER
        cand.reasons.append(f"{PENALTY_TABLE_HEADER:g} value is a table header row")

    if blank:
        # Not a discrepancy — an escalation. Kept so the gate can report
        # missing_value with the evidence attached (DATA_NOTES §5).
        cand.score += PENALTY_BLANK
        cand.reasons.append(f"{PENALTY_BLANK:g} value is blank/placeholder")

    return cand


def _parses(name: str, normalised: Optional[str], number: Optional[float]) -> bool:
    """Is this value usable as this field?

    Numeric fields need a number `normalize` was willing to produce (it already
    rejects an absurd container count and a non-positive weight). Parties and
    ports need a canonical form with letters in it — "23,654" canonicalises to
    something non-empty but is a table cell, not a company.
    """
    if name in NUMERIC_FIELDS:
        return number is not None
    return bool(normalised) and bool(_HAS_LETTER.search(normalised))


def _looks_like_table_header(raw: str) -> bool:
    """True when the "value" is really a row of column headings.

    In the two-column PDF forms the container table's heading row reconstructs
    as e.g. label "CONTAINER NO." / value "DESCRIPTION GROSS WEIGHT (KG)".
    `labels.py` already ignores the label side; this guards the value side for
    any layout where the split lands differently.
    """
    key = normalize.basic(raw)
    if not key:
        return False
    return sum(1 for word in _TABLE_HEADER_WORDS if word in key) >= 2


# --------------------------------------------------------------------------
# Building the result
# --------------------------------------------------------------------------
def _to_field_value(name: str, best: Optional[Candidate],
                    doc_role: str) -> FieldValue:
    if best is None:
        # Never found. Distinct from blank: the document did not print this
        # field at all (a Packing List has no ports, for instance).
        return FieldValue(field=name)

    return FieldValue(
        field=name,
        raw=best.raw,
        normalised=best.normalised,
        number=best.number,
        # "Usable" means non-blank *and* parseable. A value we could not read
        # is an escalation, exactly like a blank one — never a mismatch.
        present=best.parsed and not best.blank,
        blank=best.blank,
        evidence=Evidence(
            doc_role=doc_role,
            locator=best.chunk.locator,
            label=best.chunk.label,
            snippet=_snippet(best.chunk),
        ),
        extractor="rule",
    )


def _snippet(chunk: Chunk) -> str:
    """The raw "label: value" text, on one line, short enough to display.

    Whitespace is collapsed because a PDF value carries its address block on
    several lines; the reviewer needs a line they can match against the page,
    not a faithful reproduction of the layout.
    """
    # `is not None` rather than a truth test: .xlsx hands us real numbers, and
    # a legitimate 0 must still be shown to the reviewer.
    has_value = chunk.value is not None and str(chunk.value).strip() != ""
    text = f"{chunk.label}: {chunk.value}" if has_value else f"{chunk.label}:"
    flat = " ".join(str(text).split())
    if len(flat) <= SNIPPET_MAX:
        return flat
    return flat[: SNIPPET_MAX - 3].rstrip() + "..."


__all__ = ["Candidate", "extract_fields", "field_candidates", "SNIPPET_MAX"]
