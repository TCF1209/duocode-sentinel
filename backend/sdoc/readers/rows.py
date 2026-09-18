"""Shared helper: turn a list of text lines into label/value chunks.

Used by the plain-text reader and, after column reconstruction, by the PDF
reader. A chunk starts at a line that looks like `Label: value`; any line that
follows and does *not* look like a new label is treated as a continuation of
the current value (this is how multi-line address blocks stay attached to the
party they belong to).
"""
from __future__ import annotations

import re

from ..schema import Chunk

# "Shipper/Exporter: APRIL FINE PAPER" — a label is short, has letters, and is
# followed by a colon. The 60-char cap stops a sentence containing a colon
# ("Note: the second attachment is a Packing List") from starting a chunk.
_LABEL_LINE = re.compile(r"^(?P<label>[^:]{1,60}?)\s*:\s*(?P<value>.*)$")

# Decorative rules the generators draw under a title.
_RULE_LINE = re.compile(r"^[\s=_\-*~#]+$")


def chunks_from_lines(lines: list[str], *, locator_prefix: str = "line") -> list[Chunk]:
    """Build chunks from plain text lines, keeping a 1-based line locator."""
    chunks: list[Chunk] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if not line.strip() or _RULE_LINE.match(line.strip()):
            continue

        indented = line[:1] in (" ", "\t")
        m = None if indented else _LABEL_LINE.match(line.strip())

        if m and m.group("label").strip():
            chunks.append(
                Chunk(
                    label=m.group("label").strip(),
                    value=m.group("value").strip(),
                    locator=f"{locator_prefix} {idx}",
                    order=len(chunks),
                )
            )
        elif chunks:
            # continuation of the previous value (address block, wrapped text)
            chunks[-1].value = f"{chunks[-1].value}\n{line.strip()}".strip()
    return chunks


def split_label_value(text: str) -> tuple[str, str] | None:
    """Split a single `Label: value` string, or return None."""
    m = _LABEL_LINE.match(text.strip())
    if not m or not m.group("label").strip():
        return None
    return m.group("label").strip(), m.group("value").strip()
