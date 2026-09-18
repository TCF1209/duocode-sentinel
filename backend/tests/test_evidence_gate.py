"""Tests for the evidence gate, against the real documents in data/bundle.

The gate's promise is that no defect is reported unless both sides of it can be
pointed at in a real document, so these tests are mostly about the two ways
that promise can break:

  * it fires on a value that is legitimately there, only formatted differently
    in `doc.text` — every readable pair in the bundle is checked for this, in
    all four attachment formats;
  * it waves through a value the document does not contain — checked with a
    fabricated reading and with substring near-misses.

Plus the four escalation reasons from `DATA_NOTES.md` §5 and the zero-
attachment intent trap from §5a, each on the real email that exhibits it.

`extract/fields.py` and `compare.py` land separately, so the two helpers below
stand in for them. They build the same `FieldValue` / `FieldComparison` objects
from real chunks of real documents, which is all the gate consumes — it never
sees an email or a reader.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import DATA
from sdoc import evidence_gate as gate
from sdoc import labels, normalize, readers
from sdoc.schema import (
    COMPARE_FIELDS,
    MATCH,
    MISMATCH,
    REVIEW_REASONS,
    UNCOMPARABLE,
    DocFields,
    Evidence,
    FieldComparison,
    FieldValue,
    ParsedDoc,
)

pytestmark = pytest.mark.skipif(
    not (DATA / "inbox").is_dir(), reason="data/bundle is not present (it is git-ignored)"
)


# --------------------------------------------------------------------------
# Stand-ins for the modules that land separately
# --------------------------------------------------------------------------
def build_fields(doc: ParsedDoc, role: str) -> DocFields:
    """chunks -> the 7 FieldValues, with evidence (stands in for extract/fields.py)."""
    out: dict[str, FieldValue] = {}
    for chunk in doc.chunks:
        name = labels.resolve(chunk.label)
        if not name:
            continue
        raw = chunk.value or ""
        blank = normalize.is_blank(raw)
        canonical, number = normalize.normalise_field(name, raw)
        value = FieldValue(
            field=name,
            raw=raw or None,
            normalised=canonical,
            number=number,
            present=bool(raw) and not blank and canonical is not None,
            blank=blank,
            evidence=Evidence(doc_role=role, locator=chunk.locator,
                              label=chunk.label, snippet=raw[:120]),
        )
        current = out.get(name)
        if current is None or (not current.present and value.present):
            out[name] = value
    return DocFields(doc=doc, fields=out)


def build_comparisons(si: DocFields, bl: DocFields) -> list[FieldComparison]:
    """Exact equality after normalisation (stands in for compare.py)."""
    result: list[FieldComparison] = []
    for name in COMPARE_FIELDS:
        a, b = si.get(name), bl.get(name)
        if not a.present or not b.present:
            result.append(FieldComparison(field=name, verdict=UNCOMPARABLE, si=a, bl=b,
                                          reason="value blank or not found"))
            continue
        if a.number is not None and b.number is not None:
            same = abs(a.number - b.number) < 0.5
        elif name in ("port_of_loading", "port_of_discharge"):
            same = normalize.ports_equal(a.raw, b.raw)
        else:
            same = a.normalised == b.normalised
        result.append(FieldComparison(field=name, verdict=MATCH if same else MISMATCH,
                                      si=a, bl=b))
    return result


@dataclass(frozen=True)
class StubIntent:
    """What `classify/intent.py` will hand the gate: two flags, no text.

    The gate acts on the flags, so the stub is enough to test it. The phrases
    below are the real dataset's wording (`DATA_NOTES.md` §5a); when the real
    intent classifier lands, `intent_for()` picks it up automatically and these
    two cases become an integration check of the trap.
    """

    requests_draft: bool = False
    expects_attached_documents: bool = False

    @classmethod
    def from_body(cls, body: str) -> "StubIntent":
        low = body.lower()
        asks_us_to_produce = "send the draft bl" in low or "send us the draft" in low
        believes_attached = (
            "attached" in low
            or "attachments appear" in low
            or "please compare" in low
            or "still missing" in low
        )
        return cls(requests_draft=asks_us_to_produce,
                   expects_attached_documents=believes_attached and not asks_us_to_produce)


def intent_for(email: dict) -> object:
    """The real intent classifier if it exists yet, otherwise the stub."""
    try:
        from sdoc.classify import intent as intent_module
    except Exception:
        intent_module = None
    for name in ("classify_intent", "classify", "detect", "detect_intent", "read_intent"):
        fn = getattr(intent_module, name, None) if intent_module else None
        if not callable(fn):
            continue
        for args in ((email,), (email.get("subject", ""), email.get("body", "")),
                     (email.get("body", ""),)):
            try:
                got = fn(*args)
            except Exception:
                continue
            if hasattr(got, "requests_draft") and hasattr(got, "expects_attached_documents"):
                return got
    return StubIntent.from_body(email.get("body", ""))


# --------------------------------------------------------------------------
# Fixtures over the real bundle
# --------------------------------------------------------------------------
def load_email(email_id: str) -> dict:
    return json.loads((DATA / "inbox" / f"{email_id}.json").read_text(encoding="utf-8"))


def read_pair(email: dict) -> tuple[ParsedDoc | None, ParsedDoc | None]:
    """Split an email's attachments into (SI, BL) the way intake will."""
    docs = [readers.read_attachment(DATA, p) for p in email.get("attachments") or []]
    si = next((d for d in docs if d.role_hint == "SI"), None)
    bl = next((d for d in docs if d.role_hint == "BL"), None)
    leftovers = [d for d in docs if d is not si and d is not bl]
    if si is None and leftovers:
        si = leftovers.pop(0)
    if bl is None and leftovers:
        bl = leftovers.pop(0)
    return si, bl


