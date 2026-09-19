"""Model-assisted field reading, and the line it is not allowed to cross.

The whole point of this module is that a model may *read* a document but may
not *assert* anything the document does not contain. These tests pin that:
a value the model returns which cannot be located in the source is discarded,
and the field stays absent so the case escalates to a person.

Everything runs offline against a stub. A test that needed the network would
not be able to prove the offline guarantee it exists to protect.
"""
from __future__ import annotations

import pytest

from sdoc.evidence_gate import trace_value
from sdoc.extract import fields as rule_extract
from sdoc.extract import llm as extract_llm
from sdoc.extract.llm import DocumentReading, ReadField
from sdoc.llm.client import LLMUnavailable
from sdoc.readers.rows import chunks_from_lines
from sdoc.schema import COMPARE_FIELDS, DocFields, FieldValue, ParsedDoc

# A document whose labels labels.py does not recognise: a human reads it
# without difficulty, the rule extractor finds nothing.
UNSEEN_LABELS = """\
SHIPPING INSTRUCTION
Shipped By: APRIL FAR EAST (M) SDN BHD
Deliver To: EAST BRIGHT FZ-LLC
Send Notice To: EAST BRIGHT FZ-LLC
Loading Terminal: NANTONG, CHINA
Final Destination Port: KARACHI, PAKISTAN
Boxes: 6 x 40'HC
Total Wt.: 131,058 KG
"""


def _doc(text: str = UNSEEN_LABELS) -> ParsedDoc:
    doc = ParsedDoc(path="attachments/x_SI.txt", ext=".txt", role_hint="SI")
    doc.text = text
    doc.chunks = chunks_from_lines(text.splitlines())
    return doc


class _StubClient:
    """Stands in for LLMClient. Returns a canned reading, or raises."""

    available = True

    def __init__(self, reading=None, raises: Exception | None = None):
        self.reading, self.raises = reading, raises
        self.calls = 0

    def structured(self, **kwargs):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.reading


def _reading(pairs: list[tuple[str, str, str]]) -> DocumentReading:
    return DocumentReading(
        fields=[ReadField(field=f, value=v, label=lab) for f, v, lab in pairs]
    )


# --------------------------------------------------------------------------
# what counts as missing
# --------------------------------------------------------------------------
def test_the_synonym_table_still_catches_a_plausible_variant():
    # "Final Destination Port" is not in the table verbatim, but it is close
    # enough to "Destination Port" for the fuzzy label pass to resolve it. The
    # model is a fallback for what the table cannot reach — not a replacement
    # for it, and every field it does not have to read is a field that costs
    # nothing and cannot be hallucinated.
    fields = rule_extract.extract_fields(_doc(), "SI")
    assert fields.get("port_of_discharge").present is True
    assert fields.get("port_of_discharge").extractor == "rule"


def test_genuinely_unseen_labels_leave_their_fields_missing():
    fields = rule_extract.extract_fields(_doc(), "SI")
    missing = set(extract_llm.missing_field_names(fields))
    # "Shipped By", "Deliver To", "Send Notice To", "Loading Terminal",
    # "Boxes" and "Total Wt." have no counterpart the table can reach.
    assert missing == set(COMPARE_FIELDS) - {"port_of_discharge"}


def test_a_blank_value_is_not_treated_as_missing():
    # "???" means the document printed the field and left it empty. That is
    # uncertainty for a reviewer to resolve, not a label we failed to read, and
    # asking a model to fill it invites the invention this module prevents.
    doc = _doc("SHIPPING INSTRUCTION\nShipper: ???\n")
    fields = rule_extract.extract_fields(doc, "SI")
    assert fields.get("shipper").blank is True
    assert "shipper" not in extract_llm.missing_field_names(fields)


# --------------------------------------------------------------------------
# adoption
# --------------------------------------------------------------------------
def test_a_value_present_in_the_document_is_adopted_with_traceable_evidence():
    doc = _doc()
    rules = rule_extract.extract_fields(doc, "SI")
    client = _StubClient(_reading([
        ("shipper", "APRIL FAR EAST (M) SDN BHD", "Shipped By"),
        ("container_count", "6 x 40'HC", "Boxes"),
    ]))

    merged = extract_llm.fill_missing_fields(doc, rules, "SI", client=client)

    shipper = merged.get("shipper")
    assert shipper.present is True
    assert shipper.extractor == "llm"
    assert shipper.raw == "APRIL FAR EAST (M) SDN BHD"
    assert shipper.evidence is not None
    # The evidence must satisfy the same gate that guards rule-read values.
    assert trace_value(doc, shipper) is True

    assert merged.get("container_count").number == 6


