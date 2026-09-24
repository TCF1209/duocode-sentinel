"""The gate's missing-value sentence has to say what actually happened.

A *blank* is a field the document prints and leaves empty ("???", "TBA"):
the sender has to supply it. An *absent* field is one no label resolved to
at all -- the document may state it perfectly well, under wording
`labels.py` has never seen -- and telling an operator "the documents do not
state the consignee" while a consignee line sits on the page in front of
them is the kind of sentence that costs every later escalation its
credibility. Same status and review reason either way (`blank_value` /
`missing_value`, the graded artefact does not move); different sentence,
different recovery.

Runs the whole /compare path on inline text rather than calling the gate
directly, so the sentence is checked where an operator would read it: in the
case notes.
"""
from __future__ import annotations

from api.direct_compare import compare_uploads

# The same seven-field fixture test_api.py uses, with the labels the table
# already knows. Identical on both sides, so the unmodified pair is OK and
# every escalation below is caused by exactly one edit.
_TEXT = (
    "Shipper: TEST EXPORT COMPANY LTD\n"
    "Consignee: TEST IMPORT COMPANY LTD\n"
    "Notify Party: TEST NOTIFY AGENT LTD\n"
    "Port of Loading: PORT KLANG\n"
    "Port of Discharge: SINGAPORE\n"
    "Container Count: 2\n"
    "Gross Weight (KG): 15000\n"
)


def _report(si_text: str, bl_text: str = _TEXT) -> dict:
    result = compare_uploads("fixture_SI.txt", si_text.encode(), "fixture_BL.txt", bl_text.encode())
    return result.to_report()


def test_the_unmodified_pair_matches():
    report = _report(_TEXT)
    assert report["status"] == "OK", report["notes"]


def test_a_label_the_table_does_not_know_is_reported_as_unread_not_as_absent():
    # "Sender of Goods" is the wording docs/ADVERSARIAL.md section 8 uses as
    # genuinely unseen; the rules lose the field and must say so honestly.
    report = _report(_TEXT.replace("Shipper:", "Sender of Goods:"))
    assert report["status"] == "NEEDS_REVIEW"
    assert report["review_reason"] == "missing_value"
    notes = " ".join(report["notes"])
    assert "No label for shipper in the SI could be recognised" in notes
    assert "do not state shipper" not in notes
    # The recovery points at the label table, not at the sender.
    assert "label table" in notes
    assert "Ask the sender" not in notes


def test_a_blank_keeps_the_blank_sentence_and_the_sender_recovery():
    report = _report(_TEXT.replace("Consignee: TEST IMPORT COMPANY LTD", "Consignee: ???"))
    assert report["status"] == "NEEDS_REVIEW"
    assert report["review_reason"] == "missing_value"
    notes = " ".join(report["notes"])
    assert "The documents do not state consignee" in notes
    assert "No label for" not in notes
    assert "Ask the sender" in notes


def test_a_blank_and_an_unknown_label_together_get_both_sentences():
    si = _TEXT.replace("Shipper:", "Sender of Goods:").replace(
        "Consignee: TEST IMPORT COMPANY LTD", "Consignee: ???"
    )
    report = _report(si)
    assert report["review_reason"] == "missing_value"
    notes = " ".join(report["notes"])
    assert "The documents do not state consignee" in notes
    assert "No label for shipper in the SI could be recognised" in notes


def test_an_unknown_label_on_both_sides_names_either_document():
    si = _TEXT.replace("Port of Discharge:", "Final Port:")
    bl = _TEXT.replace("Port of Discharge:", "Final Port:")
    report = _report(si, bl)
    assert report["review_reason"] == "missing_value"
    notes = " ".join(report["notes"])
    assert "port of discharge in either document" in notes
