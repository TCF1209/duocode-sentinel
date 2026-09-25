"""Evidence gate — nothing is reported as a defect unless we can point at it.

The gate runs **after** comparison and **before** the final decision. Its one
job is to answer a question the comparer cannot:

    is this a *discrepancy*, or is it a *reading* problem?

A value that cannot be located in the source document is a value we misread or
invented. Reporting it as a mismatch is a false alarm, and a false alarm is
expensive twice over: it costs precision on the score, and it teaches an
operations desk that the system cries wolf. Routing the same case to a human
costs nothing and tells them exactly where to look — which is the distinction
the problem statement asks for (`docs/ARCHITECTURE.md` §2.3).

So every reported defect must be *grounded*: both sides of it traceable to a
real span of a real document. Everything else becomes a review case with a
reason and a recovery action.

The gate evaluates seven conditions in order and returns on the first that
fires:

    1. no_comparison_needed  the sender wants us to produce a draft BL
    2. missing_attachment    fewer than two documents, and a pair was expected
    3. unreadable            a reader could not get text out of a document
    4. wrong_document        the pair is not {SI, BL}
    5. blank_value           the decision rests on a value the document
                             does not state ("???", "TBA", empty)
    6. untraceable_value     the decision rests on a value we cannot find in
                             the document we claim to have read it from
    7. grounded              the caller may report OK or MISMATCH

Order matters. Conditions 1-4 describe the *case*; they are cheaper and more
specific than anything field-level, and it would be nonsense to report "we
could not trace the consignee" on a document that never arrived. Blank is
checked before traceability because a blank value has nothing to trace: it is
uncertainty, not a misreading, and it carries a different review reason.

What the gate can and cannot prove: it proves that a value we hold is *present*
in the document we claim to have read it from. It cannot prove the value was
read from the right *place* in that document — that is what `Evidence.locator`
is for, and it is why a figure is the weakest thing to trace: a gross weight of
21,577 is unmistakable, but a container count of 6 will also be found in a
street address. Party and port values, which is where the expensive false
alarms live, are distinctive enough for the check to bite.

The module imports nothing outside `schema` and `normalize`: no network, no
model, no reader. `intent` and `pair_problem` are passed in rather than
imported so the gate has no opinion about how they were produced.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Optional, Sequence

from . import normalize
from .schema import (
    COMPARE_FIELDS,
    MATCH,
    MISMATCH,
    UNCOMPARABLE,
    DocFields,
    FieldComparison,
    FieldValue,
    ParsedDoc,
)

GATE_STATUSES: tuple[str, ...] = (
    "grounded",
    "no_comparison_needed",
    "missing_attachment",
    "unreadable",
    "wrong_document",
    "blank_value",
    "ocr_confusable",
    "untraceable_value",
)

# What a reviewer should physically do, per reader failure. The reason strings
# are the reader's own (`readers/__init__.py`), so the advice matches the
# actual failure: a file that did not arrive needs a re-send, a scan needs a
# pair of eyes.
_UNREADABLE_RECOVERY: dict[str, str] = {
    "empty_file": "Ask the sender to re-send {roles} — the file arrived empty.",
    "missing_file": "Ask the sender to re-send {roles} — the attachment is referenced but not present.",
    "corrupt": "Ask the sender to re-send {roles} — the file will not open.",
    "no_text_layer": "Open {roles} by eye: it is an image-only scan, so nothing was machine-readable.",
    "unsupported": "Ask the sender for {roles} in PDF, Word, Excel or plain text.",
}
_UNREADABLE_DEFAULT = "Open {roles} by hand and confirm the seven fields."


@dataclass(frozen=True)
class GateDecision:
    """The gate's verdict on one comparison case.

    `review_reason` is `None` only when the caller is free to report an
    outcome of its own (`grounded`, `no_comparison_needed`); otherwise it is
    one of `schema.REVIEW_REASONS` and the case must end in `NEEDS_REVIEW`.
    """

    status: str
    review_reason: Optional[str]
    reason: str
    blocked_signals: list[str] = dc_field(default_factory=list)
    recovery: str = ""
    untraceable_fields: list[str] = dc_field(default_factory=list)
    evidence_checked: int = 0
    evidence_traced: int = 0

    @property
    def allows_defect(self) -> bool:
        """True when the caller may report OK/MISMATCH from the comparisons."""
        return self.status in ("grounded", "no_comparison_needed")

    def as_dict(self) -> dict[str, Any]:
        """Audit-trail shape for `report.json` and the review queue UI."""
        return {
            "status": self.status,
            "review_reason": self.review_reason,
            "reason": self.reason,
            "blocked_signals": list(self.blocked_signals),
            "recovery": self.recovery,
            "untraceable_fields": list(self.untraceable_fields),
            "evidence_checked": self.evidence_checked,
            "evidence_traced": self.evidence_traced,
        }


# --------------------------------------------------------------------------
# Tracing a value back into its document
# --------------------------------------------------------------------------
# Digits split by a thin space or a tab ("216 950") are one number, but digits
# on two different lines are two numbers. Only intra-line gaps are closed.
_DIGIT_GAP = re.compile(r"(?<=\d)[ \t]+(?=\d)")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WEIGHT_UNIT_AFTER = re.compile(r"^\W{0,3}(MT|MTS|TON|TONS|TONNE|TONNES)\b", re.I)


@dataclass(frozen=True)
class _DocIndex:
    """Three searchable views of one document, built once per document.

    * `squashed`  — upper-cased, whitespace-collapsed, punctuation intact.
      Catches the common case: the value was lifted verbatim from a chunk, so
      it is still there character for character once line wrapping is undone.
    * `tokens`    — `normalize.basic()` tokens. Catches values the reader
      re-joined with different punctuation: the .docx reader writes a table row
      to `text` as "Shipper | ACME | ..." but hands the extractor "ACME ...",
      and the .xlsx reader joins cells with a tab in one and a space in the
      other. Punctuation must not decide whether we believe our own read.
    * `numbers`   — every figure printed in the document, in kg-equivalent
      form as well as face value, because a document quoting "138 MT" backs an
      extracted `gross_weight_kg` of 138000.
    """

    squashed: str
    tokens: tuple[str, ...]
    numbers: frozenset[float]

    @property
    def empty(self) -> bool:
        return not self.squashed


def _squash(s: Optional[str]) -> str:
    """Upper-case and collapse every run of whitespace to one space."""
    if not s:
        return ""
    return " ".join(str(s).upper().split())


def _tokens(s: Optional[str]) -> tuple[str, ...]:
    return tuple(normalize.basic(s).split())


def _numbers_in(text: str) -> frozenset[float]:
    found: set[float] = set()
    joined = _DIGIT_GAP.sub("", text)
    for m in _NUMBER.finditer(joined):
        try:
            n = float(m.group(0).replace(",", ""))
        except ValueError:                      # pragma: no cover - regex-bound
            continue
        found.add(n)
        # "138 MT" in the document is the same fact as 138000 kg in our field.
        if _WEIGHT_UNIT_AFTER.match(joined[m.end():m.end() + 8]):
            found.add(n * 1000.0)
    return frozenset(found)


def _index(doc: Optional[ParsedDoc]) -> _DocIndex:
    text = (doc.text if doc is not None else "") or ""
    return _DocIndex(
        squashed=_squash(text),
        tokens=_tokens(text),
        numbers=_numbers_in(text),
    )


def _contains_span(haystack: str, needle: str) -> bool:
    """Is `needle` in `haystack`, bounded by something other than a letter/digit?

    A plain `in` test would trace a container count of "6" against the "6" in
    "656, GANGNAM-DAERO" — i.e. an invented short value would look confirmed.
    The boundary is only demanded on a side where the needle itself ends in an
    alphanumeric, so a value that legitimately starts with punctuation
    ("#21-01", "(MYPKG)") is still findable.
    """
    if not needle:
        return False
    left_bounded = needle[0].isalnum()
    right_bounded = needle[-1].isalnum()
    start = 0
    while True:
        i = haystack.find(needle, start)
        if i < 0:
            return False
        j = i + len(needle)
        ok_left = not left_bounded or i == 0 or not haystack[i - 1].isalnum()
        ok_right = not right_bounded or j >= len(haystack) or not haystack[j].isalnum()
        if ok_left and ok_right:
            return True
        start = i + 1


def _contains_sequence(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    """Is `needle` a contiguous run of tokens inside `haystack`?

    Token-sequence containment rather than substring containment on purpose:
    on the joined token string, "40" would match inside "4012" and a two-digit
    container size would "trace" against a booking reference.
    """
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    first = needle[0]
    for i in range(len(haystack) - n + 1):
        if haystack[i] == first and tuple(haystack[i:i + n]) == tuple(needle):
            return True
    return False


def _number_close(a: float, b: float) -> bool:
    # Weights are quoted to the kilogram and counts are integers, so anything
    # below half a unit is float noise from the xlsx reader, not a difference.
    return abs(a - b) < 0.5


def _trace(index: _DocIndex, value: Optional[FieldValue]) -> bool:
    if value is None or index.empty:
        return False
    raw = value.raw
    if raw is None:
        return False
    raw = str(raw)
    if normalize.is_blank(raw):
        # Nothing to locate. Blank values never reach here — condition 5
        # already routed them — and they are uncertainty, not a misreading.
        return False

    # 1. verbatim, modulo line wrapping and case. Every one of the 1,645 values
    #    the rule extractor finds in this dataset traces on this path alone —
    #    which is the point: a rule-extracted value is a slice of a chunk of
    #    the document, so it is still there character for character.
    if _contains_span(index.squashed, _squash(raw)):
        return True

    # 2. canonical tokens, so punctuation and separators cannot fail a value
    #    that is plainly there: the .docx reader writes a table row into `text`
    #    as "Shipper | ACME LTD" while handing the extractor "ACME LTD", and
    #    the .xlsx reader separates cells with a tab in one and a space in the
    #    other.
    if _contains_sequence(index.tokens, _tokens(raw)):
        return True

    # 3. the canonical form the comparison will actually use.
    #
    #    Deliberately NOT a fourth path on `first_segment()`: accepting the
    #    entity name alone would accept a value that is a strict prefix of what
    #    the document says, and "APRIL FINE PAPER TRADING" is a prefix of
    #    "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE" — a different shipper
    #    (DATA_NOTES §4). Blessing a truncated read is exactly how a false
    #    discrepancy would slip past this gate. It earns nothing on the real
    #    data either: no value needs it.
    canonical, number = normalize.normalise_field(value.field or "", raw)
    if number is not None:
        # A figure is traced by its magnitude: the document prints "21,577 KG"
        # and we hold 21577.0. Text matching cannot bridge the separator.
        return any(_number_close(number, n) for n in index.numbers)
    if canonical and _contains_sequence(index.tokens, tuple(canonical.split())):
        return True
    return False


def trace_value(doc: ParsedDoc, value: FieldValue) -> bool:
    """Can `value.raw` be located in `doc`'s own text?

    False means one of two things, and both are reasons to stop: either we
    extracted something the document does not say, or we are holding the value
    against the wrong document. Either way the case belongs to a human.
    """
    return _trace(_index(doc), value)


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------
def _flag(intent: Any, name: str) -> bool:
    """Read one intent flag defensively.

    `intent` is `classify.intent.Intent`, but the gate must also behave when a
    caller has no intent to give it (an API request with a bare pair of files,
    a unit test). A missing flag reads as False, never as an exception.
    """
    return bool(getattr(intent, name, False))


def _role_label(role: str) -> str:
    return "the SI" if role == "SI" else "the draft BL"


def _unreadable_recovery(reasons: list[tuple[str, str]]) -> str:
    roles = " and ".join(_role_label(r) for r, _ in reasons)
    template = _UNREADABLE_RECOVERY.get(reasons[0][1], _UNREADABLE_DEFAULT)
    return template.format(roles=roles)


def _side_unusable(v: Optional[FieldValue]) -> bool:
    """True when this side carries no usable value, whatever the verdict says.

    A blank is not a discrepancy (CLAUDE.md rule 4). If a comparer ever calls
    `???` a MISMATCH — because a placeholder is, literally, different text —
    the gate turns it back into a review case rather than let a false alarm
    through.
    """
    if v is None:
        return True
    if not v.present or v.blank:
        return True
    return v.raw is None or normalize.is_blank(str(v.raw))


def _blank_signals_from_fields(
    names: Iterable[str],
    si_fields: Optional[DocFields],
    bl_fields: Optional[DocFields],
) -> list[str]:
    """Which side is missing which field, read straight from the extraction.

    Used where there is no comparison to read it off — a reviewer still needs
    to be told *which* field to chase and in *which* document.
    """
    signals: list[str] = []
    for name in names:
        for role, side in (("SI", si_fields), ("BL", bl_fields)):
            if side is None:
                continue
            if _side_unusable(side.get(name)):
                signals.append(f"blank:{role}:{name}")
    return signals


def _side_absent(v: Optional[FieldValue]) -> bool:
    """No chunk resolved to this field at all — narrower than "unusable".

    `extract/fields.py` leaves `raw` as None when no label in the document
    resolved to the field; a blank carries its placeholder text instead. The
    same distinction `extract/llm.py` draws when deciding what to ask about.
    """
    return v is None or (v.raw is None and not v.present)


def _absent_sides(fields: Iterable[str], comparisons: Sequence[FieldComparison]) -> dict[str, list[str]]:
    """Which of `fields` no label resolved to, and in which document(s)."""
    wanted = set(fields)
    out: dict[str, list[str]] = {}
    for c in comparisons:
        if c.field not in wanted:
            continue
        sides = [role for role, v in (("SI", c.si), ("BL", c.bl)) if _side_absent(v)]
        if sides:
            out[c.field] = sides
    return out


def _no_label_sentence(absent: dict[str, list[str]]) -> str:
    """"No label for shipper in the SI; consignee in either document could be
    recognised ..." — grouped by where the label was not found, so the
    operator knows which page to open."""
    by_where: dict[str, list[str]] = {}
    for name in _sorted_fields(absent):
        sides = absent[name]
        where = "either document" if len(sides) == 2 else _role_label(sides[0])
        by_where.setdefault(where, []).append(name.replace("_", " "))
    clauses = [f"{', '.join(names)} in {where}" for where, names in by_where.items()]
    return (
        "No label for " + "; ".join(clauses) + " could be recognised — new wording, "
        "so the value was left unread, not guessed."
    )


def _decided_fields(comparisons: Sequence[FieldComparison]) -> list[FieldComparison]:
    """The comparisons a reported outcome would actually rest on."""
    return [c for c in comparisons if c.verdict in (MATCH, MISMATCH)]


def _sorted_fields(names: Iterable[str]) -> list[str]:
    """Field names in the canonical order, so reports read the same every time."""
    unique = set(names)
    ordered = [f for f in COMPARE_FIELDS if f in unique]
    ordered += sorted(n for n in unique if n not in COMPARE_FIELDS)
    return ordered


def evaluate(
    *,
    si_doc: Optional[ParsedDoc],
    bl_doc: Optional[ParsedDoc],
    si_fields: Optional[DocFields],
    bl_fields: Optional[DocFields],
    comparisons: Sequence[FieldComparison],
    intent: Any,
    pair_problem: Optional[str],
) -> GateDecision:
    """Decide whether a comparison outcome may be reported as fact.

    Never raises: a crash inside the gate must not take down a batch run, and
    a case the gate could not verify is a case for a human.
    """
    try:
        return _evaluate(
            si_doc=si_doc,
            bl_doc=bl_doc,
            si_fields=si_fields,
            bl_fields=bl_fields,
            comparisons=list(comparisons or []),
            intent=intent,
            pair_problem=pair_problem,
        )
    except Exception as exc:
        # A malformed comparison list or a half-built FieldValue is a bug, but
        # it must cost one case, not the batch — and the case goes to a human.
        return GateDecision(
            status="unreadable",
            review_reason="unreadable",
            reason="The evidence gate could not verify this case, so it was not auto-decided.",
            blocked_signals=[f"gate_error:{type(exc).__name__}"],
            recovery="Check the SI and the draft BL by hand.",
        )


def _evaluate(
    *,
    si_doc: Optional[ParsedDoc],
    bl_doc: Optional[ParsedDoc],
    si_fields: Optional[DocFields],
    bl_fields: Optional[DocFields],
    comparisons: list[FieldComparison],
    intent: Any,
    pair_problem: Optional[str],
) -> GateDecision:
    present = [(role, doc) for role, doc in (("SI", si_doc), ("BL", bl_doc)) if doc is not None]
    n_docs = len(present)
    requests_draft = _flag(intent, "requests_draft")
    expects_documents = _flag(intent, "expects_attached_documents")

    # ---- 1. nothing to compare, and nothing wrong -------------------------
    # "Please assist to send the draft BL ... for checking" with no
    # attachments is a normal request to *produce* a document, not a failed
    # comparison. The counting of attachments cannot tell this apart from the
    # dropped-attachment case below — only the intent can (DATA_NOTES §5a).
    if n_docs == 0 and requests_draft and not expects_documents:
        return GateDecision(
            status="no_comparison_needed",
            review_reason=None,
            reason="The sender is asking us to produce the draft BL, so there is no pair to compare yet.",
            blocked_signals=["attachments:0", "intent:requests_draft"],
            recovery="Issue the draft BL and send it back for checking.",
        )

    # ---- 2. we cannot compare half a pair ---------------------------------
    if n_docs < 2:
        if n_docs == 1:
            have_role = present[0][0]
            missing_role = "BL" if have_role == "SI" else "SI"
            return GateDecision(
                status="missing_attachment",
                review_reason="missing_attachment",
                reason=(
                    f"Only {_role_label(have_role)} is attached; "
                    f"{_role_label(missing_role)} is missing, so there is nothing to compare it against."
                ),
                blocked_signals=["attachments:1", f"missing_document:{missing_role}"],
                recovery=f"Ask the sender for {_role_label(missing_role)}.",
            )
        if expects_documents:
            return GateDecision(
                status="missing_attachment",
                review_reason="missing_attachment",
                reason="The sender expects us to check attached documents, but the email carries none.",
                blocked_signals=["attachments:0", "intent:expects_attached_documents"],
                recovery="Ask the sender to re-send both the SI and the draft BL.",
            )
        # Zero attachments and the intent check found no signal either way.
        # Deliberate default: with no documents there is no defect to report,
        # so the gate does not manufacture an escalation — it records that the
        # intent was unclear and lets the caller report a plain outcome.
        return GateDecision(
            status="no_comparison_needed",
            review_reason=None,
            reason="There are no attachments and no sign that the sender believes they attached any, so there is nothing to compare.",
            blocked_signals=["attachments:0", "intent:unclear"],
            recovery="No action unless the sender expected to attach documents.",
        )

    # ---- 3. we could not read what we were sent ---------------------------
    # Carry the reader's own diagnosis through: "re-send this" and "open the
    # scan yourself" are different instructions to an operator.
    bad = [(role, doc.unreadable_reason or "unknown") for role, doc in present if not doc.readable]
    if bad:
        detail = ", ".join(f"{_role_label(role)} ({reason})" for role, reason in bad)
        return GateDecision(
            status="unreadable",
            review_reason="unreadable",
            reason=f"We could not read {detail}, so no field can be checked against it.",
            blocked_signals=[f"{role.lower()}:{reason}" for role, reason in bad],
            recovery=_unreadable_recovery(bad),
        )

    # ---- 4. the right number of documents, the wrong documents ------------
    # Any pair problem lands here: `REVIEW_REASONS` has exactly one reason for
    # "this is not an {SI, BL} pair", and the raw problem string is kept in the
    # signals so the reviewer sees what the classifier actually said.
    if pair_problem:
        problem = str(pair_problem).strip()
        si_type = si_doc.doc_type if si_doc else "UNKNOWN"
        bl_type = bl_doc.doc_type if bl_doc else "UNKNOWN"
        return GateDecision(
            status="wrong_document",
            review_reason="wrong_doc_type",
            reason=(
                "The two attachments are not a Shipping Instruction and a draft Bill of Lading "
                f"(read as {si_type} and {bl_type}), so comparing them would be meaningless."
            ),
            blocked_signals=[f"pair_problem:{problem}", f"si_doc_type:{si_type}", f"bl_doc_type:{bl_type}"],
            recovery="Ask the sender for the draft BL; the attached document is something else.",
        )

    # ---- 5. the document does not state the value -------------------------
    # A blank is uncertainty, not a discrepancy (CLAUDE.md rule 4): reporting
    # MISMATCH on a "???" field is a false alarm and costs precision.
    if not comparisons:
        return GateDecision(
            status="blank_value",
            review_reason="missing_value",
            reason="Neither document yielded values we could compare, so there is nothing to decide on.",
            blocked_signals=["comparisons:none"] + _blank_signals_from_fields(
                COMPARE_FIELDS, si_fields, bl_fields),
            recovery="Open both documents and check the seven fields by hand.",
        )

    blank_fields: list[str] = []
    blank_signals: list[str] = []
    ocr_fields: list[str] = []
    for c in comparisons:
        si_bad = _side_unusable(c.si)
        bl_bad = _side_unusable(c.bl)
        if c.verdict != UNCOMPARABLE and not si_bad and not bl_bad:
            continue
        if c.reason == "ocr_confusable" and not si_bad and not bl_bad:
            # Both documents state this field and both readings are legible.
            # It belongs to the branch below, which says so; folding it in
            # here would tell the operator the value is missing while they
            # are looking straight at it.
            ocr_fields.append(c.field)
            continue
        blank_fields.append(c.field)
        for role, bad_side in (("SI", si_bad), ("BL", bl_bad)):
            if bad_side:
                blank_signals.append(f"blank:{role}:{c.field}")
        if not si_bad and not bl_bad:
            blank_signals.append(f"uncomparable:{c.field}:{c.reason or 'no reason given'}")

    # A field nobody produced a verdict for is a field the decision cannot rest
    # on either. This is a no-op while the comparer emits all seven (it does),
    # and a guard if it ever silently stops covering one.
    uncovered = [f for f in COMPARE_FIELDS if f not in {c.field for c in comparisons}]
    uncovered_signals = _blank_signals_from_fields(uncovered, si_fields, bl_fields)
    if uncovered_signals:
        blank_fields.extend(uncovered)
        blank_signals.extend(uncovered_signals)

    if blank_fields:
        fields = _sorted_fields(blank_fields)
        # Two different things end here and the operator needs to know which.
        # A *blank* is a field the document prints and leaves empty ("???",
        # "TBA"): the sender has to supply it. An *absent* field is one no
        # label resolved to at all -- the document may well state it, under a
        # wording the label table has never seen -- and telling the operator
        # "the documents do not state the consignee" while they are looking
        # straight at a consignee line would cost the trust every other
        # escalation depends on. Same status, same review reason; different
        # sentence, different recovery.
        absent = _absent_sides(fields, comparisons)
        blank_only = [f for f in fields if f not in absent]
        sentences: list[str] = []
        recoveries: list[str] = []
        if blank_only:
            sentences.append(
                "The documents do not state "
                + ", ".join(f.replace("_", " ") for f in blank_only)
                + " — a blank value is uncertainty, not a discrepancy."
            )
            recoveries.append("Ask the sender to confirm the missing field(s).")
        if absent:
            sentences.append(_no_label_sentence(absent))
            recoveries.append(
                "Read the field(s) off the document; if the wording is new, add it to the label table."
            )
        return GateDecision(
            status="blank_value",
            review_reason="missing_value",
            reason=" ".join(sentences),
            blocked_signals=blank_signals,
            recovery=" ".join(recoveries),
        )

    # ---- 5b. the two readings differ only where OCR confuses glyphs -------
    # `NANT0NG` against `NANTONG` is one port and a bad scan, not two ports.
    # `compare.py` refuses to call that a discrepancy; the gate refuses to let
    # the case be auto-decided either way, because the other possibility is
    # that the character really is different and we cannot tell from the text
    # layer alone. Both readings go to the operator, who can see the page.
    if ocr_fields:
        fields = _sorted_fields(ocr_fields)
        return GateDecision(
            status="ocr_confusable",
            review_reason="unreadable",
            reason=(
                "The two documents differ on "
                + ", ".join(f.replace("_", " ") for f in fields)
                + " only in characters OCR routinely confuses (O/0, I/1, S/5,"
                " B/8) — this reads as a scanning error rather than a"
                " discrepancy, but the text alone cannot settle which."
            ),
            blocked_signals=[f"ocr_confusable:{f}" for f in fields],
            recovery="Compare both values against the pages; if they are the same party or port, this field is clean.",
        )

    # ---- 6. can we actually find what we claim to have read? --------------
    # The core check. A rule-extracted value is a slice of a chunk of the
    # document, so it should trace essentially always; a trace failure means we
    # are holding a value the document does not contain, and reporting that as
    # a discrepancy would be inventing one.
    si_index, bl_index = _index(si_doc), _index(bl_doc)
    checked = traced = 0
    untraceable: list[str] = []
    signals: list[str] = []

    for c in _decided_fields(comparisons):
        for role, index, value in (("SI", si_index, c.si), ("BL", bl_index, c.bl)):
            checked += 1
            if _trace(index, value):
                traced += 1
            else:
                untraceable.append(c.field)
                snippet = _squash(value.raw)[:60] if value is not None else ""
                signals.append(f"untraceable:{role}:{c.field}:{snippet}")

    if untraceable:
        fields = _sorted_fields(untraceable)
        return GateDecision(
            status="untraceable_value",
            review_reason="unreadable",
            reason=(
                "We could not find our own reading of "
                + ", ".join(f.replace("_", " ") for f in fields)
                + " in the source document, so the extraction cannot be trusted."
            ),
            blocked_signals=signals,
            recovery="Confirm the flagged field(s) against the documents before replying.",
            untraceable_fields=fields,
            evidence_checked=checked,
            evidence_traced=traced,
        )

    # ---- 7. grounded ------------------------------------------------------
    return GateDecision(
        status="grounded",
        review_reason=None,
        reason=f"Every compared value ({traced}/{checked}) was located in its source document.",
        blocked_signals=[],
        recovery="",
        evidence_checked=checked,
        evidence_traced=traced,
    )


__all__ = ["GATE_STATUSES", "GateDecision", "trace_value", "evaluate"]
