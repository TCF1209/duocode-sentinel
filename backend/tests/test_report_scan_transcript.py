"""A vision transcript reaches the report, and changes nothing else.

`readers/scan.py` parks what a vision model read off an image-only PDF on
an attribute no extraction path reads. Until 24 Sep that was where it
stayed: `report.json` never carried it, so the API and the dashboard could
not show a reviewer the page already read. Now `schema._doc` copies it into
the document's report record -- and only there. The document is still
unreadable, the case still escalates, and the graded submission shape is
untouched.
"""
from __future__ import annotations

from sdoc.readers import scan
from sdoc.schema import COMPARE_FIELDS, CaseResult, ParsedDoc


def _scan_doc(path: str, role: str) -> ParsedDoc:
    return ParsedDoc(path=path, ext=".pdf", role_hint=role, readable=False, unreadable_reason="no_text_layer")


def _transcript() -> scan.ScanTranscript:
    fields = [
        scan.ScanField(
            field=name,
            value="6 x 40'HC" if name == "container_count" else "",
            legible=name == "container_count",
        )
        for name in COMPARE_FIELDS
    ]
    return scan.ScanTranscript(
        fields=fields, overall_legible=True, confidence=0.9,
        model="gpt-5-mini", pages_read=1, note="Scan transcribed by gpt-5-mini from 1 page.",
    )


def test_a_transcript_rides_on_its_document_in_the_report():
    si = _scan_doc("attachments/email_x_SI.pdf", "SI")
    bl = _scan_doc("attachments/email_x_BL.pdf", "BL")
    scan.attach(si, _transcript())

    report = CaseResult(email_id="email_x", category="BL_COMPARISON",
                        status="NEEDS_REVIEW", review_reason="unreadable",
                        si_doc=si, bl_doc=bl).to_report()

    got = report["documents"]["si"]["scan_transcript"]
    assert got["kind"] == "scan_transcript"
    assert got["model"] == "gpt-5-mini"
    assert got["legible_count"] == 1
    assert got["fields"][5] == {"field": "container_count", "value": "6 x 40'HC", "legible": True}
    assert "advisory" in got and "not a verified extraction" in got["advisory"]
    # The other document, with no transcript, carries no key at all.
    assert "scan_transcript" not in report["documents"]["bl"]


def test_the_transcript_does_not_make_the_document_look_read():
    si = _scan_doc("attachments/email_x_SI.pdf", "SI")
    scan.attach(si, _transcript())
    result = CaseResult(email_id="email_x", category="BL_COMPARISON",
                        status="NEEDS_REVIEW", review_reason="unreadable", si_doc=si)

    report = result.to_report()
    assert report["documents"]["si"]["readable"] is False
    assert report["documents"]["si"]["unreadable_reason"] == "no_text_layer"
    assert si.text == "" and si.chunks == []
    # The graded artefact is the submission shape, and it never sees this.
    assert "scan_transcript" not in result.to_submission()
    assert "documents" not in result.to_submission()
