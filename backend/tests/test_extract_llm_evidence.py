"""extract/llm.py — the evidence side: where a model answer is allowed to land.

`test_extract_llm.py` pins the contract (a traceable value is adopted, an
invented one is not, rules win, an unavailable model changes nothing). This
file is the adversarial half: the answers a model gives *rarely*, which are
exactly the ones that would turn into a confident false discrepancy if the
locating step were even slightly loose.

Three families, all drawn from `docs/DATA_NOTES.md`:

* a **truncated** party name — the characters are on the page, so a bare
  substring search would bless "APRIL FINE PAPER TRADING" as a reading of
  "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", a different shipper (§4);
* a **number read from the wrong place** — the 40 in "6 x 40'HC" is the box
  size, and a per-container weight is not the shipment total (§3a, §4);
* a value read from the **wrong line or the wrong document** — right text,
  wrong provenance, which makes the reviewer's locator a lie.

Offline throughout: the stub is the model. Nothing here opens a socket.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

import pytest

from sdoc.evidence_gate import trace_value
from sdoc.extract.fields import SNIPPET_MAX, extract_fields
from sdoc.extract.llm import (
    DocumentReading,
    ReadField,
    fill_missing_fields,
    missing_field_names,
)
from sdoc.readers import plain
from sdoc.schema import COMPARE_FIELDS, Chunk, DocFields, FieldValue, ParsedDoc

# --------------------------------------------------------------------------
# Document shapes — real bundle layouts, labels reworded past labels.py.
# These describe a *shape*, never a particular email.
# --------------------------------------------------------------------------
RELABELLED_SI = """\
SHIPPING INSTRUCTION
========================================

Shipped By: APRIL FAR EAST (M) SDN BHD
  TOWER 2, AVENUE 5, LEVEL 6; BANGSAR SOUTH CITY, MALAYSIA
Deliver To: EAST BRIGHT FZ-LLC
  RAKEZ AMENITY CENTER; AL HAMRA INDUSTRIAL ZONE, RAK, UAE
Party to be Advised: KPP-ANTALIS (SINGAPORE) PTE. LTD.
Uplift Port: NANTONG, CHINA (CNNTG)
Destination Terminal: KARACHI, PAKISTAN (PKKHI)
Box Count: 6 x 40'HC
Total Wt.: 131,058 KG
Vessel: NAP 914 V.BS007
Booking Ref: ONEYSI12345678
"""

# The same facts with no label delimiter at all: `readers/rows.py` starts a
# chunk only on "Label: value", so this layout yields none and the evidence can
# come only from the line scan.
COLUMNAR_SI = """\
SHIPPING INSTRUCTION

