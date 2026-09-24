"""SI ↔ BL comparison — the stage that decides whether a draft BL is wrong.

The Shipping Instruction is the *reference*: it is what the shipper told us to
put on the bill of lading.  The draft BL is the *document under test*.  So a
difference is always phrased "SI says X, BL says Y", and a field we cannot read
on either side is never reported as a difference.

Three verdicts, and the third one is the important one:

    MATCH          both sides present and canonically equal
    MISMATCH       both sides present and canonically different -> a real defect
    UNCOMPARABLE   at least one side is missing, blank or unparseable

`UNCOMPARABLE` exists because a blank is not a discrepancy.  A BL whose
consignee reads `???` is not *wrong*, it is *unknown*; reporting MISMATCH there
is a false alarm that costs precision and, worse, teaches an operator to
distrust the tool.  Those cases become `NEEDS_REVIEW` upstream, carrying the
evidence on both sides so a human can settle them in seconds.

Two rules here are non-negotiable, and both come from `docs/DATA_NOTES.md` §4:

* **Values are compared with exact equality after canonicalisation, never with
  a similarity score.**  The entity pools contain deliberately near-identical
  names — `APRIL FINE PAPER TRADING` vs `APRIL FINE PAPER TRADING (MIDDLE EAST)
  FZE`, `NANTONG, CHINA` vs `RUGAO/NANTONG/SHANGHAI, CHINA`.  Those are
  different parties and different ports.  Any threshold loose enough to merge
  `KPP-ANTALIS (SINGAPORE) PTE. LTD.` with `KPP-ANTALIS SINGAPORE` also merges
  those, and a planted defect vanishes.  Fuzzy matching belongs in `labels.py`,
  where it decides what a *label* means, never here, where we decide what a
  *value* is.
* **Canonicalisation lives in `normalize.py`.**  This module chooses which
  normaliser applies to which field and nothing else; it does not know how a
  legal suffix or a UN/LOCODE is stripped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable, Optional

from . import normalize
from .schema import (
    COMPARE_FIELDS,
    MATCH,
    MISMATCH,
    NUMERIC_FIELDS,
    PARTY_FIELDS,
    PORT_FIELDS,
    UNCOMPARABLE,
    DocFields,
    FieldComparison,
    FieldValue,
)

# --------------------------------------------------------------------------
# Public constants
# --------------------------------------------------------------------------
#: Exact wording the problem statement asks for when a pair is clean.
NO_MISMATCH_TEXT = "No mismatch detected."

#: Why a field could not be compared. One of these, never a free-text string,
#: so the dashboard can group escalations and the scorer stays stable.
UNCOMPARABLE_REASONS: tuple[str, ...] = (
    "si_missing",
    "bl_missing",
    "si_blank",
    "bl_blank",
    "si_unparseable",
    "bl_unparseable",
    "ocr_confusable",
)

# Absolute tolerance for gross weight, in kilograms.
#
# Deliberately absolute and deliberately tiny: it exists only to absorb binary
# floating-point noise (an .xlsx cell arrives as 216950.0, a .txt as
# "216,950 KG"; a document quoting "138 MT" is multiplied by 1000).  It is NOT
# a "close enough" allowance.
#
# A percentage tolerance would be actively harmful here.  The planted weight
# defects in this dataset are ±500 to 2000 kg, and shipments run to ~200,000 kg
# — so even a 1% tolerance (2,000 kg) swallows the whole defect class, and 0.5%
# swallows most of it.  Weight discrepancies also matter more, not less, on
# large shipments: they drive freight charges and container safety limits. So
# the tolerance stays constant and sub-kilogram at every shipment size.
WEIGHT_TOLERANCE_KG = 0.5


# --------------------------------------------------------------------------
# Per-field comparison strategy
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class _Rule:
    """How one field is canonicalised and tested for equality.

    `key` answers "what is the canonical form of this value, and is there one
    at all?" (``None`` means unparseable).  `equal` answers "are these two raw
    values the same shipping fact?" and takes the *raw* text, because some
    comparisons need information that canonicalisation throws away — ports keep
    a UN/LOCODE that `normalize.port()` strips.
    """

    key: Callable[[object], Optional[str]]
    equal: Callable[[object, object], bool]
    number: Optional[Callable[[object], Optional[float]]] = None


# ---- parties ------------------------------------------------------------
def _party_key(raw: object) -> Optional[str]:
    return normalize.org(raw) or None  # type: ignore[arg-type]


def _party_equal(a: object, b: object) -> bool:
    """Exact equality of canonical company names.

    `normalize.org()` already drops legal-form tokens and punctuation, so
    "KPP-ANTALIS (SINGAPORE) PTE. LTD." == "KPP-ANTALIS SINGAPORE". Everything
    the canonical form still distinguishes is a real difference of identity —
    "(MIDDLE EAST) FZE" survives as MIDDLE EAST and must survive, because that
    is a different legal entity in a different country.
    """
    return normalize.org(a) == normalize.org(b)  # type: ignore[arg-type]


# ---- ports --------------------------------------------------------------
def _port_key(raw: object) -> Optional[str]:
    """Canonical port name, or None when the field carries no port name.

    A value that is nothing but a bare UN/LOCODE is treated as unparseable
    rather than resolved to a port: the codes in this set are copied forward
    from the booking and go stale (see `_port_equal`), so a code alone is not
    evidence enough to clear or condemn a BL. That sends the case to a human,
    which is the safe direction.
    """
    return normalize.port(raw) or None  # type: ignore[arg-type]


def _port_equal(a: object, b: object) -> bool:
    """Delegates to `normalize.ports_equal`, which never lets a stale UN/LOCODE
    overrule a name difference.

    That property is what this dataset needs: the planted port defects keep the
    *original* code beside the *new* name — `MOMBASA, KENYA (KEMBA)` in the SI
    against `TUTICORIN, INDIA (KEMBA)` in the BL. Trusting the code would clear
    a genuine defect. A substring test would be just as wrong in the other
    direction: `NANTONG, CHINA` is contained in `RUGAO/NANTONG/SHANGHAI, CHINA`
    and they are different load ports.
    """
    return normalize.ports_equal(a, b)  # type: ignore[arg-type]


# ---- numbers ------------------------------------------------------------
def _count_number(raw: object) -> Optional[float]:
    n = normalize.container_count(raw)
    return None if n is None else float(n)


def _count_key(raw: object) -> Optional[str]:
    n = normalize.container_count(raw)
    return None if n is None else str(n)


def _count_equal(a: object, b: object) -> bool:
    """Integer equality on the parsed count — no tolerance at all.

    `normalize.container_count()` takes the first number in the value, so
    "6 x 40'HC" is six containers of forty-foot size, not forty. One container
    more or fewer on a BL is a real defect, so there is nothing to tolerate.
    """
    na, nb = normalize.container_count(a), normalize.container_count(b)
    return na is not None and na == nb


def _weight_key(raw: object) -> Optional[str]:
    n = normalize.gross_weight_kg(raw)
    return None if n is None else f"{n:.0f}"


def _weight_equal(a: object, b: object) -> bool:
    """Numeric equality in kilograms, within `WEIGHT_TOLERANCE_KG`.

    Both sides are converted to kg first, so a document quoting "138 MT"
    compares cleanly against one quoting "138,000 KG".
    """
    na, nb = normalize.gross_weight_kg(a), normalize.gross_weight_kg(b)
    if na is None or nb is None:
        return False
    return abs(na - nb) < WEIGHT_TOLERANCE_KG


_RULES: dict[str, _Rule] = {
    **{f: _Rule(key=_party_key, equal=_party_equal) for f in PARTY_FIELDS},
    **{f: _Rule(key=_port_key, equal=_port_equal) for f in PORT_FIELDS},
    "container_count": _Rule(key=_count_key, equal=_count_equal, number=_count_number),
    "gross_weight_kg": _Rule(
        key=_weight_key, equal=_weight_equal, number=normalize.gross_weight_kg
    ),
}

_UNRULED = [f for f in COMPARE_FIELDS if f not in _RULES]
if _UNRULED:  # pragma: no cover - guards a field being added to the schema
    raise RuntimeError(f"compare.py has no rule for: {', '.join(_UNRULED)}")


# --------------------------------------------------------------------------
# Reading one side of a field
# --------------------------------------------------------------------------
_MISSING = "missing"
_BLANK = "blank"
_UNPARSEABLE = "unparseable"
_USABLE = "usable"


def _source(fv: FieldValue) -> object:
    """The text this comparison works from.

    `raw` is the verbatim document text and is the authority, because the
    canonicalisation rules live in `normalize.py` and must be applied here
    consistently rather than inherited from whichever extractor filled the
    field. `normalised` is only a fallback for an extractor (e.g. the LLM path)
    that produces a canonical value with no raw span behind it.
    """
    return fv.raw if fv.raw is not None else fv.normalised


def _assess(field: str, fv: FieldValue) -> tuple[str, Optional[str], Optional[float]]:
    """Classify one side: usable / missing / blank / unparseable.

    The *value* is the authority, not the flags. `blank` is honoured because an
    extractor may know the label was present while the value was a placeholder,
    but `present` is not consulted: a field carrying readable text is compared,
    so an extractor's confidence flag can never turn a clean comparison into an
    escalation on its own.
    """
    rule = _RULES[field]
    raw = _source(fv)

    if fv.blank:
        # the extractor saw the label and a placeholder value ("???", "TBA")
        return _BLANK, None, None
    if raw is None:
        # the label never appeared in this document
        return _MISSING, None, None
    if normalize.is_blank(raw if isinstance(raw, str) else str(raw)):
        return _BLANK, None, None

    key = rule.key(raw)
    if key is None:
        # text is there but carries no usable fact — "Gross Weight: SEE ANNEX"
        return _UNPARSEABLE, None, None

    number = rule.number(raw) if rule.number is not None else None
    return _USABLE, key, number


def _canonical(field: str, fv: FieldValue, key: Optional[str],
               number: Optional[float]) -> FieldValue:
    """A copy of `fv` carrying the canonical form this module actually compared.

    A copy, never a mutation: the caller's `DocFields` belongs to the extractor
    and the report shows both. Filling `normalised` here means the UI can put
    the compared value under the raw one, so a reviewer can see *why* two
    strings that look different were called equal.
    """
    return replace(
        fv,
        field=field,
        normalised=key if key is not None else fv.normalised,
        number=number if number is not None else fv.number,
    )


def _side_of(doc: Optional[DocFields], field: str) -> FieldValue:
    """The field as read from one document, or an empty placeholder.

    Tolerates `None` so an unreadable or absent attachment degrades into seven
    `*_missing` escalations instead of raising inside the pipeline.
    """
    if doc is None:
        return FieldValue(field=field)
    return doc.get(field)


# --------------------------------------------------------------------------
# OCR confusion
#
# `NANT0NG` against `NANTONG` is not a different port. It is the same port
# read by an engine that cannot tell O from 0, and reporting it as a port
# discrepancy sends an operator to look for a routing error that does not
# exist. The adversarial harness measures the cost: injecting one confusable
# character per field into one document of each pair invents **151** defects
# on the dev bundle.
#
# This is the one place in the module that does not decide by exact equality,
# so it is worth being precise about what it is and is not:
#
#   * It never returns MATCH. Two values that differ only on confusable
#     characters are `UNCOMPARABLE`, which becomes `NEEDS_REVIEW` upstream
#     with both readings side by side. The worst case is therefore a
#     *spurious escalation* — a human looks at a pair that was fine — and
#     never a masked defect. That asymmetry is why this does not violate the
#     "no fuzzy value matching" rule in `docs/DATA_NOTES.md` §4: a similarity
#     threshold is dangerous because it can *clear* a BL, and this cannot.
#   * The test is not a distance. Both values must be the same length and
#     every differing position must hold two characters from the **same**
#     confusion class. `215950` vs `218950` is not confusable (5 and 8 are in
#     different classes), and `NANTONG, CHINA` vs `RUGAO/NANTONG/SHANGHAI,
#     CHINA` is not confusable (different lengths).
#   * It is applied to party and port names only. A damaged number does not
#     reach this point: `normalize.digits_contaminated` already makes it
#     unparseable, which is the safer treatment for a field whose defects are
#     small integers.
#
# Checked against the entity pools of all four datasets: of 804 pairs of
# genuinely different parties and ports, **zero** are confusable under this
# test — and none is even within two characters at equal length. The planted
# defects swap whole entities, so there is no defect in this data that this
# veto could swallow. `backend/tests/test_ocr_confusion.py` re-runs that sweep
# over the dev bundle, so a future entity pool that does contain a confusable
# pair fails the suite instead of quietly losing a defect.
#
# There is deliberately no cap on how many characters may differ. A cap would
# add no safety here (nothing is close) and would make the veto miss a badly
# scanned document, which is the case it exists for.
# --------------------------------------------------------------------------
_OCR_CLASSES: tuple[frozenset[str], ...] = (
    frozenset("O0"),
    frozenset("I1"),
    frozenset("S5"),
    frozenset("B8"),
)

#: Fields the veto applies to. Numbers are excluded on purpose — see above.
_OCR_CHECKED = PARTY_FIELDS + PORT_FIELDS


def _same_confusion_class(a: str, b: str) -> bool:
    return any(a in cls and b in cls for cls in _OCR_CLASSES)


def ocr_confusable(a: str, b: str) -> bool:
    """Do these two canonical values differ *only* where OCR confuses glyphs?

    >>> ocr_confusable("NANTONG CHINA", "NANT0NG CHINA")
    True
    >>> ocr_confusable("NANTONG CHINA", "NANTONG INDIA")
    False
    >>> ocr_confusable("APRIL FINE PAPER", "APRIL FINE PAPER MIDDLE EAST")
    False
    """
    if a == b or len(a) != len(b):
        return False
    differing = [(x, y) for x, y in zip(a, b) if x != y]
    return bool(differing) and all(_same_confusion_class(x, y) for x, y in differing)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def compare_field(field: str, si_value: FieldValue, bl_value: FieldValue) -> FieldComparison:
    """Compare one field. Exposed so a reviewer UI can re-run a single row."""
    si_state, si_key, si_num = _assess(field, si_value)
    bl_state, bl_key, bl_num = _assess(field, bl_value)

    si_out = _canonical(field, si_value, si_key, si_num)
    bl_out = _canonical(field, bl_value, bl_key, bl_num)

    if si_state != _USABLE or bl_state != _USABLE:
        # The SI is named first because it is the reference document: with no
        # instruction to check against there is nothing to say about the BL.
        reason = f"si_{si_state}" if si_state != _USABLE else f"bl_{bl_state}"
        return FieldComparison(field=field, verdict=UNCOMPARABLE,
                               si=si_out, bl=bl_out, reason=reason)

    same = _RULES[field].equal(_source(si_value), _source(bl_value))
    if not same and field in _OCR_CHECKED and ocr_confusable(si_key or "", bl_key or ""):
        # Same value, different glyphs. Hand it to a human with both readings
        # rather than calling it a discrepancy or calling it clean.
        return FieldComparison(field=field, verdict=UNCOMPARABLE,
                               si=si_out, bl=bl_out, reason="ocr_confusable")
    return FieldComparison(
        field=field,
        verdict=MATCH if same else MISMATCH,
        si=si_out,
        bl=bl_out,
        reason=None,
    )


def compare_documents(si: DocFields, bl: DocFields) -> list[FieldComparison]:
    """Compare a Shipping Instruction against a draft Bill of Lading.

    Always returns exactly one `FieldComparison` per entry in `COMPARE_FIELDS`,
    in that order, so the report has a fixed shape whatever the documents
    contained — a field neither document mentions is an explicit
    `UNCOMPARABLE/si_missing` row, not a silent absence.
    """
    return [
        compare_field(field, *_repaired(si, bl, field))
        for field in COMPARE_FIELDS
    ]


# --------------------------------------------------------------------------
# Truncation repair
#
# A party name too long for its column wraps onto the next line, and the reader
# cannot tell that continuation apart from the address block that normally
# follows a name. It keeps the first line, so
#
#     Consignee: APRIL FINE PAPER TRADING (MIDDLE
#       EAST) FZE
#
# is read as "APRIL FINE PAPER TRADING (MIDDLE" — which differs from the other
# document and is reported as a discrepancy that does not exist. The
# adversarial harness measures this: wrapping long party names silently
# produced 74 wrong values, and silent wrong values are the one failure mode
# this system must not have.
#
# The repair is deliberately narrow. It fires only when one side's canonical
# value is a strict prefix of the other's, and it completes the short side
# using **that document's own next line**. The completion has to reproduce the
# other side's canonical form exactly, so the repair can recognise that we cut
# a value short — it cannot invent agreement. When the two documents genuinely
# name different parties, the short side's next line is its address block, the
# completion does not match, and the mismatch stands.
# --------------------------------------------------------------------------
_REPAIRABLE = PARTY_FIELDS + PORT_FIELDS
_CONTINUATION_SEARCH = 200

# A locator this specific -- a plain-text or PDF-derived reader's "line N" --
# names the exact line a value came from, so `_extend` can start its search
# there instead of at whatever occurrence of the same text comes first in the
# document. docx's own locators ("para N", "table T row R") do not match this
# and are unaffected: `_extend` falls back to the original whole-document
# search for anything this does not recognise.
_LINE_LOCATOR = re.compile(r"^line (\d+)$")


def _line_start_offset(text: str, line_number: int) -> Optional[int]:
    """Character offset where 1-indexed `line_number` starts in `text`.

    `None` when the locator names a line the text does not have -- stale
    evidence should fall back to the old search, not raise.
    """
    lines = text.split("\n")
    idx = line_number - 1
    if idx < 0 or idx >= len(lines):
        return None
    return sum(len(line) + 1 for line in lines[:idx])


def _repaired(si: DocFields, bl: DocFields, field: str) -> tuple[FieldValue, FieldValue]:
    si_value, bl_value = _side_of(si, field), _side_of(bl, field)
    if field not in _REPAIRABLE:
        return si_value, bl_value

    si_key, bl_key = _RULES[field].key(_source(si_value)), _RULES[field].key(_source(bl_value))
    if not si_key or not bl_key or si_key == bl_key:
        return si_value, bl_value

    if _is_token_prefix(si_key, bl_key):
        return _extend(si, si_value, field, bl_key), bl_value
    if _is_token_prefix(bl_key, si_key):
        return si_value, _extend(bl, bl_value, field, si_key)
    return si_value, bl_value


def _is_token_prefix(short: str, long: str) -> bool:
    """Is `short` the beginning of `long`, whole words only?

    Whole words matter: "KLANG" must not count as a prefix of "KLANGER", or the
    repair would start chasing coincidences.
    """
    a, b = short.split(), long.split()
    return 0 < len(a) < len(b) and b[: len(a)] == a


def _extend(fields: DocFields, value: FieldValue, field: str,
            target_key: str) -> FieldValue:
    """Complete a value from its own document, if that reproduces `target_key`."""
    doc = getattr(fields, "doc", None)
    text = getattr(doc, "text", "") or ""
    if not value.raw or not text:
        return value

    # Anchor on the evidence locator when it names a line, so a value that
    # recurs earlier in the document -- two fields sharing an identical first
    # line, docs/ADVERSARIAL.md §5.4 -- is completed from where it actually
    # is, not from whichever occurrence text.find meets first.
    search_from = 0
    locator = value.evidence.locator if value.evidence else None
    match = _LINE_LOCATOR.match(locator) if locator else None
    if match:
        offset = _line_start_offset(text, int(match.group(1)))
        if offset is not None:
            search_from = offset

    start = text.find(value.raw, search_from)
    if start < 0:
        return value
    tail = text[start + len(value.raw): start + len(value.raw) + _CONTINUATION_SEARCH]
    if not tail[:1].isspace():
        return value                       # the value did not end where we cut it

    for line in tail.splitlines():
        line = line.strip()
        if not line:
            continue
        candidate = f"{value.raw} {line}"
        if _RULES[field].key(candidate) == target_key:
            note = "value was wrapped across two lines; completed from the document"
            evidence = value.evidence
            if evidence is not None:
                evidence = replace(evidence, snippet=f"{evidence.snippet} / {line}")
            key = _RULES[field].key(candidate)
            return replace(value, raw=candidate, normalised=key, evidence=evidence,
                           extractor=f"{value.extractor}+wrap")
        break                              # only the immediately following line
    return value


def defect_fields(comparisons: list[FieldComparison]) -> list[str]:
    """Sorted names of the fields that are genuinely wrong on the BL.

    Only `MISMATCH` counts. An `UNCOMPARABLE` field is an unknown, and calling
    an unknown a defect is the false alarm this pipeline is built to avoid.
    """
    return sorted(c.field for c in comparisons if c.verdict == MISMATCH)


def uncomparable_fields(comparisons: list[FieldComparison]) -> list[str]:
    """Sorted names of the fields that must be settled by a human."""
    return sorted(c.field for c in comparisons if c.verdict == UNCOMPARABLE)


def summarise(comparisons: list[FieldComparison]) -> str:
    """One operator-facing line describing the differences.

    >>> summarise([])
    'No mismatch detected.'

    Reports mismatches only — an uncomparable field is not a difference, and
    the reason it needs a human is carried by the case's `review_reason`, not
    by this line. Fields appear in document order (`COMPARE_FIELDS`), so the
    sentence reads the way the form does.
    """
    differing = [c for c in comparisons if c.verdict == MISMATCH]
    if not differing:
        return NO_MISMATCH_TEXT
    return "; ".join(
        f"{_display_field(c.field)} - SI: {_display_value(c.field, c.si)}"
        f" / BL: {_display_value(c.field, c.bl)}"
        for c in differing
    )


# --------------------------------------------------------------------------
# Presentation helpers
# --------------------------------------------------------------------------
def _display_field(field: str) -> str:
    return field.replace("_", " ")


def _display_value(field: str, fv: FieldValue) -> str:
    """What to show an operator for one side of a difference.

    Numeric fields show the parsed number, so "6 x 40'HC" reads as `6` and the
    line says what actually differs. Text fields show the *raw* entity name
    rather than the canonical form, because "APRIL FINE PAPER TRADING (MIDDLE
    EAST) FZE" is what the reviewer will look for in the document; the
    canonical form is in the report next to it.
    """
    if field in NUMERIC_FIELDS:
        return fv.normalised or "?"
    shown = normalize.first_segment(fv.raw) if fv.raw is not None else ""
    return shown or fv.normalised or "?"


__all__ = [
    "compare_documents",
    "ocr_confusable",
    "compare_field",
    "defect_fields",
    "uncomparable_fields",
    "summarise",
    "NO_MISMATCH_TEXT",
    "UNCOMPARABLE_REASONS",
    "WEIGHT_TOLERANCE_KG",
]
