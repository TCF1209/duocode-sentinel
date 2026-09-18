"""Attachment reading — one entry point, four formats, one output shape.

Every reader returns a `ParsedDoc`. A document that cannot be read is not an
exception: it comes back with `readable=False` and an `unreadable_reason`, and
the pipeline turns that into a review case rather than a crash or a guess.

    empty_file      the file is 0 bytes, or decodes to nothing
    corrupt         the bytes are not a valid file of that type
    no_text_layer   a PDF that renders but carries no characters (a scan)
    unsupported     an extension we have no reader for
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..schema import ParsedDoc
from . import office, pdf, plain

# Guardrail: an attachment larger than this is a configuration problem, not a
# document, and must not be loaded into memory during a batch run.
MAX_BYTES = 25 * 1024 * 1024

_READERS = {
    ".txt": plain.read,
    ".text": plain.read,
    ".csv": plain.read,
    ".pdf": pdf.read,
    ".docx": office.read_docx,
    ".xlsx": office.read_xlsx,
    ".xlsm": office.read_xlsx,
}


def role_hint(path: str) -> str:
    """Whether the filename suggests this is the SI or the BL.

    A hint only. The authoritative answer comes from `doctype.py`, which reads
    the document's own content — a file called `..._BL.txt` that turns out to
    be a Commercial Invoice is exactly the case we must catch.
    """
    stem = Path(path).stem.upper()
    if stem.endswith("_SI") or "_SI_" in stem or stem.endswith("SI"):
        return "SI"
    if stem.endswith("_BL") or "_BL_" in stem or stem.endswith("BL"):
        return "BL"
    return "?"


def read_attachment(root: str | os.PathLike, rel_path: str) -> ParsedDoc:
    """Read one attachment referenced by an email record.

    `rel_path` is the string exactly as it appears in `email["attachments"]`,
    e.g. "attachments/email_004_SI.txt".
    """
    full = Path(root) / rel_path
    ext = full.suffix.lower()
    doc = ParsedDoc(path=rel_path, ext=ext, role_hint=role_hint(rel_path))

    if not full.exists():
        doc.readable = False
        doc.unreadable_reason = "missing_file"
        doc.notes.append(f"{rel_path} is referenced by the email but not present")
        return doc

    try:
        size = full.stat().st_size
    except OSError as exc:
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"stat failed: {exc}")
        return doc

    doc.n_bytes = size
    if size == 0:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        doc.notes.append("file is 0 bytes")
        return doc

    if size > MAX_BYTES:
        doc.readable = False
        doc.unreadable_reason = "unsupported"
        doc.notes.append(f"file is {size} bytes, above the {MAX_BYTES} limit")
        return doc

    reader = _READERS.get(ext)
    if reader is None:
        doc.readable = False
        doc.unreadable_reason = "unsupported"
        doc.notes.append(f"no reader for '{ext}'")
        return doc

    try:
        data = full.read_bytes()
    except OSError as exc:
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"read failed: {exc}")
        return doc

    try:
        doc = reader(doc, data)
    except Exception as exc:                       # a reader must never escape
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"{type(exc).__name__}: {exc}")
        return doc

    # Late guard: a reader can succeed structurally and still return nothing
    # useful — e.g. a PDF whose only content is a scanned image.
    if doc.readable and not doc.text.strip():
        doc.readable = False
        doc.unreadable_reason = doc.unreadable_reason or "empty_file"

    return doc


def read_all(root: str | os.PathLike, paths: list[str]) -> list[ParsedDoc]:
    return [read_attachment(root, p) for p in paths]


__all__ = ["read_attachment", "read_all", "role_hint", "ParsedDoc", "MAX_BYTES"]