Shipped By                      APRIL FINE PAPER TRADING (MIDDLE EAST) FZE
Uplift Port                     RUGAO/NANTONG/SHANGHAI, CHINA
Total Wt.                       118,270 KG
"""


def _doc(text: str, *, path: str = "attachments/shape_SI.txt") -> ParsedDoc:
    """Run a document shape through the real .txt reader."""
    return plain.read(ParsedDoc(path=path, ext=".txt", role_hint="SI"),
                      text.encode("utf-8"))


@dataclass
class _StubClient:
    """`LLMClient` with no SDK, no key and no network, recording every call."""

    answers: list[tuple[str, str, str]] = dc_field(default_factory=list)
    available: bool = True
    raises: Optional[Exception] = None
    calls: list[dict[str, Any]] = dc_field(default_factory=list)

    def structured(self, **kwargs: Any) -> DocumentReading:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return DocumentReading(
            fields=[ReadField(field=f, value=v, label=lab)
                    for f, v, lab in self.answers]
        )


def _fill(doc: ParsedDoc, answers, *, role: str = "SI",
          **kw) -> tuple[DocFields, _StubClient]:
    """Extract by rules, then let a stubbed model fill what is missing."""
    before = extract_fields(doc, role)
    client = _StubClient(answers=list(answers), **kw)
    return fill_missing_fields(doc, before, role, client=client), client


# ==========================================================================
# 1. The evidence records where we found it, not what we were told
# ==========================================================================
def test_evidence_points_at_the_line_the_value_is_printed_on():
    doc = _doc(RELABELLED_SI)
    merged, _ = _fill(doc, [
        ("shipper", "APRIL FAR EAST (M) SDN BHD", "Shipped By"),
        ("port_of_loading", "NANTONG, CHINA (CNNTG)", "Uplift Port"),
        ("gross_weight_kg", "131,058 KG", "Total Wt."),
    ])

    shipper = merged.get("shipper")
    assert shipper.extractor == "llm"
    assert shipper.normalised == "APRIL FAR EAST M"        # SDN BHD dropped
    assert shipper.evidence.doc_role == "SI"
    assert shipper.evidence.locator == "line 4"
    assert shipper.evidence.label == "Shipped By"          # as the page prints it
    assert "APRIL FAR EAST" in shipper.evidence.snippet

    assert merged.get("port_of_loading").normalised == "NANTONG CHINA"
    assert merged.get("gross_weight_kg").number == 131058.0
    for name in ("port_of_loading", "gross_weight_kg"):
        assert trace_value(doc, merged.get(name)) is True


def test_the_snippet_keeps_the_reviewer_contract():
    """One display line, trimmed — the invariants `fields.py` also guarantees,
    because the review queue renders both kinds of evidence the same way."""
    doc = _doc(RELABELLED_SI)
    merged, _ = _fill(doc, [("consignee", "EAST BRIGHT FZ-LLC", "Deliver To")])
    snippet = merged.get("consignee").evidence.snippet

    assert snippet.startswith("Deliver To: EAST BRIGHT FZ-LLC")
    assert "\n" not in snippet
    assert 0 < len(snippet) <= SNIPPET_MAX


def test_the_claimed_label_only_chooses_between_real_locations():
    """A consignee and a notify party are frequently the same company.

    The value alone cannot say which line we read, so the label the model
    reports breaks the tie — but only between places the value genuinely is.
    Without this the locator sends a reviewer to the wrong row of the form.
    """
    doc = _doc("Deliver To: EAST BRIGHT FZ-LLC\n"
               "Party to be Advised: EAST BRIGHT FZ-LLC\n")
    merged, _ = _fill(doc, [
        ("consignee", "EAST BRIGHT FZ-LLC", "Deliver To"),
        ("notify_party", "EAST BRIGHT FZ-LLC", "Party to be Advised"),
    ])

    assert merged.get("consignee").evidence.locator == "line 1"
    assert merged.get("notify_party").evidence.locator == "line 2"
    assert merged.get("notify_party").evidence.label == "Party to be Advised"


def test_evidence_falls_back_to_the_line_scan_when_there_are_no_chunks():
    doc = _doc(COLUMNAR_SI)
    assert doc.chunks == [], "a colon-less form yields no label/value pairs"

    merged, _ = _fill(doc, [
        ("shipper", "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", "Shipped By"),
        ("gross_weight_kg", "118,270 KG", "Total Wt."),
    ])

    shipper = merged.get("shipper")
    assert shipper.present and shipper.extractor == "llm"
    assert shipper.evidence.locator == "line 3"
    assert shipper.evidence.label == "Shipped By"      # the text before the value
    assert trace_value(doc, shipper) is True
    assert merged.get("gross_weight_kg").number == 118270.0


def test_a_chunk_carrying_a_non_string_value_is_still_a_valid_location():
    """.xlsx hands the extractor real numbers, not text."""
    doc = ParsedDoc(
        path="attachments/sheet_SI.xlsx", ext=".xlsx", readable=True,
        text="GROSS WEIGHT\t216950\nBox Count\t10\n",
        chunks=[Chunk(label="GROSS WEIGHT", value=216950, locator="S.I.!A10"),
                Chunk(label="Box Count", value=10, locator="S.I.!A11", order=1)],
    )
    rules = extract_fields(doc, "SI")
    assert "container_count" in missing_field_names(rules)

    merged = fill_missing_fields(
        doc, rules, "SI",
        client=_StubClient(answers=[("container_count", "10", "Box Count")]),
    )
    count = merged.get("container_count")
    assert count.number == 10.0
    assert count.evidence.locator == "S.I.!A11"
    assert trace_value(doc, count) is True


# ==========================================================================
# 2. Right characters, wrong value
# ==========================================================================
def test_a_truncated_party_name_is_rejected():
    """"APRIL FINE PAPER TRADING" is a *different* shipper from
    "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE" (DATA_NOTES §4).

    Every character of the short name is on the page, so only "the match must
    run to the end of the printed value" can refuse it — and refusing it is the
    difference between escalating and inventing a discrepancy.
    """
    doc = _doc(COLUMNAR_SI)
    merged, _ = _fill(doc, [("shipper", "APRIL FINE PAPER TRADING", "Shipped By")])

    assert merged.get("shipper").present is False
    assert merged.get("shipper").raw is None
    assert any("could not be located" in n for n in doc.notes)


def test_a_number_embedded_in_a_longer_figure_is_rejected():
    doc = _doc("Total Wt.: 1,118,270 KG\n")
    merged, _ = _fill(doc, [("gross_weight_kg", "118,270", "Total Wt.")])
    assert merged.get("gross_weight_kg").present is False


def test_the_container_size_is_not_accepted_as_the_count():
    """In "6 x 40'HC" the 40 is the box size, not a quantity. It is printed, so
    only "the first figure of the value" can reject it."""
    doc = _doc("Box Count: 6 x 40'HC\n")

    wrong, _ = _fill(doc, [("container_count", "40", "Box Count")])
    assert wrong.get("container_count").present is False

    right, _ = _fill(doc, [("container_count", "6", "Box Count")])
    assert right.get("container_count").number == 6.0


def test_a_per_container_weight_is_not_accepted_as_the_shipment_total():
    """The container table prints an id before each row's weight, so the row
    figure is never the first figure of its line (DATA_NOTES §3a)."""
    doc = _doc("Total Wt.: 118,270 KG\n"
               "UJAJ2269312 40'HC PAPERBOARD 23,654\n")
    merged, _ = _fill(doc, [("gross_weight_kg", "23,654", "GROSS WEIGHT (KG)")])
    assert merged.get("gross_weight_kg").present is False


def test_a_value_hidden_inside_an_address_block_is_not_credited_to_the_label():
    """The value must be the value, not a phrase from the address beneath it."""
    doc = _doc("Deliver To: EAST BRIGHT FZ-LLC\n"
               "  RAKEZ AMENITY CENTER; AL HAMRA INDUSTRIAL ZONE, RAK, UAE\n")
    merged, _ = _fill(doc, [("consignee", "AL HAMRA INDUSTRIAL ZONE", "Deliver To")])
    assert merged.get("consignee").present is False


def test_a_value_that_belongs_to_the_other_document_is_not_adopted():
    """A real failure mode of a batch run: the right value, the wrong document.

    The draft BL's notify party is printed in the BL. Offered as a reading of
    the SI it must be refused, or the comparison runs against a value we never
    read from the side we claim to have read it from.
    """
    si = _doc("Deliver To: EAST BRIGHT FZ-LLC\n", path="attachments/x_SI.txt")
    merged, _ = _fill(si, [("notify_party", "UAB NOVAKOPA", "Onward Notification")])
    assert merged.get("notify_party").present is False


@pytest.mark.parametrize("answer", ["", "   ", "???", "N/A", "TBA", "_______"])
def test_a_placeholder_answer_leaves_the_field_absent_not_blank(answer):
    """"The document does not state it" is the answer we asked for. It must not
    be laundered into a blank we then claim to have read."""
    doc = _doc(RELABELLED_SI)
    merged, _ = _fill(doc, [("consignee", answer, "Deliver To")])

    assert merged.get("consignee").present is False
    assert merged.get("consignee").blank is False
    assert merged.get("consignee").raw is None


def test_a_mixture_of_real_and_invented_answers_separates_cleanly():
    """The invariant that matters: everything adopted traces, everything else
    is gone — one bad answer neither survives nor takes its neighbours down."""
    doc = _doc(RELABELLED_SI)
    merged, _ = _fill(doc, [
        ("shipper", "APRIL FAR EAST (M) SDN BHD", "Shipped By"),
        ("consignee", "NOT IN THIS DOCUMENT PTE LTD", "Deliver To"),
        ("notify_party", "KPP-ANTALIS (SINGAPORE) PTE. LTD.", "Party to be Advised"),
        ("port_of_loading", "SINGAPORE", "Uplift Port"),
        ("port_of_discharge", "KARACHI, PAKISTAN (PKKHI)", "Destination Terminal"),
        ("container_count", "6 x 40'HC", "Box Count"),
        ("gross_weight_kg", "999,999 KG", "Total Wt."),
    ])

    adopted = {n for n in COMPARE_FIELDS if merged.get(n).present}
    assert adopted == {"shipper", "notify_party", "port_of_discharge",
                       "container_count"}
    for name in COMPARE_FIELDS:
        value = merged.get(name)
        if name in adopted:
            assert value.extractor == "llm"
            assert trace_value(doc, value) is True
        else:
            assert value.raw is None and value.evidence is None


def test_silence_on_a_document_of_the_wrong_kind_stays_an_escalation():
    """A Commercial Invoice sent as the BL has no ports to find. The correct
    answer is an empty one, and it must leave the case for a human."""
    doc = _doc("COMMERCIAL INVOICE\nInvoice No.: INV-8841\n"
               "Seller: APRIL FAR EAST (M) SDN BHD\nTotal Amount: USD 412,550.00\n")
    rules = extract_fields(doc, "BL")
    merged = fill_missing_fields(
        doc, rules, "BL",
        client=_StubClient(answers=[(n, "", "") for n in missing_field_names(rules)]),
    )
    for name in COMPARE_FIELDS:
        assert merged.get(name).present is False


# ==========================================================================
# 3. What the rules own stays the rules'
# ==========================================================================
def test_a_rule_value_survives_even_an_answer_that_would_trace():
    doc = _doc("Shipper: APRIL FAR EAST (M) SDN BHD\n"
               "Deliver To: EAST BRIGHT FZ-LLC\n")
    rules = extract_fields(doc, "SI")
    assert missing_field_names(rules) == [
        "consignee", "notify_party", "port_of_loading", "port_of_discharge",
        "container_count", "gross_weight_kg",
    ]

    client = _StubClient(answers=[
        # Printed in the document, so it *would* trace — and must still lose.
        ("shipper", "EAST BRIGHT FZ-LLC", "Deliver To"),
        ("consignee", "EAST BRIGHT FZ-LLC", "Deliver To"),
    ])
    merged = fill_missing_fields(doc, rules, "SI", client=client)

    assert merged.get("shipper").raw == "APRIL FAR EAST (M) SDN BHD"
    assert merged.get("shipper").extractor == "rule"
    assert merged.get("consignee").extractor == "llm"

    asked = client.calls[0]["prompt"].split("--- BEGIN DOCUMENT ---")[0]
    assert "shipper" not in asked and "consignee" in asked


def test_a_blank_field_is_neither_asked_about_nor_replaced():
    doc = _doc("Gross Weight (KG): ???\nBox Count: 6 x 40'HC\n")
    rules = extract_fields(doc, "SI")
    client = _StubClient(answers=[("container_count", "6 x 40'HC", "Box Count")])
    merged = fill_missing_fields(doc, rules, "SI", client=client)

    weight = merged.get("gross_weight_kg")
    assert weight.blank is True and weight.raw == "???" and weight.extractor == "rule"
    asked = client.calls[0]["prompt"].split("--- BEGIN DOCUMENT ---")[0]
    assert "gross_weight_kg" not in asked


def test_a_value_the_rules_read_but_could_not_parse_is_still_theirs():
    doc = _doc("Total Containers: SEE ATTACHED MANIFEST\n")
    rules = extract_fields(doc, "SI")

    assert rules.get("container_count").raw == "SEE ATTACHED MANIFEST"
    assert "container_count" not in missing_field_names(rules)


def test_the_input_docfields_is_not_mutated():
    """A caller may keep the rule-only reading beside the merged one."""
    doc = _doc(RELABELLED_SI)
    rules = extract_fields(doc, "SI")
    merged = fill_missing_fields(
        doc, rules, "SI",
        client=_StubClient(answers=[("shipper", "APRIL FAR EAST (M) SDN BHD",
                                     "Shipped By")]),
    )
    assert merged is not rules
    assert merged.get("shipper").present is True
    assert rules.get("shipper").present is False and rules.get("shipper").raw is None


def test_a_repeated_answer_for_one_field_is_taken_once():
    doc = _doc(RELABELLED_SI)
    merged, _ = _fill(doc, [
        ("consignee", "EAST BRIGHT FZ-LLC", "Deliver To"),
        ("consignee", "KPP-ANTALIS (SINGAPORE) PTE. LTD.", "Party to be Advised"),
    ])
    assert merged.get("consignee").raw == "EAST BRIGHT FZ-LLC"


def test_missing_names_come_back_in_canonical_order():
    """A stable order is a stable prompt, which is a stable cache key."""
    names = missing_field_names(extract_fields(_doc(RELABELLED_SI), "SI"))
    assert names == [f for f in COMPARE_FIELDS if f in set(names)]


def test_missing_names_is_total_over_the_seven():
    empty = DocFields(doc=_doc("Vessel: NAP 914\n"))
    assert missing_field_names(empty) == list(COMPARE_FIELDS)
    assert isinstance(empty.get("shipper"), FieldValue)


# ==========================================================================
# 4. The model reads one document; it is never asked to compare two
# ==========================================================================
def test_the_prompt_holds_one_document_and_asks_for_no_judgement():
    """Comparison stays exact and deterministic in compare.py. A model asked
    "do these match?" answers plausibly even on values it misread."""
    doc = _doc(RELABELLED_SI)
    _, client = _fill(doc, [])
    call = client.calls[0]

    assert call["purpose"] == "extract"
    assert call["schema"] is DocumentReading
    assert call["reasoning_effort"] == "low"        # careful reading, not triage
    assert call["prompt"].count("--- BEGIN DOCUMENT ---") == 1
    for forbidden in ("match", "mismatch", "discrepancy", "compare", "agree"):
        assert forbidden not in call["prompt"].lower()
    assert "do not compare" in call["instructions"].lower()


def test_the_prompt_describes_only_the_fields_that_are_missing():
    doc = _doc("Shipper: APRIL FAR EAST (M) SDN BHD\nBox Count: 6 x 40'HC\n")
    _, client = _fill(doc, [])
    asked = client.calls[0]["prompt"].split("--- BEGIN DOCUMENT ---")[0]

    assert "container_count" in asked
    assert "shipper" not in asked


def test_a_client_with_no_key_is_never_called():
    """No key configured is a normal operating mode, not an error."""
    doc = _doc(RELABELLED_SI)
    rules = extract_fields(doc, "SI")
    client = _StubClient(available=False)

    assert fill_missing_fields(doc, rules, "SI", client=client) is rules
    assert client.calls == []
