"""Shared helper: turn a list of text lines into label/value chunks.

Used by the plain-text reader and, after column reconstruction, by the PDF
reader. A chunk starts at a line that looks like `Label: value`; any line that
follows and does *not* look like a new label is treated as a continuation of
the current value (this is how multi-line address blocks stay attached to the
party they belong to).
"""
from __future__ import annotations

import re

from .. import labels
from ..schema import Chunk

# "Shipper/Exporter: APRIL FINE PAPER" — a label is short, has letters, and is
# followed by a colon. The 60-char cap stops a sentence containing a colon
# ("Note: the second attachment is a Packing List") from starting a chunk.
_LABEL_LINE = re.compile(r"^(?P<label>[^:]{1,60}?)\s*:\s*(?P<value>.*)$")

# Forms do not agree on how to separate a label from its value. A colon is the
# common case; an em or en dash, or simply a wide gap, are just as readable to
# a person and appear throughout real carrier stationery. Measured against the
# adversarial harness, refusing to recognise these cost every field on the
# page — a safe failure (each case escalated, none were misread) but a useless
# one, because an inbox where nothing extracts is an inbox nobody uses.
_ALT_SEPARATOR = re.compile(
    r"^(?P<label>.{1,60}?)\s*(?:[–—―|]|\t|\s{2,})\s*(?P<value>\S.*)$"
)

# Decorative rules the generators draw under a title.
_RULE_LINE = re.compile(r"^[\s=_\-*~#]+$")


def _alt_split(text: str) -> tuple[str, str] | None:
    """Split on a non-colon separator, but only for a label we recognise.

    The guard is what makes this safe. A wide gap is far too common in prose
    and in table rows to treat as a label boundary on its own, so a split is
    only accepted when the left-hand side resolves to one of the seven
    compared fields. A sentence, an address line or a container row cannot
    pass that test, and nothing that used to parse changes behaviour.
    """
    match = _ALT_SEPARATOR.match(text)
    if not match:
        return None
    label = match.group("label").strip()
    if not label or labels.resolve(label) is None:
        return None
    return label, match.group("value").strip()


def chunks_from_lines(lines: list[str], *, locator_prefix: str = "line") -> list[Chunk]:
    """Build chunks from plain text lines, keeping a 1-based line locator."""
    chunks: list[Chunk] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if not line.strip() or _RULE_LINE.match(line.strip()):
            continue

        stripped = line.strip()
        indented = line[:1] in (" ", "\t")

        pair: tuple[str, str] | None = None
        m = _LABEL_LINE.match(stripped)
        if m and m.group("label").strip():
            pair = (m.group("label").strip(), m.group("value").strip())
        else:
            pair = _alt_split(stripped)

        # Indentation normally marks a continuation — an address block under
        # the party it belongs to. But a form that indents its whole field list
        # is still a form, so an indented line may start a field when its label
        # resolves to one of the seven. An address line cannot pass that test.
        if pair and indented and labels.resolve(pair[0]) is None:
            pair = None

        if pair:
            chunks.append(
                Chunk(label=pair[0], value=pair[1],
                      locator=f"{locator_prefix} {idx}", order=len(chunks))
            )
        elif chunks:
            # continuation of the previous value (address block, wrapped text)
            chunks[-1].value = f"{chunks[-1].value}\n{stripped}".strip()
    return chunks


def split_label_value(text: str) -> tuple[str, str] | None:
    """Split a single label/value string, or return None.

    Tries a colon first, then the alternative separators, which is what lets a
    PDF row drawn as one string ("TOTAL GROSS WEIGHT — 118,270 KG") still be
    read as a field.
    """
    stripped = text.strip()
    m = _LABEL_LINE.match(stripped)
    if m and m.group("label").strip():
        return m.group("label").strip(), m.group("value").strip()
    return _alt_split(stripped)
