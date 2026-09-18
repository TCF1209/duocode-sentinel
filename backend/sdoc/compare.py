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
        compare_field(field, _side_of(si, field), _side_of(bl, field))
        for field in COMPARE_FIELDS
    ]


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
    "compare_field",
    "defect_fields",
    "uncomparable_fields",
    "summarise",
    "NO_MISMATCH_TEXT",
    "UNCOMPARABLE_REASONS",
    "WEIGHT_TOLERANCE_KG",
]