def run_gate(email_id: str, *, pair_problem: str | None = None,
             mutate=None) -> gate.GateDecision:
    """Read an email's attachments and put the whole case through the gate."""
    email = load_email(email_id)
    si_doc, bl_doc = read_pair(email)
    si_fields = build_fields(si_doc, "SI") if si_doc and si_doc.readable else None
    bl_fields = build_fields(bl_doc, "BL") if bl_doc and bl_doc.readable else None
    comparisons: list[FieldComparison] = []
    if si_fields and bl_fields:
        comparisons = build_comparisons(si_fields, bl_fields)
    if mutate is not None:
        comparisons = mutate(comparisons)
    decision = gate.evaluate(
        si_doc=si_doc, bl_doc=bl_doc,
        si_fields=si_fields, bl_fields=bl_fields,
        comparisons=comparisons, intent=intent_for(email), pair_problem=pair_problem,
    )
    assert_contract(decision)
    return decision


def assert_contract(decision: gate.GateDecision) -> None:
    """Every decision must be usable by the pipeline and readable by a person."""
    assert decision.status in gate.GATE_STATUSES
    assert decision.review_reason is None or decision.review_reason in REVIEW_REASONS
    assert decision.reason.strip(), "a decision must carry an operator-facing sentence"
    assert decision.evidence_traced <= decision.evidence_checked
    if decision.review_reason is not None:
        assert decision.recovery.strip(), "an escalation must tell a human what to do"
    if decision.status == "grounded":
        assert decision.review_reason is None
        assert decision.untraceable_fields == []


def comparable_pairs() -> list[str]:
    """Every email in the bundle that carries two readable attachments."""
    out = []
    for path in sorted((DATA / "inbox").glob("*.json")):
        email = json.loads(path.read_text(encoding="utf-8"))
        if len(email.get("attachments") or []) != 2:
            continue
        si, bl = read_pair(email)
        if si and bl and si.readable and bl.readable:
            out.append(email["email_id"])
    return out


# --------------------------------------------------------------------------
# 1. A clean pair is grounded — in every attachment format
# --------------------------------------------------------------------------
def test_clean_txt_pair_is_grounded():
    decision = run_gate("email_001")
    assert decision.status == "grounded"
    assert decision.review_reason is None
    # 7 fields x 2 documents: the decision rests on all of them.
    assert decision.evidence_checked == 2 * len(COMPARE_FIELDS)
    assert decision.evidence_traced == decision.evidence_checked
    assert decision.untraceable_fields == []
    assert decision.blocked_signals == []


