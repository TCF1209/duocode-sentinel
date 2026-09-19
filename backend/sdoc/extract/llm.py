"""Model-assisted reading of the fields the rules could not resolve.

`extract/fields.py` finds a field by resolving the *label* a chunk was printed
under. That is the right default — it is exact, free, and it never invents —
but it fails in one specific way: a document that words a label in a way
`labels.py` has never seen ("Shipped By", "Total Wt.", "Party to be Advised")
yields an absent field, and the case escalates even though a person looking at
the page would have read the value without hesitating.

This module is that person. It hands the model **one** document and asks it to
read only the fields the rules left empty, verbatim, together with the label
each value was printed under.

Three constraints shape everything below.

**The model reads; it never decides.** It is never asked whether two documents
agree — comparison stays exact and deterministic in `compare.py`. A model asked
"do these match?" answers plausibly even on values it misread, and the
exactness that makes a reported discrepancy trustworthy would be gone.

**A model answer is untrusted until we can point at it in the document.** Every
value the model returns is located as a real span of `doc.text` before it
becomes a `FieldValue`, and the `Evidence` we attach records where it was
actually found — not where the model said it was. A value we cannot locate is
dropped and the field stays absent, which escalates the case. That is the whole
reason the evidence gate exists (`docs/ARCHITECTURE.md` §5), and `_adopt()`
finishes by running the gate's own `trace_value()` so this module cannot drift
away from the check the rest of the pipeline relies on.

**Locating is stricter than "the characters are somewhere on the page".** A
party name that is a *prefix* of what the document prints is a different party
— "APRIL FINE PAPER TRADING" against "APRIL FINE PAPER TRADING (MIDDLE EAST)
FZE" (`docs/DATA_NOTES.md` §4) — so for parties and ports the match must run to
the end of the printed value, not merely start inside it. For the two numeric
fields the match must not sit inside a longer figure, which is how "118,270"
would "trace" against a printed 1,118,270.

With no client, no API key, or an `LLMUnavailable` of any kind, the input comes
back untouched: the deterministic pipeline is the product, and this is a
recovery path bolted to the side of it.
"""
from __future__ import annotations

from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field

from .. import evidence_gate, normalize
from ..llm import LLMClient, LLMUnavailable
from ..schema import (
    COMPARE_FIELDS,
    NUMERIC_FIELDS,
    Chunk,
    DocFields,
    Evidence,
    FieldValue,
    ParsedDoc,
)
from .fields import SNIPPET_MAX

# A shipping form is a page, not a book: the largest attachment in the bundle
# is ~1.4 kB of text. The cap exists so a pathological attachment cannot turn
# one recovery into a large bill, not because real documents approach it.
MAX_DOC_CHARS = 12_000

# Purpose slug for the cost breakdown. Kept distinct from the classifier's so
# the metrics page can say what reading cost as opposed to triage.
PURPOSE = "extract"

# The value region of a line ends at end-of-line or at a pipe: that is exactly
# where `normalize.first_segment()` cuts, and the two must agree or a value we
# accept here would not be the value the comparison later normalises.
_SEGMENT_END = "|"


# --------------------------------------------------------------------------
# What we ask the model for
# --------------------------------------------------------------------------
FieldName = Literal[
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]

# The Literal is what constrains the model's answer to a field we can merge.
# If it ever drifts from the canonical seven, answers would silently become
# unmatchable rather than wrong — so fail loudly at import time instead.
assert set(get_args(FieldName)) == set(COMPARE_FIELDS)


class ReadField(BaseModel):
    """One field as the model read it off the page."""

    field: FieldName = Field(description="Which of the seven fields this is.")
    value: str = Field(
        description=(
            "The value exactly as printed, character for character. Empty "
            "string if the document does not state it."
        )
    )
    label: str = Field(
        description=(
            "The label this value was printed under, copied from the "
            "document. Empty string if it has no label."
        )
    )


