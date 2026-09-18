"""Word (.docx) and Excel (.xlsx) attachment readers.

Both formats already carry the label/value structure we want:

    xlsx   column A = label, column B = value
    docx   a 2-column "Table Grid", one field per row

so reading them is mostly about producing a useful locator ("cell A7",
"table 1 row 3") and flattening the value to a string.
"""
from __future__ import annotations

import io

from ..schema import Chunk, ParsedDoc
from .rows import split_label_value


# --------------------------------------------------------------------------
# .xlsx
# --------------------------------------------------------------------------
def read_xlsx(doc: ParsedDoc, data: bytes) -> ParsedDoc:
    import openpyxl

    if not data:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:                      # corrupt / not really xlsx
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"openpyxl: {type(exc).__name__}: {exc}")
        return doc

    lines: list[str] = []
    chunks: list[Chunk] = []
    order = 0
    for ws in wb.worksheets:
        for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = ["" if c is None else str(c).strip() for c in row]
            while cells and not cells[-1]:
                cells.pop()
            if not cells:
                continue
            lines.append("\t".join(cells))

            label = cells[0]
            value = " ".join(cells[1:]).strip()
            if label and value:
                chunks.append(
                    Chunk(label=label, value=value,
                          locator=f"{ws.title}!A{r}", order=order)
                )
                order += 1
            elif label:
                # a single-cell row can still be "Label: value" written inline
                pair = split_label_value(label)
                if pair:
                    chunks.append(
                        Chunk(label=pair[0], value=pair[1],
                              locator=f"{ws.title}!A{r}", order=order)
                    )
                    order += 1

    wb.close()
    doc.text = "\n".join(lines)
    doc.chunks = chunks
    if not doc.text.strip():
        doc.readable = False
        doc.unreadable_reason = "empty_file"
    return doc


# --------------------------------------------------------------------------
# .docx
# --------------------------------------------------------------------------
def read_docx(doc: ParsedDoc, data: bytes) -> ParsedDoc:
    import docx

    if not data:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as exc:
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"python-docx: {type(exc).__name__}: {exc}")
        return doc

    lines: list[str] = []
    chunks: list[Chunk] = []
    order = 0

    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        lines.append(t)
        pair = split_label_value(t)
        if pair:
            chunks.append(Chunk(label=pair[0], value=pair[1],
                                locator=f"para {len(lines)}", order=order))
            order += 1

    for ti, table in enumerate(d.tables, start=1):
        for ri, row in enumerate(table.rows, start=1):
            cells = [c.text.strip() for c in row.cells]
            # python-docx repeats merged cells; collapse consecutive duplicates
            dedup: list[str] = []
            for c in cells:
                if not dedup or dedup[-1] != c:
                    dedup.append(c)
            if not any(dedup):
                continue
            lines.append(" | ".join(dedup))
            if len(dedup) >= 2 and dedup[0]:
                chunks.append(
                    Chunk(label=dedup[0], value=" ".join(x for x in dedup[1:] if x).strip(),
                          locator=f"table {ti} row {ri}", order=order)
                )
                order += 1

    doc.text = "\n".join(lines)
    doc.chunks = chunks
    if not doc.text.strip():
        doc.readable = False
        doc.unreadable_reason = "empty_file"
    return doc