@pytest.mark.parametrize("email_id, formats", [
    ("email_059", "pdf + pdf"),
    ("email_005", "xlsx + xlsx"),
    ("email_055", "xlsx + docx"),
    ("email_313", "pdf + pdf, two-column form"),
])
def test_clean_pairs_are_grounded_in_every_format(email_id, formats):
    """The traceability check must survive each reader's idea of `doc.text`.

    The .docx reader writes table rows as "label | value" and the .xlsx reader
    separates cells with a tab, while both hand the extractor a space-joined
    value; the PDF reader rebuilds rows from word coordinates. A gate that only
    understood plain text would veto perfectly good pairs here.
    """
    decision = run_gate(email_id)
    assert decision.status == "grounded", f"{formats}: {decision.reason}"
    assert decision.evidence_traced == decision.evidence_checked > 0


def test_no_readable_pair_in_the_bundle_is_called_untraceable():
    """The honest direction: the gate must not fire on real, correct readings.

    Every rule-extracted value in this dataset is a slice of a chunk of its own
    document, so all of them should trace. If this ever fails, either the
    extractor invented something or the gate got too strict.
    """
    untraceable = {}
    grounded = 0
    for email_id in comparable_pairs():
        decision = run_gate(email_id)
        if decision.status == "untraceable_value":
            untraceable[email_id] = decision.blocked_signals
        if decision.status == "grounded":
            grounded += 1
    assert untraceable == {}
    # DATA_NOTES §1: roughly 109 genuine SI+BL pairs are comparable.
    assert grounded >= 100


# --------------------------------------------------------------------------
# 2. Unreadable documents
# --------------------------------------------------------------------------
def test_image_only_scan_is_unreadable_with_the_readers_own_reason():
    """email_512 carries two image-only scanned PDFs (DATA_NOTES §5)."""
    decision = run_gate("email_512")
    assert decision.status == "unreadable"
    assert decision.review_reason == "unreadable"
    assert "si:no_text_layer" in decision.blocked_signals
    assert "bl:no_text_layer" in decision.blocked_signals
    # The operator must be told to look at the scan, not to ask for a re-send.
    assert "scan" in decision.recovery.lower()


def test_truncated_pdf_is_unreadable_and_asks_for_a_re_send():
    """email_515's BL is a truncated PDF that will not open."""
    decision = run_gate("email_515")
    assert decision.status == "unreadable"
    assert decision.review_reason == "unreadable"
    assert "bl:corrupt" in decision.blocked_signals
    assert "re-send" in decision.recovery.lower()


def test_unreadable_is_checked_before_field_level_reasons():
    """A document we could not open cannot also be 'missing a value'."""
    decision = run_gate("email_513", pair_problem=None)
    assert decision.status == "unreadable"


# --------------------------------------------------------------------------
# 3. The wrong document
# --------------------------------------------------------------------------
def test_commercial_invoice_instead_of_a_bl_is_wrong_document():
    """email_501's second attachment is a Commercial Invoice (DATA_NOTES §5)."""
    _, bl_doc = read_pair(load_email("email_501"))
    assert "COMMERCIAL INVOICE" in bl_doc.text.upper()      # the real file, not a fixture

    decision = run_gate("email_501", pair_problem="wrong_doc_type")
    assert decision.status == "wrong_document"
    assert decision.review_reason == "wrong_doc_type"
    assert any(s.startswith("pair_problem:") for s in decision.blocked_signals)


def test_wrong_document_outranks_the_missing_values_it_causes():
    """Ordering matters: an invoice has none of our seven fields.

    Without the doctype check it would look like a blank-value case, and the
    operator would be told to chase missing fields instead of the right
    document.
    """
    assert run_gate("email_501", pair_problem=None).status == "blank_value"
    assert run_gate("email_501", pair_problem="wrong_doc_type").status == "wrong_document"