class DocumentReading(BaseModel):
    """The model's reading of one document — never a comparison of two."""

    fields: list[ReadField] = Field(
        description="One entry per requested field, in the order requested."
    )


_INSTRUCTIONS = """\
You are a shipping documentation clerk reading ONE document — a Shipping \
Instruction or a draft Bill of Lading. You transcribe what the page says. You \
do not compare documents, you do not judge whether anything is correct, and \
there is no second document.

Rules:
* Copy each value exactly as printed: same spelling, same punctuation, same \
casing, same thousands separators, same units. Do not tidy, translate, expand \
abbreviations, convert units or re-order words.
* For a company or a port, give only the name as printed on the line the label \
introduces. Do not include the street address, city or post code that follows \
it on later lines.
* Also report `label`: the wording of the label the value sits under, copied \
from the document exactly as it is printed there.
* Return an empty string for `value` when the document does not state the \
field, or states it only as a placeholder such as ???, ____, N/A, TBA or TBC. \
An empty answer is a correct and useful answer.
* Never infer a value from another field, from the file name, or from what is \
usual for this trade lane. If it is not printed on this page, it is not there.

Anything you return is checked against the document text before it is used, so \
a guess is worse than an empty string: it is discarded and the case is sent to \
a human either way.
"""

# What each field *is*, in the words a clerk would use. This is what carries
# an unseen label: the model matches on meaning where `labels.py` could not
# match on wording.
_FIELD_BRIEF: dict[str, str] = {
    "shipper": "the party shipping the goods (the exporter or consignor)",
    "consignee": "the party the goods are consigned to (may be printed as "
                 "'to the order of')",
    "notify_party": "the party to be notified when the cargo arrives",
    "port_of_loading": "the port the cargo is loaded at",
    "port_of_discharge": "the port the cargo is discharged at",
    "container_count": "how many containers the shipment is, as printed "
                       "(e.g. \"6 x 40'HC\") — not the box size",
    "gross_weight_kg": "the TOTAL gross weight of the shipment, as printed — "
                       "not one container's row, and not the net weight",
}

_ROLE_BRIEF = {
    "SI": "a Shipping Instruction",
    "BL": "a draft Bill of Lading",
}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def missing_field_names(fields: DocFields) -> list[str]:
    """The fields the rules produced nothing at all for, in canonical order.

    "Nothing at all" is narrower than "not usable", and the narrowness is the
    point:

    * a **blank** (`???`, `____MT`, `TBA`) means the document printed the field
      and left it empty. That is uncertainty the reviewer must resolve, not a
      label we failed to read (CLAUDE.md rule 4), and asking a model to fill it
      invites exactly the invention this architecture exists to prevent;
    * a value that was found but does not **parse** ("SEE ATTACHED MANIFEST"
      under "Total Containers") is also a rule-extracted value; overwriting it
      would break the promise that rules win.

    What is left is the case this module was built for: no chunk in the
    document resolved to this field, because the label was worded in a way
    `labels.py` does not recognise.

    Canonical order keeps the prompt — and therefore the cache key — stable
    across runs for the same document.
    """
    return [name for name in COMPARE_FIELDS if _is_missing(fields.get(name))]


