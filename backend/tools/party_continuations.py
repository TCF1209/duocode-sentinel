"""How often a party value is followed by a line with no label of its own.

    python backend/tools/party_continuations.py bundle_data

The measurement behind docs/ADVERSARIAL.md §5.2: why the obvious guard
against a wrapped party name -- "distrust a value when an unlabelled line
follows it" -- costs more than the one case it would catch (`email_145`).
That line is the only signal such a guard has, and it is also the ordinary
shape of a party field: a name, then its address block.

Both counts use the readers' own rule for a continuation (readers/rows.py
`chunks_from_lines`: a line that starts no new label is attached to the value
above it, and a decorative rule is skipped):

* per label line -- every Shipper / Consignee / Notify label line in the .txt
  attachments, and whether the reader attaches the next line to its value;
* per SI/BL pair -- whether either document, in any format, has a party value
  (a label resolving to shipper, consignee or notify_party) that runs onto a
  further line. A comparison that refused to auto-match such a value would
  escalate every pair counted here.

Not a unit test and not part of the pipeline: a reproducible number for a
document. Written on 25 Sep, when the 24 Sep figure ("485 of 530") would not
reproduce -- that was a miscount, and this is the count.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdoc import labels                                   # noqa: E402
from sdoc.readers import read_attachment                  # noqa: E402
from sdoc.readers.rows import _RULE_LINE, chunks_from_lines  # noqa: E402

PARTY = {"shipper", "consignee", "notify_party"}
# The label lines §5.2 names: the three words themselves, in any case.
PARTY_LABEL_LINE = re.compile(r"^\s*(shipper|consignee|notify)\b[^:]{0,60}:", re.I)


def _pct(n: int, d: int) -> str:
    return f"{n / d:4.0%}" if d else "   -"


def per_label_line(att: Path) -> None:
    total: Counter[str] = Counter()
    attached: Counter[str] = Counter()
    for f in sorted(att.glob("*.txt")):
        lines = f.read_bytes().decode("utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            m = PARTY_LABEL_LINE.match(line)
            if not m:
                continue
            word = m.group(1).lower()
            total[word] += 1
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt.strip() and not _RULE_LINE.match(nxt.strip()) and len(chunks_from_lines([line, nxt])) == 1:
                attached[word] += 1

    print("party label lines in the .txt attachments, next line attached to the value:")
    for word in ("shipper", "consignee", "notify"):
        print(f"  {word:10s} {attached[word]:4d} / {total[word]:4d}  {_pct(attached[word], total[word])}")
    n, d = sum(attached.values()), sum(total.values())
    print(f"  {'all':10s} {n:4d} / {d:4d}  {_pct(n, d)}")


def per_pair(root: Path) -> None:
    docs: dict[str, dict[str, object]] = {}
    for f in sorted((root / "attachments").iterdir()):
        stem, _, role = f.stem.rpartition("_")
        if role in ("SI", "BL"):
            docs.setdefault(stem, {})[role] = read_attachment(root, f"attachments/{f.name}")
    pairs = {k: v for k, v in docs.items() if set(v) == {"SI", "BL"}}

    flagged = 0
    not_flagged: Counter[str] = Counter()
    for pair in pairs.values():
        if any(labels.resolve(c.label) in PARTY and "\n" in c.value
               for doc in pair.values() for c in doc.chunks):
            flagged += 1
        elif any(not doc.readable for doc in pair.values()):
            not_flagged["could not be read"] += 1
        elif any(doc.ext == ".xlsx" for doc in pair.values()):
            not_flagged["spreadsheet (a cell does not wrap)"] += 1
        else:
            not_flagged["no party value runs on"] += 1

    print("\nSI/BL pairs, every format, with a party value that runs onto a further line:")
    print(f"  {flagged} / {len(pairs)}  {_pct(flagged, len(pairs))}")
    for why, n in not_flagged.most_common():
        print(f"  not flagged: {n} -- {why}")


if __name__ == "__main__":
    data = Path(sys.argv[1] if len(sys.argv) > 1 else "bundle_data")
    per_label_line(data / "attachments")
    per_pair(data)
