"""Smoke test: read one attachment of every format and print what we got.

    python backend/tools/smoke_readers.py data/bundle

Not a unit test — a human-readable sanity check used while building the
readers. Real regression tests live in backend/tests/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdoc import labels                                   # noqa: E402
from sdoc.readers import read_attachment                  # noqa: E402

SAMPLES = [
    "attachments/email_004_SI.txt",    # plain text
    "attachments/email_004_BL.txt",
    "attachments/email_313_SI.pdf",    # two-column PDF form
    "attachments/email_313_BL.pdf",
    "attachments/email_097_SI.xlsx",   # excel SI
    "attachments/email_097_BL.docx",   # bilingual word BL
    "attachments/email_512_SI.pdf",    # edge case: scanned / empty / garbled
    "attachments/email_512_BL.pdf",
]


def main(root: str) -> None:
    for rel in SAMPLES:
        doc = read_attachment(root, rel)
        head = f"{rel}  [{doc.ext}]  {doc.n_bytes} bytes"
        print("\n" + "=" * 78)
        print(head)
        print("-" * 78)
        if not doc.readable:
            print(f"  UNREADABLE -> {doc.unreadable_reason}")
            for n in doc.notes:
                print(f"    note: {n}")
            continue

        resolved = 0
        for c in doc.chunks:
            field = labels.resolve(c.label)
            if field:
                resolved += 1
                value = c.value.splitlines()[0] if c.value else ""
                print(f"  {field:<18} <- {c.label!r:<42} = {value[:46]!r}  ({c.locator})")
        print(f"  ... {len(doc.chunks)} chunks, {resolved} resolved to a compared field")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/bundle")