def fill_missing_fields(
    doc: ParsedDoc,
    existing: DocFields,
    doc_role: str,
    *,
    client: Optional[LLMClient] = None,
) -> DocFields:
    """Read the rules' blind spots off `doc` with the model, and merge them in.

    Rule-extracted values always win and are never overwritten: they came from
    a resolved label, they are free, and they are the values the whole system
    was measured on. Only fields in `missing_field_names(existing)` are even
    asked about, and an answer for any other field is discarded.

    Returns the input object unchanged when there is nothing to ask, nobody to
    ask, or the model is unavailable — so a caller can apply this
    unconditionally and a run with no API key behaves exactly as it did before.
    """
    missing = missing_field_names(existing)
    if not missing:
        return existing
    if client is None or not client.available:
        return existing
    if not doc.readable or not (doc.text or "").strip():
        # Nothing to read, and nothing to trace an answer against. An
        # unreadable document is the vision path's problem, not this one's.
        return existing

    try:
        reading = _ask(client, doc, doc_role, missing)
    except LLMUnavailable as exc:
        # No key, no network, a refusal, or the run budget is spent. All of
        # them mean the same thing here: the rules' answer stands and the case
        # escalates on its own merits.
        doc.notes.append(f"llm field extraction unavailable: {exc}")
        return existing

    wanted = set(missing)
    adopted: dict[str, FieldValue] = {}
    for item in reading.fields:
        if item.field not in wanted or item.field in adopted:
            continue                       # not asked for, or answered twice
        value = _adopt(doc, doc_role, item.field, item.value, item.label)
        if value is not None:
            adopted[item.field] = value

    if not adopted:
        return existing

    merged = DocFields(doc=existing.doc, fields=dict(existing.fields))
    merged.fields.update(adopted)
    return merged


# --------------------------------------------------------------------------
# Asking
# --------------------------------------------------------------------------
def _is_missing(value: FieldValue) -> bool:
    # `raw is None` is the extractor's own signal for "no chunk resolved to
    # this field" — distinct from a blank, which carries its placeholder text.
    return value.raw is None and not value.present


def _ask(client: LLMClient, doc: ParsedDoc, doc_role: str,
         missing: list[str]) -> DocumentReading:
    wanted = "\n".join(f"- {name}: {_FIELD_BRIEF[name]}" for name in missing)
    text = (doc.text or "")[:MAX_DOC_CHARS]
    prompt = (
        f"This document is {_ROLE_BRIEF.get(doc_role, 'a shipping document')}.\n"
        f"Read ONLY these fields from it:\n{wanted}\n\n"
        f"--- BEGIN DOCUMENT ---\n{text}\n--- END DOCUMENT ---"
    )
    return client.structured(
        purpose=PURPOSE,
        instructions=_INSTRUCTIONS,
        prompt=prompt,
        schema=DocumentReading,
        # Careful reading of a short page, not a judgement call: "low" buys the
        # attention this needs without paying for reasoning we do not want it
        # doing. "minimal" is for triage.
        reasoning_effort="low",
    )


# --------------------------------------------------------------------------
# Turning an answer into evidence, or throwing it away
# --------------------------------------------------------------------------
def _adopt(doc: ParsedDoc, doc_role: str, name: str, value: str,
           claimed_label: str) -> Optional[FieldValue]:
    """Verify one model answer and build its `FieldValue`, or return None.

    Every rejection leaves the field absent, which escalates the case. That is
    the correct trade: an escalation costs a reviewer a minute, a fabricated
    discrepancy costs the operations desk its trust in every flag after it.
    """
    raw = normalize.first_segment(value).strip()
    if not raw or normalize.is_blank(raw):
        # "The document does not state it" — the answer we asked for, and the
        # rules' absent field already says the same thing. Noted rather than
        # dropped in silence, so the audit trail shows we looked.
        doc.notes.append(f"llm {name}: the document prints no value for it")
        return None

    normalised, number = normalize.normalise_field(name, raw)
    if not _usable(name, normalised, number):
        # Mirrors `fields._parses`: a weight is a positive number, a party is a
        # name with letters in it. A value we cannot use is not a value.
        doc.notes.append(f"llm {name}: rejected, {raw!r} is not usable as {name}")
        return None

    located = _locate(doc, name, raw, claimed_label)
    if located is None:
        # The model produced text this document does not contain. This is the
        # hallucination the architecture is built around: it is dropped here,
        # recorded for the reviewer, and never reaches the comparison.
        doc.notes.append(
            f"llm {name}: rejected, {raw!r} could not be located in {doc.path}"
        )
        return None

    locator, printed_label, snippet = located
    field_value = FieldValue(
        field=name,
        raw=raw,
        normalised=normalised,
        number=number,
        present=True,
        blank=False,
        evidence=Evidence(
            doc_role=doc_role,
            locator=locator,
            # The label the document actually prints at that spot, not the one
            # the model claimed. Evidence is what we verified, never what we
            # were told — and the two are checked against each other below.
            label=printed_label,
            snippet=snippet,
        ),
        extractor="llm",
    )

    # The gate's own check, run here rather than re-implemented, so this module
    # can never accept a value the gate would later veto. Belt and braces: the
    # span search above already guarantees it, and that is exactly why it must
    # keep passing if either side is ever changed.
    if not evidence_gate.trace_value(doc, field_value):
        doc.notes.append(f"llm {name}: rejected, {raw!r} failed the evidence gate")
        return None

    note = f"llm {name}: read {raw!r} at {locator}"
    if claimed_label and normalize.basic(claimed_label) != normalize.basic(printed_label):
        # Not a rejection: the value is in the document at a place we can point
        # at, which is what the gate cares about. But a reviewer should see that
        # the model named a different label than the one printed there.
        note += f" (model called the label {claimed_label!r}, document prints {printed_label!r})"
    doc.notes.append(note)
    return field_value


