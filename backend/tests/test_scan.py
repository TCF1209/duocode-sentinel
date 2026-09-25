"""Scanned-PDF transcription: useful to a reviewer, invisible to the decision.

The load-bearing test in this file is
`test_transcribed_scan_is_still_unreadable`. Everything else checks that the
module does its job; that one checks it cannot quietly stop doing the *other*
job — keeping an image-only scan out of an automatic pass. A future change that
"helpfully" fills in `doc.text` or flips `doc.readable` would turn a
model-transcribed weight into a reported discrepancy, and this file is where
that gets caught.

No test here touches the network: sockets are blocked for the whole module and
the model client is always a stub, so this runs on a judge's laptop with no key
and no connection.
"""
from __future__ import annotations

import io
import socket
from types import SimpleNamespace
from typing import Any, get_args

import pytest

from sdoc.llm import LLMUnavailable
from sdoc.readers import read_attachment, scan
from sdoc.schema import COMPARE_FIELDS, ParsedDoc


# --------------------------------------------------------------------------
# no network, ever
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Any socket use in this module is a bug, so make it a loud one."""

    def _blocked(*args, **kwargs):
        raise AssertionError("test_scan must not open a socket")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


# --------------------------------------------------------------------------
# fixtures: a real PDF, and a stand-in for the model client
# --------------------------------------------------------------------------
def make_pdf(pages: int = 1, width: float = 595, height: float = 842) -> bytes:
    """A real, valid PDF with blank pages — i.e. an image-only scan's twin.

    Built with pypdfium2 rather than checked in as a fixture file so the tests
    still run where `data/` is absent (it is git-ignored).
    """
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(width, height)
    buffer = io.BytesIO()
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()


FULL_ANSWER: dict[str, Any] = {
    "fields": [
        {"field": "shipper", "value": "APRIL FAR EAST (M) SDN BHD", "legible": True},
        {"field": "consignee", "value": "AL GURG STATIONERY LLC", "legible": True},
        {"field": "notify_party", "value": "AL GURG STATIONERY LLC", "legible": True},
        {"field": "port_of_loading", "value": "NHAVA SHEVA, INDIA", "legible": True},
        {"field": "port_of_discharge", "value": "TUTICORIN, INDIA", "legible": True},
        {"field": "container_count", "value": "6 x 40'HC", "legible": True},
        {"field": "gross_weight_kg", "value": "128,544 KG", "legible": True},
    ],
    "overall_legible": True,
    "confidence": 0.92,
}


class StubClient:
    """Stands in for `LLMClient` without importing the SDK or touching a key.

    It validates the payload against the *real* schema the module asks for, so
    a change to that schema fails here rather than in production.
    """

    def __init__(self, payload: dict[str, Any] | None = None, *,
                 available: bool = True, raises: BaseException | None = None,
                 vision_model: str = "gpt-5-mini") -> None:
        self._payload = payload if payload is not None else FULL_ANSWER
        self._available = available
        self._raises = raises
        self.settings = SimpleNamespace(vision_model=vision_model)
        self.calls: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return self._available

    def structured(self, *, purpose: str, instructions: str, prompt: str,
                   schema: Any, images: list[bytes] | None = None,
                   reasoning_effort: str | None = None, **kwargs: Any) -> Any:
        self.calls.append({
            "purpose": purpose, "prompt": prompt, "images": images or [],
            "reasoning_effort": reasoning_effort,
        })
        if self._raises is not None:
            raise self._raises
        return schema.model_validate(self._payload)


def scan_doc(tmp_path, name: str = "email_999_SI.pdf", pages: int = 1) -> tuple[ParsedDoc, bytes]:
    """An image-only scan as the pipeline actually sees it.

    Goes through `read_attachment` on purpose: the diagnosis the rest of the
    system relies on must be the reader's own, not one the test invented.
    """
    folder = tmp_path / "attachments"
    folder.mkdir(exist_ok=True)
    data = make_pdf(pages=pages)
    (folder / name).write_bytes(data)
    doc = read_attachment(tmp_path, f"attachments/{name}")
    return doc, data


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def test_render_pages_returns_png_bytes():
    pages = scan.render_pages(make_pdf())
    assert len(pages) == 1
    assert pages[0].startswith(b"\x89PNG\r\n\x1a\n")


def test_render_pages_caps_the_page_count():
    # One pathological attachment must not be able to dominate a batch run.
    assert len(scan.render_pages(make_pdf(pages=9), max_pages=2)) == 2


def test_render_pages_caps_the_pixel_size():
    from PIL import Image

    # A page 4x A4 in each direction: rendering at scale 2.0 would be ~4800px.
    png = scan.render_pages(make_pdf(width=2380, height=3368), max_pages=1)[0]
    with Image.open(io.BytesIO(png)) as image:
        assert max(image.size) <= scan.MAX_EDGE_PX


def test_render_pages_on_rubbish_returns_empty_list():
    assert scan.render_pages(b"") == []
    assert scan.render_pages(b"this is not a pdf, it is a text file") == []


# --------------------------------------------------------------------------
# transcribe: the offline paths
# --------------------------------------------------------------------------
def test_transcribe_without_a_client_returns_none(tmp_path):
    doc, data = scan_doc(tmp_path)
    assert scan.transcribe(doc, data) is None
    assert scan.transcript_of(doc) is None


def test_transcribe_with_an_unavailable_client_returns_none(tmp_path):
    doc, data = scan_doc(tmp_path)
    client = StubClient(available=False)
    assert scan.transcribe(doc, data, client=client) is None
    assert client.calls == []          # no key means no call was even attempted


def test_llm_unavailable_is_an_escalation_not_a_crash(tmp_path):
    doc, data = scan_doc(tmp_path)
    client = StubClient(raises=LLMUnavailable("run budget spent"))
    assert scan.transcribe(doc, data, client=client) is None
    assert scan.transcript_of(doc) is None


def test_an_unexpected_error_is_swallowed_and_noted(tmp_path):
    doc, data = scan_doc(tmp_path)
    client = StubClient(raises=RuntimeError("connection reset by peer"))
    assert scan.transcribe(doc, data, client=client) is None
    joined = " ".join(doc.notes)
    assert "RuntimeError" in joined
    # The provider's message can echo the request; only the type is recorded.
    assert "connection reset by peer" not in joined


def test_a_non_pdf_is_not_transcribed(tmp_path):
    doc = ParsedDoc(path="attachments/x.docx", ext=".docx")
    client = StubClient()
    assert scan.transcribe(doc, b"PK\x03\x04not-a-pdf", client=client) is None
    assert client.calls == []


# --------------------------------------------------------------------------
# transcribe: the happy path
# --------------------------------------------------------------------------
def test_stubbed_client_produces_a_transcript(tmp_path):
    doc, data = scan_doc(tmp_path)
    transcript = scan.transcribe(doc, data, client=StubClient())

    assert isinstance(transcript, scan.ScanTranscript)
    assert [f.field for f in transcript.fields] == list(COMPARE_FIELDS)
    assert transcript.legible_count == 7
    assert transcript.overall_legible is True
    assert transcript.confidence == pytest.approx(0.92)
    assert transcript.pages_read == 1
    assert transcript.model == "gpt-5-mini"

    by_field = {f.field: f.value for f in transcript.fields}
    assert by_field["container_count"] == "6 x 40'HC"      # verbatim, not "6"
    assert by_field["gross_weight_kg"] == "128,544 KG"

    assert scan.transcript_of(doc) is transcript
    assert transcript.note in doc.notes

    # A printed caption the model copied in front of a value is not part of
    # it (seen live on email_512's BL: "Shipper: APRIL FAR EAST (M) SDN BHD").
    # A colon that is not a caption for this field stays.
    captioned = {**FULL_ANSWER, "fields": [
        {"field": "shipper", "value": "Shipper: APRIL FAR EAST (M) SDN BHD", "legible": True},
        {"field": "notify_party", "value": "Notify: AL GURG STATIONERY LLC", "legible": True},
        {"field": "port_of_loading", "value": "Port of Loading: NHAVA SHEVA, INDIA", "legible": True},
        {"field": "consignee", "value": "ATTN: AL GURG STATIONERY LLC", "legible": True},
    ]}
    by_field = {f.field: f.value for f in scan.transcribe(doc, data, client=StubClient(captioned)).fields}
    assert by_field["shipper"] == "APRIL FAR EAST (M) SDN BHD"
    assert by_field["notify_party"] == "AL GURG STATIONERY LLC"
    assert by_field["port_of_loading"] == "NHAVA SHEVA, INDIA"
    assert by_field["consignee"] == "ATTN: AL GURG STATIONERY LLC"


def test_the_call_is_cheap_and_carries_the_page(tmp_path):
    doc, data = scan_doc(tmp_path)
    client = StubClient()
    scan.transcribe(doc, data, client=client)

    (call,) = client.calls
    assert call["purpose"] == "read_scan"
    assert call["reasoning_effort"] == "low"
    assert len(call["images"]) == 1 and call["images"][0].startswith(b"\x89PNG")
    # The role hint from the filename is context for the layout, nothing more.
    assert "Shipping Instruction" in call["prompt"]


def test_report_payload_flags_itself_as_reviewer_evidence(tmp_path):
    doc, data = scan_doc(tmp_path)
    payload = scan.transcribe(doc, data, client=StubClient()).as_dict()
    assert payload["kind"] == "scan_transcript"
    assert "not a verified extraction" in payload["advisory"]
    assert len(payload["fields"]) == 7


# --------------------------------------------------------------------------
# THE IMPORTANT ONE
# --------------------------------------------------------------------------
def test_transcribed_scan_is_still_unreadable(tmp_path):
    """A transcript adds context to an escalation; it never removes one.

    If this ever fails, a model-transcribed value can reach the extractor and
    be reported as a discrepancy against a document nobody verified.
    """
    doc, data = scan_doc(tmp_path)
    assert doc.readable is False
    assert doc.unreadable_reason == "no_text_layer"

    transcript = scan.transcribe(doc, data, client=StubClient())
    assert transcript is not None                 # the transcript did happen

    assert doc.readable is False
    assert doc.unreadable_reason == "no_text_layer"
    # Nothing an extractor reads may have been touched: chunks feed the field
    # extractor, and `text` is what the evidence gate traces values against.
    assert doc.chunks == []
    assert doc.text.strip() == ""
    assert "APRIL FAR EAST" not in doc.text


def test_the_note_tells_the_reviewer_the_case_is_still_theirs(tmp_path):
    doc, data = scan_doc(tmp_path)
    transcript = scan.transcribe(doc, data, client=StubClient())
    assert "review" in transcript.note.lower()
    assert "7/7 fields legible" in transcript.note


# --------------------------------------------------------------------------
# never guess
# --------------------------------------------------------------------------
def test_an_illegible_field_keeps_no_guess(tmp_path):
    """A hedged answer — a value *and* legible=false — must not reach a human.

    Guessing at a smudged weight is the worst outcome available here: the
    reviewer would act on a figure nobody read.
    """
    payload = {
        "fields": [dict(f) for f in FULL_ANSWER["fields"]],
        "overall_legible": True,
        "confidence": 0.4,
    }
    payload["fields"][6] = {
        "field": "gross_weight_kg", "value": "128,5?4 KG", "legible": False,
    }
    doc, data = scan_doc(tmp_path)
    transcript = scan.transcribe(doc, data, client=StubClient(payload))

    weight = next(f for f in transcript.fields if f.field == "gross_weight_kg")
    assert weight.legible is False
    assert weight.value == ""
    assert transcript.legible_count == 6


@pytest.mark.parametrize("value", ["???", "   ", "N/A", "_______", "TBA"])
def test_a_placeholder_is_a_blank_not_a_reading(tmp_path, value):
    payload = {
        "fields": [{"field": "consignee", "value": value, "legible": True}],
        "overall_legible": True,
        "confidence": 0.5,
    }
    doc, data = scan_doc(tmp_path)
    transcript = scan.transcribe(doc, data, client=StubClient(payload))

    consignee = next(f for f in transcript.fields if f.field == "consignee")
    assert consignee.legible is False
    assert consignee.value == ""


def test_a_field_the_model_omitted_comes_back_illegible(tmp_path):
    payload = {
        "fields": [{"field": "shipper", "value": "APRIL FAR EAST (M) SDN BHD",
                    "legible": True}],
        "overall_legible": True,
        "confidence": 0.3,
    }
    doc, data = scan_doc(tmp_path)
    transcript = scan.transcribe(doc, data, client=StubClient(payload))

    assert [f.field for f in transcript.fields] == list(COMPARE_FIELDS)
    assert transcript.legible_count == 1
    assert all(f.value == "" for f in transcript.fields if f.field != "shipper")


def test_overall_legible_cannot_outvote_the_fields(tmp_path):
    payload = {
        "fields": [{"field": "shipper", "value": "", "legible": False}],
        "overall_legible": True,
        "confidence": 2.5,          # out of range on purpose
    }
    doc, data = scan_doc(tmp_path)
    transcript = scan.transcribe(doc, data, client=StubClient(payload))

    assert transcript.overall_legible is False
    assert transcript.confidence == 1.0


# --------------------------------------------------------------------------
# the model's field names are ours
# --------------------------------------------------------------------------
def test_the_schema_offers_exactly_the_seven_compared_fields():
    """Pinned so the prompt's vocabulary cannot drift from the domain's."""
    assert get_args(scan._FieldName) == COMPARE_FIELDS
