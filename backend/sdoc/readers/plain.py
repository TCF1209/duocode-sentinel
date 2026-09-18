"""Plain-text attachment reader."""
from __future__ import annotations

from ..schema import ParsedDoc
from .rows import chunks_from_lines


def read(doc: ParsedDoc, data: bytes) -> ParsedDoc:
    if not data:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc

    text = data.decode("utf-8", errors="replace")
    if not text.strip():
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc

    doc.text = text
    doc.chunks = chunks_from_lines(text.splitlines())
    return doc