def _usable(name: str, normalised: Optional[str], number: Optional[float]) -> bool:
    """Is this value usable as this field? Same rule as `fields._parses`.

    Deliberately duplicated rather than imported from a private: the rule is
    two lines, and a model-read value must satisfy the same bar as a
    rule-extracted one without either module reaching into the other.
    """
    if name in NUMERIC_FIELDS:
        return number is not None
    return bool(normalised) and any(c.isalpha() for c in normalised)


# --------------------------------------------------------------------------
# Locating a value in the document it is supposed to have come from
# --------------------------------------------------------------------------
def _locate(doc: ParsedDoc, name: str, raw: str,
            claimed_label: str) -> Optional[tuple[str, str, str]]:
    """Find `raw` in `doc` and return (locator, printed label, snippet).

    Two passes, in this order:

    1. **The chunks the reader produced.** A chunk the label resolver rejected
       is still a real label/value pair at a real locator — "Shipped By" at
       `line 3`, `S.I.!A4`, `p1 r7` — and it is the most precise provenance we
       have. This is the common case for the documents this module exists for:
       the reader found the pair, only `labels.py` did not recognise the
       wording.
    2. **The document text, line by line.** For layouts where no chunk was
       formed at all (a value on a continuation line, a form with no colon).
       The label recorded is the text printed before the value on that line,
       which is the label by construction.

    Within each pass, a spot whose printed label matches the one the model
    reported wins over one that merely holds the same text. The claim is used
    only to *choose between places the value genuinely is* — never to create a
    location — and it earns its keep on a real document: a consignee and a
    notify party are frequently the same company, so the value alone cannot say
    which of the two lines we read, and the evidence would point a reviewer at
    the wrong row.

    None means the value is not in this document in a form we are willing to
    stand behind, and the caller drops it.
    """
    claim = normalize.basic(claimed_label)
    fallback: Optional[tuple[str, str, str]] = None

    for chunk in doc.chunks:
        # `first_segment` because that is the slice the rule extractor would
        # have taken from the same chunk; matching anywhere in a trailing
        # address block would credit a value to the wrong line.
        segment = normalize.first_segment(chunk.value)
        if _find_span(segment, raw, name) is None:
            continue
        hit = (chunk.locator, chunk.label, _snippet_from_chunk(chunk))
        if claim and normalize.basic(chunk.label) == claim:
            return hit
        fallback = fallback or hit

    for number, line in enumerate((doc.text or "").splitlines(), start=1):
        start = _find_span(line, raw, name)
        if start is None:
            continue
        printed = _label_before(line, start)
        hit = (f"line {number}", printed, _trim(line))
        if claim and normalize.basic(printed) == claim:
            return hit
        fallback = fallback or hit

    return fallback