# --------------------------------------------------------------------------
# 4. A blank value is an escalation, never a discrepancy
# --------------------------------------------------------------------------
def test_blank_si_fields_are_missing_value_not_mismatch():
    """email_518's SI leaves fields as '???' / '____MT' / 'N/A'.

    Its BL states them (POD "APAPA, NIGERIA", gross weight "134,586 KG"), so a
    text comparer would happily call this a discrepancy. It is not one: we do
    not know what the SI says. CLAUDE.md rule 4.
    """
    si_doc, _ = read_pair(load_email("email_518"))
    assert "???" in si_doc.text                              # the documented trap
    si_fields = build_fields(si_doc, "SI")
    assert normalize.is_blank(si_fields.get("port_of_discharge").raw)
    assert normalize.is_blank(si_fields.get("gross_weight_kg").raw)

    decision = run_gate("email_518")
    assert decision.status == "blank_value"
    assert decision.review_reason == "missing_value"
    assert "port of discharge" in decision.reason
    assert "blank:SI:port_of_discharge" in decision.blocked_signals


def test_a_comparer_that_calls_a_blank_a_mismatch_is_vetoed():
    """The gate is the last line of defence for CLAUDE.md rule 4.

    If any future comparer (or the LLM fallback) decides that "N/A" differs
    from "APAPA, NIGERIA" — which, as text, it does — the gate must still turn
    that into a review case rather than a reported defect.
    """
    def call_every_blank_a_mismatch(comparisons):
        return [
            FieldComparison(field=c.field, verdict=MISMATCH, si=c.si, bl=c.bl)
            if c.verdict == UNCOMPARABLE else c
            for c in comparisons
        ]

    decision = run_gate("email_518", mutate=call_every_blank_a_mismatch)
    assert decision.status == "blank_value"
    assert decision.review_reason == "missing_value"


@pytest.mark.parametrize("email_id", ["email_516", "email_517", "email_519", "email_520"])
def test_every_blank_field_sample_escalates(email_id):
    decision = run_gate(email_id)
    assert decision.status == "blank_value"
    assert decision.review_reason == "missing_value"


# --------------------------------------------------------------------------
# 5. The core check — a value that is not in the document
# --------------------------------------------------------------------------
def test_trace_value_finds_every_real_reading():
    """Both documents of a real pair, all seven fields, in both directions."""
    si_doc, bl_doc = read_pair(load_email("email_001"))
    for doc, role in ((si_doc, "SI"), (bl_doc, "BL")):
        fields = build_fields(doc, role)
        for name in COMPARE_FIELDS:
            value = fields.get(name)
            assert value.present, f"{role} {name} should have been extracted"
            assert gate.trace_value(doc, value), f"{role} {name}={value.raw!r} did not trace"


def test_trace_value_rejects_a_value_the_document_never_states():
    si_doc, _ = read_pair(load_email("email_001"))
    invented = FieldValue(field="consignee", raw="ZEPHYR OCEANIC HOLDINGS (PTY) LTD",
                          normalised="ZEPHYR OCEANIC", present=True)
    assert gate.trace_value(si_doc, invented) is False


def test_trace_value_rejects_a_value_read_from_the_other_document():
    """A value held against the wrong document is a reading error too."""
    si_doc, bl_doc = read_pair(load_email("email_518"))
    bl_pod = build_fields(bl_doc, "BL").get("port_of_discharge")
    assert gate.trace_value(bl_doc, bl_pod) is True
    assert gate.trace_value(si_doc, bl_pod) is False          # SI says "N/A"


def test_trace_value_does_not_match_inside_a_longer_token():
    """"6" must not trace against the 6 inside "656", and a fragment of a
    company name must not trace against the whole name."""
    doc = ParsedDoc(path="x.txt", ext=".txt",
                    text="CONSIGNEE: TOPKOPY MIDDLE EAST FZE\n"
                         "  656, GANGNAM-DAERO; SEOUL\n"
                         "No. of Containers: 12 x 40'HC\n")
    assert gate.trace_value(doc, FieldValue(field="container_count", raw="6",
                                            present=True)) is False
    assert gate.trace_value(doc, FieldValue(field="consignee", raw="OPKOPY MIDDLE",
                                            present=True)) is False
    assert gate.trace_value(doc, FieldValue(field="container_count", raw="12 x 40'HC",
                                            present=True)) is True