def test_a_value_the_document_does_not_contain_is_discarded():
    # The hallucination case. ROXCEL appears nowhere in the document; adopting
    # it would create a discrepancy out of nothing.
    doc = _doc()
    rules = rule_extract.extract_fields(doc, "SI")
    client = _StubClient(_reading([("consignee", "ROXCEL TRADING GMBH", "Deliver To")]))

    merged = extract_llm.fill_missing_fields(doc, rules, "SI", client=client)

    consignee = merged.get("consignee")
    assert consignee.present is False
    assert consignee.raw is None


def test_a_field_that_was_not_asked_about_is_ignored():
    doc = _doc("SHIPPING INSTRUCTION\nShipper: APRIL FAR EAST (M) SDN BHD\nBoxes: 6 x 40'HC\n")
    rules = rule_extract.extract_fields(doc, "SI")
    assert rules.get("shipper").present is True          # the rules read this one
    before = rules.get("shipper").raw

    client = _StubClient(_reading([("shipper", "SOMETHING ELSE ENTIRELY", "Shipper")]))
    merged = extract_llm.fill_missing_fields(doc, rules, "SI", client=client)

    # Rule-extracted values win: they came from a resolved label and are what
    # the system was measured on.
    assert merged.get("shipper").raw == before
    assert merged.get("shipper").extractor == "rule"


def test_an_empty_value_means_absent_not_adopted():
    doc = _doc()
    rules = rule_extract.extract_fields(doc, "SI")
    client = _StubClient(_reading([("shipper", "", "")]))
    merged = extract_llm.fill_missing_fields(doc, rules, "SI", client=client)
    assert merged.get("shipper").present is False


# --------------------------------------------------------------------------
# degrading safely
# --------------------------------------------------------------------------
def test_no_client_returns_the_input_untouched():
    doc = _doc()
    rules = rule_extract.extract_fields(doc, "SI")
    assert extract_llm.fill_missing_fields(doc, rules, "SI", client=None) is rules


def test_an_unavailable_model_returns_the_input_untouched():
    doc = _doc()
    rules = rule_extract.extract_fields(doc, "SI")
    client = _StubClient(raises=LLMUnavailable("budget spent"))
    out = extract_llm.fill_missing_fields(doc, rules, "SI", client=client)
    assert out is rules
    assert any("unavailable" in n for n in doc.notes)


def test_an_unreadable_document_is_never_sent_to_the_model():
    # Nothing to read, and nothing to trace an answer against. Sending it would
    # buy a guess at full price.
    doc = ParsedDoc(path="attachments/x_BL.pdf", ext=".pdf", role_hint="BL")
    doc.readable = False
    doc.unreadable_reason = "no_text_layer"
    rules = DocFields(doc=doc, fields={f: FieldValue(field=f) for f in COMPARE_FIELDS})
    client = _StubClient(_reading([("shipper", "ANYTHING", "Shipper")]))

    out = extract_llm.fill_missing_fields(doc, rules, "BL", client=client)
    assert out is rules
    assert client.calls == 0


def test_nothing_missing_means_no_call_at_all():
    doc = _doc("SHIPPING INSTRUCTION\n"
               "Shipper: APRIL FAR EAST (M) SDN BHD\n"
               "Consignee: EAST BRIGHT FZ-LLC\n"
               "Notify Party: EAST BRIGHT FZ-LLC\n"
               "Port of Loading: NANTONG, CHINA\n"
               "Port of Discharge: KARACHI, PAKISTAN\n"
               "Total Containers: 6 x 40'HC\n"
               "Gross Weight (KG): 131,058 KG\n")
    rules = rule_extract.extract_fields(doc, "SI")
    assert extract_llm.missing_field_names(rules) == []
    client = _StubClient(_reading([]))
    extract_llm.fill_missing_fields(doc, rules, "SI", client=client)
    assert client.calls == 0


@pytest.mark.parametrize("field,value", [
    ("container_count", "not a number at all"),
    ("gross_weight_kg", "heavy"),
])
def test_an_unparseable_numeric_value_is_not_adopted(field, value):
    doc = _doc()
    rules = rule_extract.extract_fields(doc, "SI")
    client = _StubClient(_reading([(field, value, "Boxes")]))
    merged = extract_llm.fill_missing_fields(doc, rules, "SI", client=client)
    assert merged.get(field).present is False