def _find_span(haystack: str, needle: str, name: str) -> Optional[int]:
    """Where `needle` sits in `haystack` as a value, or None.

    Case-insensitive, because a reader may upper-case a cell while the page
    prints mixed case; everything else is exact. Two field-dependent rules
    decide whether a match counts as *the value* rather than as characters that
    happen to appear:

    * **parties and ports** must run to the end of the value region (end of the
      string, or the pipe the .xlsx reader joins a cell's address with). A
      prefix match would bless "APRIL FINE PAPER TRADING" as a reading of
      "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", which is a *different*
      shipper — and a false discrepancy is exactly what this module must not
      manufacture (DATA_NOTES §4).
    * **numbers** must not be embedded in a longer figure ("118,270" found
      inside a printed "1,118,270" is not that number) and must be the *first*
      figure of the value, because that is the figure `normalize` reads: in
      "6 x 40'HC" the 40 is the box size, not a quantity (DATA_NOTES §4). The
      same rule keeps a per-container row's weight from being accepted as the
      shipment total, since the container id printed ahead of it is digits.

    A number is not asked to run to the end of the value, because the unit
    belongs to the document, not to the figure: "6" is a complete reading of
    "6 x 40'HC" and "118,270" of "118,270 KG".
    """
    if not needle or not haystack:
        return None
    hay, sought = haystack.upper(), needle.upper()
    numeric = name in NUMERIC_FIELDS

    start = 0
    while True:
        i = hay.find(sought, start)
        if i < 0:
            return None
        j = i + len(sought)
        if _boundaries_ok(hay, i, j, numeric) and (
            _is_first_figure(hay, i) if numeric else _tail_exhausted(hay[j:])
        ):
            return i
        start = i + 1


def _boundaries_ok(hay: str, i: int, j: int, numeric: bool) -> bool:
    """The characters either side must not continue the value.

    For a number the thousands and decimal separators count as continuation
    too, so a match cannot start or end in the middle of "1,118,270.50".
    """
    before = hay[i - 1] if i > 0 else ""
    after = hay[j] if j < len(hay) else ""
    if numeric:
        return not _continues_number(before) and not _continues_number(after)
    return not before.isalnum() and not after.isalnum()


def _continues_number(char: str) -> bool:
    # The empty string means "start/end of the text", which continues nothing.
    # Without the guard `"" in ",."` is True and every value that opens its
    # line would be rejected.
    return bool(char) and (char.isdigit() or char in ",.")


def _is_first_figure(hay: str, i: int) -> bool:
    """Is this the first figure of the value, rather than a later one?

    The label is dropped first where the document punctuates it, so a label
    that happens to contain a digit does not disqualify the value it
    introduces.
    """
    head = hay[:i].rsplit(":", 1)[-1]
    return not any(c.isdigit() for c in head)


def _tail_exhausted(tail: str) -> bool:
    """True when nothing of substance follows the match in this value region.

    Cut at the pipe first: the .xlsx reader packs "NAME | ADDRESS" into one
    cell, and `first_segment()` — which is what the comparison will see —
    stops there too. Trailing punctuation and whitespace are fine; another
    word is not, because it would mean we accepted part of a longer value.
    """
    head = tail.split(_SEGMENT_END, 1)[0]
    return not any(c.isalnum() for c in head)


def _label_before(line: str, start: int) -> str:
    """The label printed before the value on this line, if there is one."""
    return line[:start].strip().rstrip(":").strip()


def _snippet_from_chunk(chunk: Chunk) -> str:
    has_value = chunk.value is not None and str(chunk.value).strip() != ""
    text = f"{chunk.label}: {chunk.value}" if has_value else f"{chunk.label}:"
    return _trim(text)


def _trim(text: str) -> str:
    """One display line for the review queue — same shape as `fields._snippet`."""
    flat = " ".join(str(text).split())
    if len(flat) <= SNIPPET_MAX:
        return flat
    return flat[: SNIPPET_MAX - 3].rstrip() + "..."


__all__ = [
    "DocumentReading",
    "MAX_DOC_CHARS",
    "PURPOSE",
    "ReadField",
    "fill_missing_fields",
    "missing_field_names",
]
