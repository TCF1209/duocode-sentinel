"""Scanned-PDF transcription — evidence for a human, never an automatic answer.

**Read this paragraph before changing anything in this file.** An image-only
PDF is `unreadable`. `readers/pdf.py` says so (`no_text_layer`), the evidence
gate escalates on it, and the case ends in `NEEDS_REVIEW` with review reason
`unreadable`. That outcome is correct and this module does not change it. What
this module adds is the *reviewer's* side of that escalation: instead of "this
is a scan, go and open it yourself", the case arrives with the document already
read out loud. A transcript is context attached to an escalation, never grounds
for removing one.

That rule is why the module is shaped the way it is:

* `transcribe()` never sets `doc.readable`, never touches `doc.chunks`, and
  never writes `doc.text`. Populating any of those would make a scan look like
  a document the extractor had read, and a model-transcribed value would then
  flow into an automatic comparison — and worse, would *trace* against
  `doc.text` in the evidence gate, so the gate would be verifying the model
  against its own output. The transcript lands on `doc.notes` and on a separate
  attribute (`doc.scan_transcript`) that no extraction path reads.
* The model is asked to return an **empty string** for anything it cannot read
  with certainty. A reviewer who is told "gross weight: 128,544 KG" will act on
  it; guessing at a smudged figure is the single worst behaviour available
  here, so a blank is always the better answer and the prompt says so twice.
* Everything is a fallback. No key, no network, no `pypdfium2`, a refusal or a
  spent budget all return `None`, and the pipeline carries on exactly as it did
  before this module existed.

Costs are kept to what the job needs: at most two pages (an SI or a draft BL is
one, and a two-page BL puts the terms on the back), a capped pixel size so one
pathological file cannot dominate a batch run, and `reasoning_effort="low"` —
this is careful reading, not hard thinking.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .. import labels, normalize
from ..llm import LLMClient, LLMUnavailable
from ..schema import COMPARE_FIELDS, ParsedDoc

# Two pages is plenty for the documents this system sees: an SI is one page and
# a draft BL is one page of fields plus, at most, a page of printed terms that
# carries none of the seven. Capping the page count bounds the cost of a single
# attachment, so a 200-page scan cannot swallow a batch run's budget.
MAX_PAGES = 2

# Longest edge of a rendered page, in pixels. scale=2.0 on A4 gives 1191x1684,
# which gpt-5-mini reads correctly; the cap only bites on absurd page sizes,
# where rendering at the requested scale would produce an image whose token
# cost is out of proportion to the seven values we are after.
MAX_EDGE_PX = 2200

# Where the transcript is parked on a ParsedDoc. Deliberately not a schema
# field: nothing in `extract/`, `compare.py` or `evidence_gate.py` knows this
# name, so a transcript cannot reach an automatic decision by accident.
SCAN_ATTR = "scan_transcript"

_PURPOSE = "read_scan"


# --------------------------------------------------------------------------
# Public result types
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanField:
    """One of the seven fields as printed on the scan.

    `value` is verbatim — "6 x 40'HC", "128,544 KG" — because a reviewer is
    checking the transcript against the image, and a helpfully tidied number is
    a number they can no longer verify at a glance. `legible` false always
    means `value` is empty: a field we could not read has no value, not a
    guessed one.
    """

    field: str
    value: str
    legible: bool


@dataclass(frozen=True)
class ScanTranscript:
    """What a vision model read off a scanned document, for a human to check.

    Not an extraction result. It carries no `Evidence`, it is not a
    `FieldValue`, and no stage of the pipeline compares it against anything.
    """

    fields: list[ScanField]
    overall_legible: bool
    confidence: float
    model: str
    pages_read: int
    note: str

    @property
    def legible_count(self) -> int:
        return sum(1 for f in self.fields if f.legible)

    def as_dict(self) -> dict[str, Any]:
        """Shape for `report.json` and the review-queue UI."""
        return {
            "kind": "scan_transcript",
            "advisory": (
                "Transcribed from an image-only scan by a vision model. "
                "Reviewer evidence only — not a verified extraction."
            ),
            "fields": [
                {"field": f.field, "value": f.value, "legible": f.legible}
                for f in self.fields
            ],
            "overall_legible": self.overall_legible,
            "legible_count": self.legible_count,
            "confidence": round(self.confidence, 3),
            "model": self.model,
            "pages_read": self.pages_read,
            "note": self.note,
        }


# --------------------------------------------------------------------------
# The model's answer shape
# --------------------------------------------------------------------------
# A Literal rather than a free string: the model picks from our seven field
# names or the SDK rejects the answer, so a hallucinated field name can never
# reach `ScanField`. `test_scan.py` pins this list against COMPARE_FIELDS so
# the two cannot drift apart unnoticed.
_FieldName = Literal[
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]


class _ScanFieldOut(BaseModel):
    field: _FieldName
    value: str = Field(
        description="Exactly as printed, or an empty string if not legible."
    )
    legible: bool = Field(
        description="True only if the printed characters can be read with certainty."
    )


class _ScanReadout(BaseModel):
    fields: list[_ScanFieldOut]
    overall_legible: bool
    confidence: float


_INSTRUCTIONS = (
    "You are transcribing a scanned shipping document for a human operator at a "
    "freight desk. You are not deciding anything: you are reading the page out "
    "loud so the operator does not have to start from zero.\n"
    "Copy what is printed, character for character, including punctuation, "
    "separators and units. Do not tidy, expand, convert or correct anything.\n"
    "If a field is not printed on the page, or the printing is too faint, cut "
    "off or ambiguous to read with certainty, return an empty string and "
    "legible=false. A guess is worse than a blank here: the operator will act "
    "on what you write. Never infer a value from another field.\n"
    "Return all seven fields, in the order given."
)

# The label variants come from the real documents (docs/DATA_NOTES.md §2). The
# two that matter most are spelled out: "To the Order of" is the consignee, and
# "Notify Party/Intermediate Consignee" is the notify party even though the
# word "Consignee" appears in it.
_PROMPT_TEMPLATE = (
    "Transcribe these seven fields from the attached scan of {what}.\n"
    "  shipper            - 'Shipper', 'Shipper/Exporter', 'Shipper (Principal or Seller)'\n"
    "  consignee          - 'Consignee', 'Consignee (Non-Negotiable)', 'To the Order of'\n"
    "  notify_party       - 'Notify', 'Notify Party', 'Notify Party/Intermediate Consignee'\n"
    "                       (this label contains the word Consignee but is NOT the consignee)\n"
    "  port_of_loading    - 'Port of Loading', 'Load Port', 'POL'\n"
    "  port_of_discharge  - 'Port of Discharge', 'Discharge Port', 'POD'\n"
    "  container_count    - 'No. of Containers', 'Total Containers', 'Containers'\n"
    "  gross_weight_kg    - 'Gross Weight', 'Gross Wt (kgs)', 'TOTAL GROSS WEIGHT'\n"
    "\n"
    "For a party, transcribe the entity name line only, not the address block "
    "under it. For container_count and gross_weight_kg, transcribe the figure "
    "exactly as printed, keeping the units and any 'x 40HC' style suffix.\n"
    "confidence is your own 0-1 estimate of how much of this page you could read."
)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render_pages(data: bytes, max_pages: int = MAX_PAGES,
                 scale: float = 2.0) -> list[bytes]:
    """Render the first `max_pages` pages of a PDF to PNG bytes.

    Returns an empty list — never raises — when the bytes are not a PDF, when
    `pypdfium2` is missing, or when rendering fails. A document we cannot draw
    is simply a document we cannot transcribe, and the case was already headed
    for a human before we tried.

    Both caps are deliberate. `max_pages` bounds the cost of one attachment;
    `MAX_EDGE_PX` bounds the cost of one page, because image tokens scale with
    pixels and a poster-sized page would otherwise cost more than the whole
    rest of the inbox.
    """
    if not data:
        return []

    try:
        import pypdfium2 as pdfium
    except ImportError:                                    # pragma: no cover
        return []

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception:
        return []                                          # not a PDF, or truncated

    pages: list[bytes] = []
    try:
        for index in range(min(len(pdf), max(0, int(max_pages)))):
            try:
                page = pdf[index]
                # Page size is in points; rendered pixels are points * scale.
                longest = max(float(page.get_width()), float(page.get_height())) or 1.0
                effective = min(float(scale), MAX_EDGE_PX / longest)
                image = page.render(scale=max(effective, 0.1)).to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                pages.append(buffer.getvalue())
            except Exception:
                # One unrenderable page does not make the others worthless: a
                # scan whose second page is broken still has its first page,
                # and that is where the seven fields live.
                continue
    finally:
        try:
            pdf.close()
        except Exception:                                  # pragma: no cover
            pass
    return pages


# --------------------------------------------------------------------------
# Transcription
# --------------------------------------------------------------------------
def transcribe(doc: ParsedDoc, data: bytes, *,
               client: Optional[LLMClient] = None) -> Optional[ScanTranscript]:
    """Read a scanned document for the reviewer and attach the result to `doc`.

    Returns `None` when there is no client, no key or no budget, when the bytes
    are not a renderable PDF, or when the model is unavailable. Never raises:
    the pipeline that calls this has already decided the case needs a human,
    and a failed transcription must not turn a review case into a crash.

    It also never makes `doc` look readable. `doc.readable`,
    `doc.unreadable_reason`, `doc.chunks` and `doc.text` are left exactly as
    the reader set them, so the case still escalates with reason `unreadable`.
    """
    if client is None or not client.available:
        return None

    pages = render_pages(data)
    if not pages:
        return None

    try:
        readout = client.structured(
            purpose=_PURPOSE,
            instructions=_INSTRUCTIONS,
            prompt=_PROMPT_TEMPLATE.format(what=_describe(doc)),
            schema=_ScanReadout,
            images=pages,
            reasoning_effort="low",
        )
    except LLMUnavailable:
        # Normal operating state, not an error: no key, network down, refusal,
        # or the run budget is spent. The reviewer gets the escalation without
        # the transcript, which is what they had before this module existed.
        return None
    except Exception as exc:
        # A bug in the call path costs this one transcript, not the batch. Only
        # the exception *type* is recorded — a provider message can carry the
        # request payload, and nothing from this path belongs in a log.
        doc.notes.append(
            f"Scan transcription failed ({type(exc).__name__}); "
            "the document still needs to be read by hand."
        )
        return None

    transcript = _to_transcript(
        readout,
        model=client.settings.vision_model,
        pages_read=len(pages),
    )
    attach(doc, transcript)
    return transcript


def attach(doc: ParsedDoc, transcript: ScanTranscript) -> None:
    """Park the transcript on the document as reviewer evidence.

    Touches `notes` and one extra attribute and nothing else. In particular it
    does not write `doc.text`: the evidence gate traces extracted values
    against `doc.text`, so a transcript written there would let a model's own
    output vouch for a model's own reading — the one thing the gate exists to
    prevent.
    """
    setattr(doc, SCAN_ATTR, transcript)
    doc.notes.append(transcript.note)


def transcript_of(doc: ParsedDoc) -> Optional[ScanTranscript]:
    """The transcript attached to `doc`, if any. For the report and the UI."""
    value = getattr(doc, SCAN_ATTR, None)
    return value if isinstance(value, ScanTranscript) else None


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _describe(doc: ParsedDoc) -> str:
    """What to tell the model the page is, without telling it what to find.

    The role hint comes from the filename, which is a hint and nothing more
    (`readers.role_hint`). It is passed as context for layout, never as an
    instruction — the model transcribes whatever is printed either way.
    """
    if doc.role_hint == "SI":
        return "a Shipping Instruction"
    if doc.role_hint == "BL":
        return "a draft Bill of Lading"
    return "a shipping document"


def _to_transcript(readout: _ScanReadout, *, model: str,
                   pages_read: int) -> ScanTranscript:
    """Normalise the model's answer into exactly seven fields, in our order.

    Three things are enforced here rather than trusted:

    * all seven fields exist, so the UI never has to handle a missing one;
    * a value the document does not really state ("???", "N/A", whitespace) is
      a blank, not a reading — `normalize.is_blank` already knows every shape
      a placeholder takes in this dataset;
    * `legible=false` wins over any text that came with it. A model that
      hedges by returning both a guess and a low flag must not leave the guess
      in front of a reviewer.
    """
    seen: dict[str, _ScanFieldOut] = {}
    for item in readout.fields or []:
        seen.setdefault(item.field, item)          # first answer per field wins

    fields: list[ScanField] = []
    for name in COMPARE_FIELDS:
        item = seen.get(name)
        value = (item.value or "").strip() if item is not None else ""
        value = _without_caption(name, value)
        legible = bool(item.legible) if item is not None else False
        if not legible or normalize.is_blank(value):
            value, legible = "", False
        fields.append(ScanField(field=name, value=value, legible=legible))

    legible_count = sum(1 for f in fields if f.legible)
    # A claim of "overall legible" with nothing legible in it is a contradiction;
    # believe the fields, which are the part a reviewer can check.
    overall = bool(readout.overall_legible) and legible_count > 0
    confidence = min(1.0, max(0.0, float(readout.confidence or 0.0)))

    return ScanTranscript(
        fields=fields,
        overall_legible=overall,
        confidence=confidence,
        model=model,
        pages_read=pages_read,
        note=_note(legible_count, len(fields), confidence, pages_read, model),
    )


def _without_caption(field: str, value: str) -> str:
    """The value without a printed caption the model copied in front of it.

    On some runs the model answers "Shipper: APRIL FAR EAST (M) SDN BHD" for
    the shipper. Accepted as a reviewer correction, the caption is compared as
    part of the name, and every field of an agreeing pair turns into a
    discrepancy. Only a caption the label table resolves to this same field is
    dropped, so a colon inside a real value stays where it is.
    """
    head, sep, rest = value.partition(":")
    if sep and rest.strip() and labels.resolve(head) == field:
        return rest.strip()
    return value


def _note(legible_count: int, total: int, confidence: float,
          pages_read: int, model: str) -> str:
    """The one line a reviewer sees in the queue.

    It ends with the escalation, not with the transcript, because that is the
    part somebody skimming a work list has to come away with.
    """
    pages = "page" if pages_read == 1 else "pages"
    return (
        f"Scan transcribed by {model} from {pages_read} {pages}: "
        f"{legible_count}/{total} fields legible, confidence {confidence:.2f}. "
        "Reviewer evidence only — the scan still has no text layer, so this "
        "case stays in review and the values must be confirmed against the image."
    )


__all__ = [
    "MAX_PAGES",
    "MAX_EDGE_PX",
    "SCAN_ATTR",
    "ScanField",
    "ScanTranscript",
    "attach",
    "render_pages",
    "transcribe",
    "transcript_of",
]
