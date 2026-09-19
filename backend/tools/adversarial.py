#!/usr/bin/env python3
"""Adversarial self-consistency harness — does the pipeline *read*, or recognise?

    python backend/tools/adversarial.py
    python backend/tools/adversarial.py --data data/bundle --limit 20
    python backend/tools/adversarial.py --only ocr_confusions,wrapped_value

Why this exists
---------------
Sentinel scores 1.0000 on four independent draws from one dataset generator.
That proves it has not memorised a particular draw. It proves nothing about a
document whose *wording or layout* the generator never emits — and an ops inbox
is full of those, because every carrier and every forwarder prints its own form.

So this harness does not need labels, and deliberately does not have any:

    Extraction from the UNPERTURBED document is the reference.
    Perturb the document so a human would still read it identically.
    Extract again. Any field whose value moved is *our* failure, not the
    document's.

That is a self-consistency test. It cannot be gamed by tuning against an answer
key because there is no answer key involved — `data/_grader/` is never opened.

What is perturbed, and what is not
----------------------------------
Only the `.txt` attachments. The `.txt` renderer is the one we can perturb
faithfully: a text file *is* its own layout, so "put the value on the next
line" means exactly that. Rewriting a PDF's word coordinates or a .docx's table
cells to simulate the same thing would be simulating our own reader's input
rather than a real document, and a harness that tests a mock is worth nothing.
The binary formats are therefore out of scope here and stay untouched; their
layout risk is a separate exercise that needs real re-rendered files.

One document at a time
----------------------
Each perturbation is applied to **one half of a pair**, never to both. That is
both more faithful and more revealing. Faithful, because the SI comes from the
shipper's system and the BL from the carrier's — a template change hits one of
them, which is exactly why the two documents already use different labels for
the same fact. Revealing, because corrupting both sides identically hides the
damage: two documents misread the same way still agree, and the harness would
report a clean bill of health it has not earned.

What counts as a failure, and which failures matter
---------------------------------------------------
A field that stops extracting and correctly escalates to NEEDS_REVIEW is a
**good** outcome: recall was lost, trust was not. It is counted, separately.

A field that quietly extracts a *different* value and is still auto-decided is
the expensive one: it is how a confident false discrepancy reaches an operator.
Reports are therefore ranked by the defects they invent, then by the real
defects they mask, then by silent wrong values.

The `control_rewrite` perturbation changes nothing at all. It exists so the
harness can be caught lying: if the control ever reports a changed field, the
measurement apparatus is broken and every other row is suspect.

Which pipeline is measured
--------------------------
The deterministic one, by default: `PipelineConfig(llm=None)`. Three reasons,
in order of weight. The model layer is a *fallback*, so the rule reader has to
be safe on its own — an unseen label that the rules misread must not become a
false discrepancy just because a model usually rescues it. Measurement must be
deterministic, and a sampled model answer is not. And this harness runs the
pipeline a few thousand times; doing that against a paid API would spend the
whole run budget on a diagnostic. Pass `run(..., llm=client)` to measure the
assisted path instead, with `--limit` small enough to afford it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdoc import labels                                        # noqa: E402
from sdoc.extract import fields as extract_mod                 # noqa: E402
from sdoc.pipeline import Pipeline, PipelineConfig, build_client   # noqa: E402
from sdoc.readers import read_attachment, role_hint            # noqa: E402
from sdoc.schema import (                                      # noqa: E402
    COMPARE_FIELDS,
    PARTY_FIELDS,
    CaseResult,
    EmailRecord,
)

# --------------------------------------------------------------------------
# Text surgery primitives
# --------------------------------------------------------------------------
# Mirrors readers/rows.py's label regex, with the separator captured so an
# untouched line can be reproduced character for character. If this drifts from
# rows.py the harness starts perturbing lines the reader never treated as
# labels, and the numbers stop meaning anything — `control_rewrite` is the
# tripwire for exactly that.
_LABEL_LINE = re.compile(r"^(?P<label>[^:]{1,60}?)(?P<sep>\s*:\s*)(?P<value>.*)$")

NBSP = chr(0x00A0)      # a non-breaking space, spelled out: invisible in source
EM_DASH = chr(0x2014)   # an em dash
REFLOW_INDENT = "    "

# Where a long party name is broken. Real forms give the value column roughly
# this much room before the print driver wraps it.
WRAP_COLUMN = 24


@dataclass
class _Block:
    """One `Label: value` line plus every line that continues it.

    The continuation lines (`tail`) are carried verbatim and never rewritten:
    they are address blocks, and the extractor only ever reads the first
    segment of a value, so touching them would measure nothing.
    """

    label: Optional[str]          # None for the preamble / decoration block
    sep: str
    value: str
    tail: list[str] = dc_field(default_factory=list)
    field: Optional[str] = None   # which of the seven, if this label resolves

    @property
    def is_field(self) -> bool:
        return self.field is not None

    def lines(self) -> list[str]:
        if self.label is None:
            return list(self.tail)
        return [f"{self.label}{self.sep}{self.value}"] + list(self.tail)


def _parse(text: str) -> list[_Block]:
    """Split a document into label blocks, the way the .txt reader sees it."""
    preamble = _Block(None, "", "", [], None)
    blocks: list[_Block] = [preamble]
    current = preamble
    for raw in text.splitlines():
        # An indented line is a continuation for readers/rows.py, so it is one
        # here too: starting a block on it would perturb a line the extractor
        # never resolved.
        m = None
        if raw.strip() and raw[:1] not in (" ", "\t"):
            m = _LABEL_LINE.match(raw)
        if m and m.group("label").strip():
            current = _Block(
                label=m.group("label"),
                sep=m.group("sep"),
                value=m.group("value"),
                tail=[],
                field=labels.resolve(m.group("label").strip()),
            )
            blocks.append(current)
        else:
            current.tail.append(raw)
    return blocks


def _join(original: str, lines: Sequence[str]) -> str:
    text = "\n".join(lines)
    if original.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text


def _rewrite(text: str, fn: Callable[[_Block], list[str]]) -> str:
    """Apply `fn` to every block whose label resolves to one of the seven."""
    out: list[str] = []
    for block in _parse(text):
        out.extend(fn(block) if block.is_field else block.lines())
    return _join(text, out)


# --------------------------------------------------------------------------
# 1. Unseen label wording
#
# Deliberately chosen NOT to appear in labels.SYNONYMS. Every one of them is
# ordinary shipping English that some forwarder's template really does print;
# none of them is in our table, which is the whole point. If the pipeline only
# reads labels it was told about, this is where that shows.
# --------------------------------------------------------------------------
UNSEEN_LABELS: dict[str, str] = {
    "shipper": "Shipped By",
    "consignee": "Deliver To",
    "notify_party": "Send Notice To",
    "port_of_loading": "Loading Terminal",
    "port_of_discharge": "Final Destination Port",
    "container_count": "Boxes",
    "gross_weight_kg": "Total Wt.",
}


def _unseen_label(b: _Block) -> list[str]:
    return [f"{UNSEEN_LABELS[b.field]}{b.sep}{b.value}"] + b.tail


# --------------------------------------------------------------------------
# 2. Reflowed value — the value under its label instead of beside it
# --------------------------------------------------------------------------
def _reflow_indented(b: _Block) -> list[str]:
    if not b.value.strip():
        return b.lines()
    return [f"{b.label}:", f"{REFLOW_INDENT}{b.value.strip()}"] + b.tail


def _reflow_flush(b: _Block) -> list[str]:
    if not b.value.strip():
        return b.lines()
    return [f"{b.label}:", b.value.strip()] + b.tail


# --------------------------------------------------------------------------
# 3. Wrapped value — a long party name broken across two lines
# --------------------------------------------------------------------------
def _wrapped_value(b: _Block) -> list[str]:
    # Parties only: they are the values long enough to wrap in a real form, and
    # they are where a truncated read turns into a false discrepancy, because
    # the entity pools contain names that are prefixes of other names.
    if b.field not in PARTY_FIELDS:
        return b.lines()
    value = b.value.strip()
    if len(value) <= WRAP_COLUMN:
        return b.lines()
    cut = value.rfind(" ", 0, WRAP_COLUMN + 1)
    if cut <= 0:
        return b.lines()
    return [f"{b.label}{b.sep}{value[:cut]}",
            f"{REFLOW_INDENT}{value[cut + 1:]}"] + b.tail


# --------------------------------------------------------------------------
# 4. Punctuation drift
# --------------------------------------------------------------------------
def _no_colon(b: _Block) -> list[str]:
    # Column-aligned forms separate label from value with whitespace alone.
    return [f"{b.label}  {b.value}"] + b.tail


def _em_dash(b: _Block) -> list[str]:
    return [f"{b.label} {EM_DASH} {b.value}"] + b.tail


def _nbsp(b: _Block) -> list[str]:
    # A non-breaking space is what a word processor leaves behind when someone
    # stops a label wrapping; it looks identical on paper.
    return [f"{b.label.replace(' ', NBSP)}:{NBSP}{b.value}"] + b.tail


def _double_space(b: _Block) -> list[str]:
    return [f"{b.label}:  {b.value}"] + b.tail


def _tab_separator(b: _Block) -> list[str]:
    return [f"{b.label}:\t{b.value}"] + b.tail


# --------------------------------------------------------------------------
# 5. Case and spacing noise
# --------------------------------------------------------------------------
def _upper_labels(b: _Block) -> list[str]:
    return [f"{b.label.upper()}{b.sep}{b.value}"] + b.tail


def _lower_labels(b: _Block) -> list[str]:
    return [f"{b.label.lower()}{b.sep}{b.value}"] + b.tail


def _inner_spaces(b: _Block) -> list[str]:
    return [f"{b.label.replace(' ', '  ')} :  {b.value}"] + b.tail


def _indented_label(b: _Block) -> list[str]:
    # A whole form block indented under a section heading. A human reads it
    # identically; a line-oriented parser may not, because indentation is how
    # continuation lines are recognised.
    return [f"   {b.label}{b.sep}{b.value}"] + b.tail


# --------------------------------------------------------------------------
# 6. OCR-style confusions — reported separately, and here is why
#
# Every other perturbation preserves the characters of the value, so a changed
# reading is unambiguously our fault. This one does not: it edits the value
# itself, the way a scanner does. A human still reads "NANT0NG" as NANTONG, so
# a flagged difference is still a false alarm — but a numeric field genuinely
# becomes a different number, and lumping that in with the layout modes would
# overstate them. Sparse on purpose (one character per value): real OCR smudges
# a glyph, it does not transliterate a document.
# --------------------------------------------------------------------------
_OCR_MAP = {
    "O": "0", "0": "O",
    "I": "1", "1": "I", "l": "1",
    "S": "5", "5": "S",
    "B": "8", "8": "B",
}


def _ocr_swap(value: str, limit: int = 1) -> str:
    out = list(value)
    hits = 0
    for i, ch in enumerate(out):
        if hits >= limit:
            break
        replacement = _OCR_MAP.get(ch)
        if replacement is None:
            continue
        out[i] = replacement
        hits += 1
    return "".join(out)


def _ocr_confusions(b: _Block) -> list[str]:
    return [f"{b.label}{b.sep}{_ocr_swap(b.value)}"] + b.tail


# --------------------------------------------------------------------------
# 7. Reordered fields — the same seven facts, printed in a different order
# --------------------------------------------------------------------------
def _reordered_fields(text: str) -> str:
    blocks = _parse(text)
    slots = [i for i, b in enumerate(blocks) if b.is_field]
    shuffled = list(blocks)
    # Reverse the seven among their own positions: every field lands somewhere
    # it has never been, while non-field blocks (title, vessel, freight) stay
    # put, so the document still reads as a shipping document.
    for slot, source in zip(slots, reversed(slots)):
        shuffled[slot] = blocks[source]
    lines: list[str] = []
    for b in shuffled:
        lines.extend(b.lines())
    return _join(text, lines)


# --------------------------------------------------------------------------
# The switchboard
# --------------------------------------------------------------------------
PERTURBATIONS: dict[str, Callable[[str], str]] = {
    # The control: parse and re-render, change nothing. A non-zero row here
    # means the harness itself is broken.
    "control_rewrite": lambda t: _rewrite(t, lambda b: b.lines()),

    "unseen_labels": lambda t: _rewrite(t, _unseen_label),

    "reflow_indented": lambda t: _rewrite(t, _reflow_indented),
    "reflow_next_line": lambda t: _rewrite(t, _reflow_flush),

    "wrapped_value": lambda t: _rewrite(t, _wrapped_value),

    "punct_no_colon": lambda t: _rewrite(t, _no_colon),
    "punct_em_dash": lambda t: _rewrite(t, _em_dash),
    "punct_nbsp": lambda t: _rewrite(t, _nbsp),
    "punct_double_space": lambda t: _rewrite(t, _double_space),
    "punct_tab": lambda t: _rewrite(t, _tab_separator),

    "case_upper_labels": lambda t: _rewrite(t, _upper_labels),
    "case_lower_labels": lambda t: _rewrite(t, _lower_labels),
    "label_inner_spaces": lambda t: _rewrite(t, _inner_spaces),
    "label_indented": lambda t: _rewrite(t, _indented_label),

    "ocr_confusions": lambda t: _rewrite(t, _ocr_confusions),

    "reordered_fields": _reordered_fields,
}

#: Which of the seven families a perturbation belongs to, for the report.
FAMILIES: dict[str, str] = {
    "control_rewrite": "control",
    "unseen_labels": "unseen label wording",
    "reflow_indented": "reflowed value",
    "reflow_next_line": "reflowed value",
    "wrapped_value": "wrapped value",
    "punct_no_colon": "punctuation drift",
    "punct_em_dash": "punctuation drift",
    "punct_nbsp": "punctuation drift",
    "punct_double_space": "punctuation drift",
    "punct_tab": "punctuation drift",
    "case_upper_labels": "case and spacing noise",
    "case_lower_labels": "case and spacing noise",
    "label_inner_spaces": "case and spacing noise",
    "label_indented": "case and spacing noise",
    "ocr_confusions": "OCR-style confusion",
    "reordered_fields": "reordered fields",
}

#: Perturbations that edit the characters of a value rather than its layout.
#: Their numeric changes are partly legitimate, so they are ranked apart.
VALUE_ALTERING: frozenset[str] = frozenset({"ocr_confusions"})


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldOutcome:
    """How one field fared across every perturbed document.

    Only documents whose *baseline* read produced a usable value are counted:
    a field the pipeline never extracted in the first place has no reference to
    move away from, and counting it would flatter or damn the harness at random.
    """

    field: str
    unchanged: int
    changed: int
    lost: int

    @property
    def total(self) -> int:
        return self.unchanged + self.changed + self.lost

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "unchanged": self.unchanged,
                "changed": self.changed, "lost": self.lost}


@dataclass(frozen=True)
class PerturbationReport:
    """One perturbation, measured over every readable .txt document.

    The first six attributes are the agreed contract. The rest are additive,
    defaulted, and exist because the brief asks what happens *downstream* —
    "does the final decision change" — and the six have nowhere to put it.
    They never change how the first six are computed.
    """

    name: str
    documents: int
    per_field: list[FieldOutcome]
    silent_wrong_values: int      # extracted, different, and NOT escalated
    escalated: int                # read failed (or moved) and we asked a human
    examples: list[dict]          # before/after, at most 5, worst first

    family: str = ""
    value_altering: bool = False
    lost_not_escalated: int = 0   # field vanished and nobody was told
    decisions_changed: int = 0    # status / defect set / reason differs
    false_discrepancies: int = 0  # we invented a defect that is not there
    masked_discrepancies: int = 0 # we lost a real defect without escalating
    escalations_gained: int = 0   # auto-decided before, human-reviewed after

    # ---- aggregates -------------------------------------------------------
    @property
    def unchanged(self) -> int:
        return sum(o.unchanged for o in self.per_field)

    @property
    def changed(self) -> int:
        return sum(o.changed for o in self.per_field)

    @property
    def lost(self) -> int:
        return sum(o.lost for o in self.per_field)

    @property
    def measured(self) -> int:
        return sum(o.total for o in self.per_field)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "value_altering": self.value_altering,
            "documents": self.documents,
            "fields_measured": self.measured,
            "unchanged": self.unchanged,
            "changed": self.changed,
            "lost": self.lost,
            "per_field": [o.as_dict() for o in self.per_field],
            "silent_wrong_values": self.silent_wrong_values,
            "escalated": self.escalated,
            "lost_not_escalated": self.lost_not_escalated,
            "decisions_changed": self.decisions_changed,
            "false_discrepancies": self.false_discrepancies,
            "masked_discrepancies": self.masked_discrepancies,
            "escalations_gained": self.escalations_gained,
            "examples": list(self.examples),
        }


def severity(report: PerturbationReport) -> tuple[int, ...]:
    """Ranking key: invented defects first, because those are what cost trust."""
    return (
        report.false_discrepancies,
        report.masked_discrepancies,
        report.silent_wrong_values,
        report.lost_not_escalated,
        report.changed,
        report.lost,
    )


# --------------------------------------------------------------------------
# Reading one document, twice
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class _FieldRead:
    present: bool
    key: Optional[tuple]          # the value as the comparison will see it
    raw: Optional[str]
    label: Optional[str]
    locator: Optional[str]
    snippet: Optional[str]


@dataclass(frozen=True)
class _DocRead:
    readable: bool
    fields: dict[str, _FieldRead]


def _read_doc(root: Path, rel: str) -> _DocRead:
    """Extract the seven fields from one attachment, exactly as the pipeline does.

    The comparison key is `(normalised, number)` — the canonical form
    `compare.py` actually tests for equality — not the raw text. A value that is
    re-wrapped but canonicalises identically has not changed the answer, and
    calling that a failure would inflate every row in the table.

    Always the rule extractor, even when `run(llm=...)` is measuring the
    assisted pipeline downstream. The per-field table is about what our parser
    reads off the page; the model layer's contribution shows up where it
    matters, in the decision the case ends on.
    """
    doc = read_attachment(root, rel)
    hint = role_hint(rel)
    doc_fields = extract_mod.extract_fields(doc, hint if hint != "?" else "SI")
    out: dict[str, _FieldRead] = {}
    for name in COMPARE_FIELDS:
        fv = doc_fields.get(name)
        ev = fv.evidence
        out[name] = _FieldRead(
            present=bool(fv.present),
            key=(fv.normalised, fv.number) if fv.present else None,
            raw=fv.raw,
            label=ev.label if ev else None,
            locator=ev.locator if ev else None,
            snippet=ev.snippet if ev else None,
        )
    return _DocRead(readable=doc.readable, fields=out)


@dataclass(frozen=True)
class _Pair:
    email: EmailRecord
    docs: tuple[str, ...]         # relative attachment paths, in email order


@dataclass(frozen=True)
class _Baseline:
    result: CaseResult
    reads: dict[str, _DocRead]


def _txt_pairs(root: Path, limit: Optional[int] = None) -> list[_Pair]:
    """Every email carrying exactly two readable plain-text attachments.

    Two is not a filter of convenience: the comparison stage needs a pair, and
    a one-attachment email is already a `missing_attachment` escalation whose
    outcome no perturbation can change.
    """
    inbox = root / "inbox"
    if not inbox.is_dir():
        raise SystemExit(f"No inbox at {inbox}. Point --data at the bundle.")

    pairs: list[_Pair] = []
    for path in sorted(inbox.glob("email_*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        email = EmailRecord.from_json(record)
        atts = list(email.attachments)
        if len(atts) != 2:
            continue
        if not all(str(a).lower().endswith((".txt", ".text")) for a in atts):
            continue
        if not all(read_attachment(root, a).readable for a in atts):
            continue
        pairs.append(_Pair(email=email, docs=tuple(atts)))
        if limit is not None and len(pairs) >= limit:
            break
    return pairs


def _read_text(path: Path) -> str:
    # Same decode as readers/plain.py, so the harness perturbs the string the
    # reader would have seen and not a prettier one.
    return path.read_bytes().decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# Measuring one perturbation
# --------------------------------------------------------------------------
# Worst first: a defect we invented, or a real one we quietly dropped, beats a
# silent wrong value, which beats an honest escalation. The rank only chooses
# which five examples to show — it never feeds a count.
# A real defect we quietly dropped outranks one we invented *for display only*:
# the summary table is ranked the other way round, because invented defects are
# what cost an operations desk its trust. But masking is rare, and a rare
# failure that never appears in the examples is a failure nobody fixes.
_RANK_MASKED_ANSWER = -1
_RANK_WRONG_ANSWER = 0        # this field's misreading changed the reported defects
_RANK_SILENT_CHANGE = 1
_RANK_LOST_SILENT = 2
_RANK_CHANGED_ESCALATED = 3
_RANK_LOST_ESCALATED = 4

MAX_EXAMPLES = 5


_LINE_LOCATOR = re.compile(r"^line\s+(\d+)$", re.I)


def _line_at(text: str, locator: Optional[str]) -> Optional[str]:
    """The exact source line an `Evidence.locator` points at.

    Located by line number rather than by searching for the value, because the
    notify party and the consignee are frequently the *same company* — a search
    would confidently print the wrong line and send whoever reads this report
    to fix the wrong label.
    """
    if not locator:
        return None
    m = _LINE_LOCATOR.match(str(locator).strip())
    if not m:
        return None
    lines = text.splitlines()
    index = int(m.group(1)) - 1
    return lines[index] if 0 <= index < len(lines) else None


def _shown(line: Optional[str]) -> Optional[str]:
    # rstrip only: leading whitespace IS the perturbation in the indentation
    # modes, and collapsing it would hide the finding.
    return None if line is None else line.rstrip()[:140]


def _after_line(source_line: Optional[str], perturbed: str,
                now: "_FieldRead",
                transform: Callable[[str], str]) -> Optional[str]:
    """The same line of the document, after the perturbation.

    When the field still extracts, its new locator says exactly where it came
    from. When it does not, there is no locator to follow, so the transform is
    re-applied to that one line: every perturbation here rewrites a label block
    independently of its neighbours, so a one-line document goes through it the
    same way the real one did.
    """
    if now.present:
        return _line_at(perturbed, now.locator)
    if source_line is None:
        return None
    return transform(source_line).rstrip("\n")


def _pick_examples(candidates: list[tuple[int, dict]]) -> list[dict]:
    """The five most damaging examples, spread over as many documents as possible.

    Five failures from one document all say the same thing, and five failures
    on one field say only slightly more. Spreading them shows whether a mode is
    a quirk of one template or a systemic blind spot, which is the question
    anyone reading this report actually has. Severity still comes first: a
    varied set of harmless examples would be worse than a repetitive damaging
    one.
    """
    ordered = sorted(candidates, key=lambda item: item[0])
    picked: list[dict] = []
    seen_docs: set[str] = set()
    seen_fields: set[str] = set()

    def take(payload: dict) -> None:
        seen_docs.add(payload["document"])
        seen_fields.add(payload["field"])
        picked.append(payload)

    remaining = [p for _, p in ordered]
    while remaining and len(picked) < MAX_EXAMPLES:
        for relax in (0, 1, 2):
            choice = next(
                (p for p in remaining
                 if (relax >= 2)
                 or (relax >= 1 and p["document"] not in seen_docs)
                 or (p["document"] not in seen_docs and p["field"] not in seen_fields)),
                None,
            )
            if choice is not None:
                remaining.remove(choice)
                take(choice)
                break
    return picked


def _measure(
    name: str,
    transform: Callable[[str], str],
    pairs: Sequence[_Pair],
    baselines: dict[str, _Baseline],
    root: Path,
    tmp_root: Path,
    probe: Pipeline,
) -> PerturbationReport:
    counts = {f: [0, 0, 0] for f in COMPARE_FIELDS}       # unchanged/changed/lost
    documents = 0
    silent = escalated = lost_silent = 0
    decisions_changed = false_disc = masked_disc = esc_gained = 0
    candidates: list[tuple[int, dict]] = []

    for pair in pairs:
        base = baselines[pair.email.email_id]
        base_defects = set(base.result.defect_fields)
        base_key = (base.result.status, tuple(sorted(base_defects)),
                    base.result.review_reason)

        for target in pair.docs:
            # Stage the whole pair: one document perturbed, the other verbatim.
            original = _read_text(root / target)
            perturbed = transform(original)
            for rel in pair.docs:
                dest = tmp_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if rel == target:
                    dest.write_text(perturbed, encoding="utf-8")
                else:
                    dest.write_bytes((root / rel).read_bytes())

            documents += 1
            result = probe.process(pair.email)
            after = _read_doc(tmp_root, target)
            before = base.reads[target]

            case_escalated = result.status == "NEEDS_REVIEW"
            defects = set(result.defect_fields)
            invented = defects - base_defects
            # A real defect that stopped being reported without anyone being
            # told is as bad as an invented one: the BL ships with the error.
            dropped = (base_defects - defects) if not case_escalated else set()
            if invented and result.status == "MISMATCH":
                false_disc += 1
            if base.result.status == "MISMATCH" and dropped:
                masked_disc += 1
            if base.result.status != "NEEDS_REVIEW" and case_escalated:
                esc_gained += 1
            if (result.status, tuple(sorted(defects)), result.review_reason) != base_key:
                decisions_changed += 1

            for fname in COMPARE_FIELDS:
                ref = before.fields[fname]
                if not ref.present:
                    continue                  # no reference read; nothing to test
                now = after.fields[fname]
                source_line = _line_at(original, ref.locator)
                if fname in dropped:
                    wrong_rank = _RANK_MASKED_ANSWER
                elif fname in invented:
                    wrong_rank = _RANK_WRONG_ANSWER
                else:
                    wrong_rank = None
                if not now.present:
                    counts[fname][2] += 1
                    if case_escalated:
                        escalated += 1
                        rank = _RANK_LOST_ESCALATED
                    else:
                        lost_silent += 1
                        rank = (_RANK_LOST_SILENT if wrong_rank is None
                                else wrong_rank)
                    outcome = "lost"
                elif now.key == ref.key:
                    counts[fname][0] += 1
                    continue
                else:
                    counts[fname][1] += 1
                    if case_escalated:
                        escalated += 1
                        rank = _RANK_CHANGED_ESCALATED
                    else:
                        silent += 1
                        rank = (_RANK_SILENT_CHANGE if wrong_rank is None
                                else wrong_rank)
                    outcome = "changed"

                candidates.append((rank, {
                    "email_id": pair.email.email_id,
                    "document": target,
                    "field": fname,
                    "outcome": outcome,
                    "escalated": case_escalated,
                    "label_before": ref.label,
                    "label_after": now.label,
                    "value_before": ref.raw,
                    "value_after": now.raw,
                    "compared_before": _show_key(ref.key),
                    "compared_after": _show_key(now.key),
                    "line_before": _shown(source_line),
                    "line_after": _shown(_after_line(source_line, perturbed,
                                                     now, transform)),
                    "status_before": base.result.status,
                    "status_after": result.status,
                    "defects_before": sorted(base_defects),
                    "defects_after": sorted(defects),
                    "invented_defect": fname in invented,
                    "masked_defect": fname in dropped,
                }))

    return PerturbationReport(
        name=name,
        documents=documents,
        per_field=[FieldOutcome(f, *counts[f]) for f in COMPARE_FIELDS],
        silent_wrong_values=silent,
        escalated=escalated,
        examples=_pick_examples(candidates),
        family=FAMILIES.get(name, "custom"),
        value_altering=name in VALUE_ALTERING,
        lost_not_escalated=lost_silent,
        decisions_changed=decisions_changed,
        false_discrepancies=false_disc,
        masked_discrepancies=masked_disc,
        escalations_gained=esc_gained,
    )


def _show_key(key: Optional[tuple]) -> Optional[str]:
    if key is None:
        return None
    text, number = key
    return text if number is None else f"{number:g}"


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def run(
    data_root: str,
    *,
    limit: Optional[int] = None,
    only: Optional[Iterable[str]] = None,
    llm: Any = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[PerturbationReport]:
    """Measure every perturbation over every readable .txt pair under `data_root`.

    Returns the reports ranked worst-first by `severity()`. With `llm=None` —
    the default — nothing here opens a socket or spends a cent: a measuring
    instrument that depends on a third party is not a measurement.
    """
    root = Path(data_root)
    pairs = _txt_pairs(root, limit)
    names = list(only) if only is not None else list(PERTURBATIONS)
    unknown = [n for n in names if n not in PERTURBATIONS]
    if unknown:
        raise KeyError(f"unknown perturbation(s): {', '.join(unknown)}")

    baseline_pipeline = Pipeline(PipelineConfig(data_root=root, llm=llm))
    baselines: dict[str, _Baseline] = {}
    for pair in pairs:
        baselines[pair.email.email_id] = _Baseline(
            result=baseline_pipeline.process(pair.email),
            reads={rel: _read_doc(root, rel) for rel in pair.docs},
        )

    reports: list[PerturbationReport] = []
    with tempfile.TemporaryDirectory(prefix="sentinel-adversarial-") as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "attachments").mkdir(parents=True, exist_ok=True)
        probe = Pipeline(PipelineConfig(data_root=tmp_root, llm=llm))
        for name in names:
            if on_progress is not None:
                on_progress(name)
            reports.append(_measure(name, PERTURBATIONS[name], pairs,
                                    baselines, root, tmp_root, probe))

    reports.sort(key=lambda r: (tuple(-x for x in severity(r)), r.name))
    return reports


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def _say(text: str = "") -> None:
    print(text)


def _print_reports(reports: Sequence[PerturbationReport], pairs: int) -> None:
    docs = reports[0].documents if reports else 0
    _say("=" * 100)
    _say(f"  ADVERSARIAL SELF-CONSISTENCY  -  {pairs} .txt SI/BL pairs"
         f"  -  {docs} perturbed documents per mode")
    _say("=" * 100)
    _say("  reference = extraction from the unperturbed document; no answer key is used")
    _say("  one half of each pair is perturbed at a time; the other stays verbatim")
    _say()

    header = (f"{'perturbation':<20}{'family':<24}{'ok':>6}{'chg':>6}{'lost':>6}"
              f"{'silent':>8}{'escal':>7}{'falseD':>8}{'maskD':>7}{'decChg':>8}")
    _say(header)
    _say("-" * len(header))
    for r in reports:
        _say(f"{r.name:<20}{r.family:<24}{r.unchanged:>6}{r.changed:>6}{r.lost:>6}"
             f"{r.silent_wrong_values:>8}{r.escalated:>7}"
             f"{r.false_discrepancies:>8}{r.masked_discrepancies:>7}"
             f"{r.decisions_changed:>8}")
    _say("-" * len(header))
    _say("  ok/chg/lost  = per (document, field), over fields the baseline did read")
    _say("  silent       = value changed and the case was still auto-decided  <-- the bad one")
    _say("  escal        = value changed or vanished and a human was asked     <-- the safe one")
    _say("  falseD       = cases where we reported a defect that is not in the document")
    _say("  maskD        = cases where a real defect stopped being reported, unescalated")
    _say()

    _say("PER FIELD (unchanged / changed / lost)")
    _say("-" * 100)
    fields_header = f"{'perturbation':<20}" + "".join(
        f"{f.replace('_', ' ')[:13]:>13}" for f in COMPARE_FIELDS)
    _say(fields_header)
    for r in reports:
        cells = []
        for o in r.per_field:
            cells.append(f"{o.unchanged}/{o.changed}/{o.lost}".rjust(13))
        _say(f"{r.name:<20}" + "".join(cells))
    _say()

    interesting = [r for r in reports if r.changed or r.lost]
    if not interesting:
        _say("No perturbation moved a single field. See the notes in the module "
             "docstring about what that does and does not prove.")
        return

    _say("EXAMPLES (worst first)")
    _say("=" * 100)
    for r in interesting:
        if not r.examples:
            continue
        _say(f"\n### {r.name}  [{r.family}]"
             + ("  (value-altering: numeric changes are partly legitimate)"
                if r.value_altering else ""))
        for ex in r.examples:
            flag = ""
            if ex["invented_defect"]:
                flag = "  *** INVENTED DEFECT ***"
            elif ex["masked_defect"]:
                flag = "  *** REAL DEFECT LOST ***"
            _say(f"  {ex['email_id']}  {ex['document']}  {ex['field']}"
                 f"  [{ex['outcome']}]{flag}")
            _say(f"      doc before : {ex['line_before']!r}")
            _say(f"      doc after  : {ex['line_after']!r}")
            _say(f"      read       : {ex['compared_before']!r}"
                 f"  ->  {ex['compared_after']!r}")
            _say(f"      case       : {ex['status_before']} {ex['defects_before']}"
                 f"  ->  {ex['status_after']} {ex['defects_after']}")


def _payload(reports: Sequence[PerturbationReport], data_root: Path,
             pairs: int, *, pipeline_mode: str = "deterministic") -> dict[str, Any]:
    return {
        "generated_by": "backend/tools/adversarial.py",
        "pipeline_mode": pipeline_mode,
        "method": (
            "Self-consistency: extraction from the unperturbed document is the "
            "reference. One half of each SI/BL pair is perturbed so a human "
            "would read it identically; any field whose compared value moves is "
            "a reading failure. No ground truth is used."
        ),
        "data_root": str(data_root),
        "formats_covered": [".txt"],
        "formats_not_covered": [
            ".pdf", ".docx", ".xlsx",
            "a faithful layout perturbation needs real re-rendered files, not a "
            "rewrite of what our own reader already produced",
        ],
        "pairs": pairs,
        "fields": list(COMPARE_FIELDS),
        "ranking": "false_discrepancies, masked_discrepancies, silent_wrong_values",
        "perturbations": [r.as_dict() for r in reports],
    }


def main() -> int:
    try:                                      # a Chinese label must not crash a report
        sys.stdout.reconfigure(errors="replace")      # type: ignore[union-attr]
    except Exception:                                 # pragma: no cover
        pass

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(REPO_ROOT / "data" / "bundle"),
                    help="folder holding inbox/ and attachments/")
    ap.add_argument("--out", default=str(REPO_ROOT / "runs" / "adversarial.json"),
                    help="where to write the machine-readable report")
    ap.add_argument("--limit", type=int, default=None,
                    help="use only the first N .txt pairs")
    ap.add_argument("--only", default=None,
                    help="comma-separated perturbation names (default: all)")
    ap.add_argument("--llm", action="store_true",
                    help="measure the ASSISTED pipeline: rules plus the model "
                         "fallback. Costs money and needs a key. Off by "
                         "default — see the note at the top of this file.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    data_root = Path(args.data).resolve()
    only = [n.strip() for n in args.only.split(",")] if args.only else None

    # The assisted run measures a different system, so it is opt-in and it
    # says so in the report. A file that does not record which pipeline it
    # measured is a file whose numbers cannot be compared to anything.
    client = build_client(enabled=True) if args.llm else None
    if args.llm and client is None:
        print("--llm was asked for but no usable client is configured "
              "(no OPENAI_API_KEY, or the budget is spent). Refusing to "
              "write a report labelled 'assisted' that measured the rules.",
              file=sys.stderr)
        return 2
    mode = "assisted" if client else "deterministic"

    pairs = len(_txt_pairs(data_root, args.limit))
    progress = None if args.quiet else (lambda n: print(f"  perturbing: {n}"))
    if not args.quiet:
        print(f"Measuring {len(only or PERTURBATIONS)} perturbations over "
              f"{pairs} .txt pairs from {data_root}  [{mode}]")
    reports = run(str(data_root), limit=args.limit, only=only, llm=client,
                  on_progress=progress)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _payload(reports, data_root, pairs, pipeline_mode=mode)
    if client is not None:
        payload["llm"] = client.stats()
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8")

    if not args.quiet:
        _say()
        _print_reports(reports, pairs)
        if client is not None:
            u = client.stats()["usage"]
            _say(f"\nModel: {u['calls']} calls ({u['live_calls']} live), "
                 f"${u['cost_usd']:.4f}")
        _say(f"\nWrote {out_path}")
    return 0


__all__ = [
    "PERTURBATIONS",
    "FAMILIES",
    "UNSEEN_LABELS",
    "VALUE_ALTERING",
    "FieldOutcome",
    "PerturbationReport",
    "run",
    "main",
    "severity",
]


if __name__ == "__main__":
    raise SystemExit(main())
