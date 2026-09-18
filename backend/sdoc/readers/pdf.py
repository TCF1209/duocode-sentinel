"""PDF attachment reader — layout-aware, coordinate based.

Why not just take the text layer?  Because the obvious approach silently
produces wrong answers on these documents.  A real SI in the dataset, read
with `pdftotext -layout`, comes out like this:

    Shipper/Exporter   APRIL FINE PAPER TRADING
                       ON BEHALF OF VITAL SOLUTIONS PTE LTD
    To the Order of    77 ROBINSON ROAD, #21-01      <-- NOT the consignee
    NOTIFY PARTY
    Load Port          8 TEMASEK BOULEVARD           <-- NOT the load port

The labels sit in a narrow left column and the values in a wider right column;
any line-oriented parser pairs a label with whatever address line happens to
sit beside it and then reports a *confident* false discrepancy.

So we work from word coordinates instead:

    1. group words into rows by their vertical position
    2. find the two dominant left edges on the page — the label column and the
       value column
    3. a row with words in both columns starts a new field; a row with words
       only in the value column continues the previous field's value

That reconstruction is deterministic, needs no LLM, and reproduces the
document exactly as a human reads it.
"""
from __future__ import annotations

import io
import logging
from collections import Counter

from ..schema import Chunk, ParsedDoc
from .rows import split_label_value

# pdfminer is chatty about fonts it cannot map; that is not our problem here.
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)

ROW_TOLERANCE = 3.0      # points; two words this close vertically share a row
COLUMN_TOLERANCE = 3.0   # points; clustering of left edges
MIN_TEXT_CHARS = 20      # below this we treat the page as having no text layer


def read(doc: ParsedDoc, data: bytes) -> ParsedDoc:
    if not data:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc

    try:
        import pdfplumber
    except ImportError:                                    # pragma: no cover
        doc.readable = False
        doc.unreadable_reason = "unsupported"
        doc.notes.append("pdfplumber is not installed")
        return doc

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [_page_words(p) for p in pdf.pages]
    except Exception as exc:
        # truncated file, no xref table, not a PDF at all
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"pdfplumber: {type(exc).__name__}: {exc}")
        return doc

    all_words = [w for page in pages for w in page]
    if not all_words:
        # a scanned / image-only PDF: the page renders fine but carries no
        # characters. This needs OCR or a vision model, not a text parser.
        doc.readable = False
        doc.unreadable_reason = "no_text_layer"
        doc.notes.append("PDF has no extractable text layer (image-only scan)")
        return doc

    chunks: list[Chunk] = []
    lines: list[str] = []
    order = 0

    for page_no, words in enumerate(pages, start=1):
        if not words:
            continue
        value_x = _value_column_x(words)
        for row_no, row in enumerate(_rows(words), start=1):
            left = [w for w in row if w["x0"] < value_x - COLUMN_TOLERANCE]
            right = [w for w in row if w["x0"] >= value_x - COLUMN_TOLERANCE]
            left_text = " ".join(w["text"] for w in left).strip()
            right_text = " ".join(w["text"] for w in right).strip()
            lines.append(" ".join(t for t in (left_text, right_text) if t))
            locator = f"p{page_no} r{row_no}"

            if not left_text:
                # continuation of the current field's value (address block)
                if chunks and right_text:
                    chunks[-1].value = f"{chunks[-1].value}\n{right_text}".strip()
                continue

            label, value = left_text, right_text
            # a label drawn as one string may carry its own colon and value,
            # e.g. "TOTAL GROSS WEIGHT: 118,270 KG"
            pair = split_label_value(left_text)
            if pair:
                label, inline = pair
                value = f"{inline} {right_text}".strip()

            if value:
                chunks.append(Chunk(label=label, value=value,
                                    locator=locator, order=order))
                order += 1
            else:
                # label with nothing beside it: the value is on the rows below
                chunks.append(Chunk(label=label, value="",
                                    locator=locator, order=order))
                order += 1

    doc.text = "\n".join(lines)
    doc.chunks = [c for c in chunks if c.value or c.label]

    if len(doc.text.strip()) < MIN_TEXT_CHARS:
        doc.readable = False
        doc.unreadable_reason = "no_text_layer"
        doc.notes.append("PDF text layer is too small to be a real document")
    return doc


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _page_words(page) -> list[dict]:
    try:
        return page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
    except Exception:
        return []


def _rows(words: list[dict]) -> list[list[dict]]:
    """Group words into visual rows, top to bottom, each sorted left to right."""
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if rows and abs(w["top"] - rows[-1][0]["top"]) <= ROW_TOLERANCE:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in rows]


def _value_column_x(words: list[dict]) -> float:
    """Left edge of the value column.

    Left edges cluster hard in a form layout. The value column is the *most
    populated* cluster to the right of the label margin, because every line of
    every multi-line value starts there — a six-field form with three address
    blocks puts fifteen or more words on that edge, while a table column to its
    right gets one per row.

    Taking the most populated cluster rather than the leftmost one matters: a
    multi-word label ("NOTIFY PARTY", "Port of Discharge") puts its second word
    at its own x, and choosing that as the split tears the label in half and
    glues its tail onto the value.

    Returns +inf for a single-column document, so every row is then treated as
    a label with an inline `Label: value`.
    """
    if not words:
        return 1e9

    # Bin left edges into fixed buckets. Single-linkage clustering is wrong
    # here: word starts are dense enough that a chain of near-neighbours merges
    # the whole page into one cluster and the "column" lands in open space.
    bin_of = lambda x: int(round(x / COLUMN_TOLERANCE))          # noqa: E731
    buckets: dict[int, list[float]] = {}
    for w in words:
        buckets.setdefault(bin_of(w["x0"]), []).append(w["x0"])

    label_margin = min(min(v) for v in buckets.values())
    threshold = max(3, int(0.04 * len(words)))
    candidates = {
        b: v for b, v in buckets.items()
        if min(v) > label_margin + 20 and len(v) >= threshold
    }
    if not candidates:
        return 1e9

    # The value column carries one word per line of every multi-line value, so
    # it is by a distance the most populated edge on the page. Ties break left.
    best = max(candidates, key=lambda b: (len(candidates[b]), -b))
    return min(candidates[best])


def dominant_left_edges(words: list[dict]) -> list[tuple[float, int]]:
    """Diagnostic helper used by tests and the /debug endpoint."""
    counts = Counter(round(w["x0"], 0) for w in words)
    return sorted(counts.items())
