"""Fallback reader for attachment formats we have no precise reader for.

A real operations inbox does not restrict itself to four file types. People
attach `.pptx` decks, saved `.html` pages, `.msg` exports, `.csv` manifests and
photographs of documents. Refusing to open them would be honest but useless; the
pipeline should get what it can and say plainly how it read it.

So: the four formats we handle precisely (`.txt`, `.pdf`, `.docx`, `.xlsx`) keep
their own readers, and everything else falls through to Microsoft's markitdown,
which converts a wide range of formats to Markdown.

**The fallback is deliberately second choice, not the default.** Measured on our
own PDFs, markitdown returns the label and the value glued together with no
separator —

    | Load Port RUGAO/NANTONG/SHANGHAI, CHINA |  |  |

— where the coordinate reader returns `label='Load Port'`,
`value='RUGAO/NANTONG/SHANGHAI, CHINA'`, `locator='p1 r15'`. Recovering that
boundary would need either a fixed list of known labels, which fails on exactly
the "same field, different wording" problem this system exists to solve, or a
model call on every document. And a flat Markdown blob carries no provenance, so
the evidence gate would have nothing to trace a value back to.

Anything read this way is therefore marked `fallback_reader` in the document's
notes, and its chunks carry coarse locators. A field read only from a fallback
document is more likely to fail the evidence gate and reach a human — which is
the correct outcome for a format we have never seen before.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..schema import Chunk, ParsedDoc
from .rows import chunks_from_lines, split_label_value

# Markdown table rows: | Label | value | value |
_TABLE_PREFIX = "|"


def read(doc: ParsedDoc, data: bytes) -> ParsedDoc:
    if not data:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc

    try:
        from markitdown import MarkItDown
    except ImportError:                                   # pragma: no cover
        doc.readable = False
        doc.unreadable_reason = "unsupported"
        doc.notes.append("markitdown is not installed; no reader for this format")
        return doc

    # markitdown dispatches on the file extension, so it needs a real path.
    tmp_path: str | None = None
    try:
        suffix = doc.ext or Path(doc.path).suffix or ".bin"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        result = MarkItDown(enable_plugins=False).convert(tmp_path)
        text = (result.text_content or "").strip()
    except Exception as exc:
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"markitdown: {type(exc).__name__}: {exc}")
        return doc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not text:
        # A format markitdown understands but that carries no text — most often
        # an image-only document that needs OCR or a vision model.
        doc.readable = False
        doc.unreadable_reason = "no_text_layer"
        doc.notes.append("fallback_reader: converted but produced no text")
        return doc

    doc.text = text
    doc.chunks = _chunks_from_markdown(text)
    doc.notes.append("fallback_reader: markitdown")
    return doc


def _chunks_from_markdown(text: str) -> list[Chunk]:
    """Recover label/value pairs from markitdown's Markdown output.

    Two shapes appear in practice: pipe tables, where the first cell is the
    label, and plain `Label: value` lines. Separator rows (`| --- | --- |`) are
    skipped. Cells beyond the second are appended, because a value containing a
    literal `|` gets split across columns by the Markdown writer.
    """
    chunks: list[Chunk] = []
    plain_lines: list[str] = []

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            plain_lines.append("")
            continue

        if line.startswith(_TABLE_PREFIX):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not any(cells) or all(set(c) <= set("-: ") for c in cells if c):
                continue                                   # separator row
            label = cells[0]
            value = " ".join(c for c in cells[1:] if c).strip()
            if label and value:
                chunks.append(Chunk(label=label, value=value,
                                    locator=f"md line {idx}", order=len(chunks)))
            elif label:
                pair = split_label_value(label)
                if pair:
                    chunks.append(Chunk(label=pair[0], value=pair[1],
                                        locator=f"md line {idx}", order=len(chunks)))
            plain_lines.append("")
            continue

        plain_lines.append(line.lstrip("#").strip())

    # Plain `Label: value` lines outside any table.
    for chunk in chunks_from_lines(plain_lines, locator_prefix="md line"):
        chunk.order = len(chunks)
        chunks.append(chunk)

    return chunks