def test_a_fabricated_reading_blocks_the_defect_it_would_have_caused():
    """The scenario the gate exists for: a misread that looks like a defect.

    We give the BL a consignee it does not contain. Compared against the SI it
    is a clean MISMATCH, and without the gate the system would report a
    discrepancy that is really a reading error.
    """
    def fabricate_bl_consignee(comparisons):
        out = []
        for c in comparisons:
            if c.field != "consignee":
                out.append(c)
                continue
            invented = FieldValue(field="consignee", raw="ZEPHYR OCEANIC HOLDINGS (PTY) LTD",
                                  normalised="ZEPHYR OCEANIC", present=True,
                                  evidence=c.bl.evidence, extractor="llm")
            out.append(FieldComparison(field="consignee", verdict=MISMATCH,
                                       si=c.si, bl=invented))
        return out

    plain = run_gate("email_001")
    assert plain.status == "grounded"

    decision = run_gate("email_001", mutate=fabricate_bl_consignee)
    assert decision.status == "untraceable_value"
    assert decision.review_reason == "unreadable"
    assert decision.untraceable_fields == ["consignee"]
    assert decision.evidence_checked == 2 * len(COMPARE_FIELDS)
    assert decision.evidence_traced == decision.evidence_checked - 1
    assert any(s.startswith("untraceable:BL:consignee") for s in decision.blocked_signals)
    assert "consignee" in decision.reason


# --------------------------------------------------------------------------
# 6. Zero attachments, two opposite outcomes (DATA_NOTES §5a)
# --------------------------------------------------------------------------
def test_request_to_produce_a_draft_bl_needs_no_comparison():
    """email_003: "Please assist to send the draft BL ... for checking asap"."""
    decision = run_gate("email_003")
    assert decision.status == "no_comparison_needed"
    assert decision.review_reason is None
    assert "attachments:0" in decision.blocked_signals


def test_dropped_attachments_is_a_missing_attachment():
    """email_506: "please compare ... (attachments appear to have been dropped)"."""
    decision = run_gate("email_506")
    assert decision.status == "missing_attachment"
    assert decision.review_reason == "missing_attachment"
    assert "re-send" in decision.recovery.lower()


def test_the_two_zero_attachment_cases_do_not_collapse_together():
    """Same category, same zero attachments, opposite correct outcomes."""
    assert run_gate("email_003").status != run_gate("email_506").status


def test_one_attachment_is_always_missing_attachment():
    """email_507 attaches the SI only. You cannot compare half a pair."""
    decision = run_gate("email_507")
    assert decision.status == "missing_attachment"
    assert decision.review_reason == "missing_attachment"
    assert "missing_document:BL" in decision.blocked_signals
    assert "draft BL" in decision.recovery


def test_one_attachment_beats_a_draft_request_intent():
    """Intent cannot rescue a half pair: something was attached, and half of
    what the sender meant to send is missing either way."""
    email = load_email("email_507")
    si_doc, bl_doc = read_pair(email)
    decision = gate.evaluate(
        si_doc=si_doc, bl_doc=bl_doc,
        si_fields=build_fields(si_doc, "SI"), bl_fields=None,
        comparisons=[], intent=StubIntent(requests_draft=True),
        pair_problem=None,
    )
    assert_contract(decision)
    assert decision.status == "missing_attachment"


# --------------------------------------------------------------------------
# 7. Robustness — the gate must never take a batch run down
# --------------------------------------------------------------------------
def test_evaluate_survives_a_malformed_comparison():
    si_doc, bl_doc = read_pair(load_email("email_001"))
    decision = gate.evaluate(
        si_doc=si_doc, bl_doc=bl_doc, si_fields=None, bl_fields=None,
        comparisons=[object()], intent=None, pair_problem=None,  # type: ignore[list-item]
    )
    assert_contract(decision)
    assert decision.review_reason == "unreadable"
    assert any(s.startswith("gate_error:") for s in decision.blocked_signals)


def test_evaluate_accepts_no_intent_and_no_documents():
    decision = gate.evaluate(si_doc=None, bl_doc=None, si_fields=None, bl_fields=None,
                             comparisons=[], intent=None, pair_problem=None)
    assert_contract(decision)
    assert decision.status == "no_comparison_needed"
    assert "intent:unclear" in decision.blocked_signals


def test_trace_value_is_false_for_a_document_with_no_text():
    doc = ParsedDoc(path="scan.pdf", ext=".pdf", readable=False,
                    unreadable_reason="no_text_layer", text="")
    assert gate.trace_value(doc, FieldValue(field="shipper", raw="ANY NAME",
                                            present=True)) is False
