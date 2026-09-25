"""Tests for the two OCR defences: the digit guard and the confusion veto.

These are the only places in the pipeline where two values that are not
canonically equal are not reported as a discrepancy, so they get their own
file and their own argument.

`docs/DATA_NOTES.md` §4 forbids fuzzy value matching, for a good reason: the
entity pools contain deliberately near-identical parties and ports, and any
similarity threshold loose enough to merge a scanning artefact also merges two
real companies, taking a planted defect with it. The confusion veto is not an
exception to that rule, because of one property these tests exist to pin:

    **It never produces MATCH.**

A confusable pair becomes `UNCOMPARABLE`, which the gate turns into
`NEEDS_REVIEW` with both readings attached. Its worst case is a human looking
at a pair that was fine; it cannot clear a bad BL. A similarity threshold can,
which is why one is banned and this is not.

The digit guard has an even narrower claim: it only ever turns a number into
`None`. It cannot make two numbers agree either.

What is measured, rather than asserted, lives in `docs/ADVERSARIAL.md` §1:
injecting one confusable character per field turned 982 reads into silently
wrong values and invented 151 defects before these two changes, and zero and
zero after.
"""
from __future__ import annotations

import itertools
import json

import pytest

from conftest import requires_bundle, skip_without_bundle
from sdoc import evidence_gate as gate
from sdoc import normalize
from sdoc.compare import _ocr_surface, compare_field, ocr_confusable
from sdoc.schema import (
    MISMATCH,
    PARTY_FIELDS,
    PORT_FIELDS,
    UNCOMPARABLE,
    DocFields,
    Evidence,
    FieldValue,
    ParsedDoc,
)


# --------------------------------------------------------------------------
# The relation itself
# --------------------------------------------------------------------------
@pytest.mark.parametrize("a, b", [
    ("NANTONG CHINA", "NANT0NG CHINA"),          # O / 0
    ("APRIL FAR EAST M", "APR1L FAR EAST M"),    # I / 1
    ("MOORIM SP", "M00RIM SP"),                  # two of them, same class
    ("SINGAPORE", "5INGAPORE"),                  # S / 5
    ("BUSAN KOREA", "8USAN KOREA"),              # B / 8
    # Two damaged characters drawn from two different classes. A bad scan
    # makes more than one mistake per line, and the outcome is an escalation
    # either way, so there is no reason to insist they share a class.
    ("BUSAN KOREA", "8U5AN KOREA"),
])
def test_a_scanning_artefact_is_recognised(a, b):
    assert ocr_confusable(a, b)
    assert ocr_confusable(b, a), "the relation must be symmetric"


@pytest.mark.parametrize("a, b, why", [
    ("NANTONG CHINA", "NANTONG CHINA", "identical values are not a confusion"),
    ("NANTONG CHINA", "NANTONG INDIA", "different country, same length"),
    ("KARACHI PAKISTAN", "MOMBASA KENYA", "different port entirely"),
    ("215950", "218950", "5 and 8 are in different confusion classes"),
    ("NANTONG", "NANT0NG CHINA", "different lengths"),
    ("BUSAN KOREA", "BUSAN JAPAN", "same length, no confusable character involved"),
])
def test_a_real_difference_is_not_explained_away(a, b, why):
    assert not ocr_confusable(a, b), why


def test_one_confusable_character_is_not_enough_if_another_differs_really():
    # First difference is O/0 and would pass on its own; the second is real.
    assert not ocr_confusable("NANTONG CHINA", "NANT0NG INDIA")


# --------------------------------------------------------------------------
# The trap pairs — the ones `docs/DATA_NOTES.md` §4 names by hand
#
# These are the value pairs a loose comparison gets wrong, and this is the
# regression guard: if the veto is ever widened into something distance-based,
# these fail before a defect is lost.
# --------------------------------------------------------------------------
TRAP_PAIRS = [
    ("APRIL FINE PAPER TRADING", "APRIL FINE PAPER TRADING MIDDLE EAST"),
    ("KPP ANTALIS SINGAPORE", "KPP ANTALIS"),
    ("NANTONG CHINA", "RUGAO NANTONG SHANGHAI CHINA"),
    ("MOMBASA KENYA", "TUTICORIN INDIA"),
    ("APRIL FAR EAST M", "APRIL FINE PAPER TRADING"),
]


@pytest.mark.parametrize("a, b", TRAP_PAIRS)
def test_the_named_near_identical_entities_stay_distinct(a, b):
    assert not ocr_confusable(a, b)


# --------------------------------------------------------------------------
# Through the comparer
# --------------------------------------------------------------------------
def _value(field: str, raw) -> FieldValue:
    canonical, number = normalize.normalise_field(field, raw)
    return FieldValue(
        field=field,
        raw=raw,
        normalised=canonical,
        number=number,
        present=canonical is not None,
        evidence=Evidence(doc_role="SI", locator="line 1", label=field, snippet=str(raw)),
    )


def _compare(field: str, si_raw, bl_raw):
    return compare_field(field, _value(field, si_raw), _value(field, bl_raw))


def test_a_confusable_port_is_escalated_not_reported():
    c = _compare("port_of_loading", "NANTONG, CHINA (CNNTG)", "NANT0NG, CHINA (CNNTG)")
    assert c.verdict == UNCOMPARABLE
    assert c.reason == "ocr_confusable"


def test_a_confusable_party_is_escalated_not_reported():
    c = _compare("shipper", "APRIL FAR EAST (M) SDN BHD", "APR1L FAR EAST (M) SDN BHD")
    assert c.verdict == UNCOMPARABLE
    assert c.reason == "ocr_confusable"


@pytest.mark.parametrize("field, si, bl", [
    # The damaged glyph sits inside a word canonicalisation drops on the clean
    # side only ("PORT", "CO"), so the canonical keys differ in length and only
    # the printed-text test can see that nothing but one glyph differs.
    ("port_of_loading", "PORT KLANG (WESTPORT), MALAYSIA (MYPKG)",
     "P0RT KLANG (WESTPORT), MALAYSIA (MYPKG)"),
    ("consignee", "MOORIM SP CO., LTD", "MOORIM SP C0., LTD"),
    ("shipper", "APRIL FAR EAST (M) SDN BHD", "APRIL FAR EAST (M) 5DN BHD"),
])
def test_a_glyph_damaged_inside_a_dropped_word_is_escalated(field, si, bl):
    c = _compare(field, si, bl)
    assert c.verdict == UNCOMPARABLE
    assert c.reason == "ocr_confusable"


@pytest.mark.parametrize("field, si, bl", [
    # A confusable glyph beside a real difference is still a real difference.
    ("port_of_discharge", "P0RT SAID, EGYPT", "PORT KLANG, MALAYSIA"),
    ("consignee", "MOORIM SP C0., LTD", "MOORIM PAPER CO., LTD"),
    # Same entity, different amount of text around it: not the same length,
    # so the printed-text test cannot fire and the canonical verdict stands.
    ("consignee", "APRIL FINE PAPER TRADING",
     "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"),
])
def test_the_printed_text_test_does_not_explain_away_a_real_difference(field, si, bl):
    assert _compare(field, si, bl).verdict == MISMATCH


def test_the_veto_never_clears_a_bad_bl():
    """The point of the whole design: it escalates, it does not absolve."""
    c = _compare("consignee", "MOORIM SP CO., LTD", "M0ORIM SP CO., LTD")
    assert c.verdict != "MATCH"
    # Nor does it explain a real difference away when the printed texts
    # happen to be the same length: the printed-text test compares every
    # character, so another word at equal length stays a discrepancy.
    assert _compare("port_of_discharge", "MERSIN, TURKEY (TRMER)",
                    "LONG BEACH, US (TRMER)").verdict == MISMATCH
    assert _compare("consignee", "MOORIM SP C0., LTD", "MOORIM SQ CO., LTD").verdict == MISMATCH


@pytest.mark.parametrize("field, si, bl", [
    ("port_of_discharge", "MOMBASA, KENYA (KEMBA)", "TUTICORIN, INDIA (KEMBA)"),
    ("consignee", "APRIL FINE PAPER TRADING",
     "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"),
    ("port_of_loading", "NANTONG, CHINA", "RUGAO/NANTONG/SHANGHAI, CHINA"),
])
def test_a_real_defect_is_still_reported(field, si, bl):
    assert _compare(field, si, bl).verdict == MISMATCH


def test_numbers_are_not_put_through_the_veto():
    """A damaged number is unreadable, not confusable.

    Character-level reasoning on a quantity is the wrong tool — the fields are
    compared as numbers, and their planted defects are small. The digit guard
    below handles them by refusing to read them at all.
    """
    c = _compare("gross_weight_kg", "216,950 KG", "216,9S0 KG")
    assert c.verdict == UNCOMPARABLE
    assert c.reason in ("bl_unparseable", "si_unparseable")


# --------------------------------------------------------------------------
# The digit guard
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw", [
    "216,9S0 KG",      # S inside the digits — used to read as 2169
    "13B MT",          # B after the digits — used to read as 13,000
    "2I6950",          # I inside the digits — used to read as 2
    "I8",              # I before the digits — used to read as 8
    "1B",
    "216 9S0 kgs",
])
def test_a_damaged_number_is_unreadable_rather_than_truncated(raw):
    assert normalize.digits_contaminated(normalize.first_segment(raw))
    assert normalize.gross_weight_kg(raw) is None
    assert normalize.container_count(raw) is None


@pytest.mark.parametrize("raw, weight", [
    ("216,950 KG", 216950.0),
    ("216,950 KGS", 216950.0),      # the S is in the unit, not against a digit
    ("138 MT", 138000.0),
    ("216 950 kgs", 216950.0),
])
def test_ordinary_shipping_notation_still_reads(raw, weight):
    assert normalize.gross_weight_kg(raw) == weight


@pytest.mark.parametrize("raw", ["6 x 40'HC", "6X40HC", "6 x 4O'HC", "TOTAL 6 CONTAINERS"])
def test_damage_away_from_the_number_does_not_cost_the_reading(raw):
    """In "6 x 4O'HC" the container *size* is damaged and the count is not.

    Checking the whole value instead of the number's own edges turned 72
    readable container counts into escalations and bought no accuracy.
    """
    assert normalize.container_count(raw) == 6


# --------------------------------------------------------------------------
# Through the gate — the operator has to be told the right thing
# --------------------------------------------------------------------------
def _doc(role: str) -> ParsedDoc:
    return ParsedDoc(path=f"<{role}>", ext=".txt", role_hint=role,
                     readable=True, text="", doc_type="SHIPPING_INSTRUCTION")


def _fields(role: str) -> DocFields:
    return DocFields(doc=_doc(role))


#: A whole clean case, so the gate reaches the branch under test. Supplying
#: one comparison instead would be answered by the blank-value branch, which
#: is correct of it: six fields nobody produced a verdict for are six fields
#: the decision cannot rest on.
_CLEAN_CASE = {
    "shipper": "APRIL FAR EAST (M) SDN BHD",
    "consignee": "MOORIM SP CO., LTD",
    "notify_party": "PACIFIC OFFICE (M) SDN BHD",
    "port_of_loading": "NANTONG, CHINA (CNNTG)",
    "port_of_discharge": "KARACHI, PAKISTAN (PKKHI)",
    "container_count": "6 x 40'HC",
    "gross_weight_kg": "216,950 KG",
}


def _case(**damaged: str):
    """Seven comparisons, all matching except the fields named in `damaged`."""
    return [
        _compare(field, raw, damaged.get(field, raw))
        for field, raw in _CLEAN_CASE.items()
    ]


def test_the_gate_escalates_a_confusable_field_and_says_why():
    comparisons = _case(port_of_loading="NANT0NG, CHINA (CNNTG)")
    decision = gate.evaluate(
        si_doc=_doc("SI"), bl_doc=_doc("BL"),
        si_fields=_fields("SI"), bl_fields=_fields("BL"),
        comparisons=comparisons, intent=None, pair_problem=None,
    )
    assert decision.status == "ocr_confusable"
    assert decision.review_reason == "unreadable"
    assert not decision.allows_defect, "the case must not be auto-decided"
    assert decision.recovery.strip()
    # The failure this wording guards against: both documents plainly state
    # the port, so telling an operator it is missing destroys their trust in
    # every other escalation the tool produces.
    assert "do not state" not in decision.reason
    assert "port of loading" in decision.reason


# --------------------------------------------------------------------------
# The safety argument, checked against the actual data
# --------------------------------------------------------------------------
@requires_bundle
def test_no_two_real_entities_in_the_dataset_are_confusable():
    """The veto cannot swallow a defect this generator is able to plant.

    The planted defects substitute whole entities, and the pools are far apart
    in edit space: no two distinct party or port values are confusable, and
    none is even within two characters at equal length. If a future dataset
    ever does contain such a pair, this fails rather than quietly losing the
    defect it belongs to.
    """
    skip_without_bundle()
    from pathlib import Path

    from sdoc.pipeline import Pipeline, PipelineConfig
    from sdoc.schema import EmailRecord

    root = Path(__file__).resolve().parents[2] / "data" / "bundle"
    pipeline = Pipeline(PipelineConfig(data_root=root, llm=None))
    parties: set[str] = set()
    ports: set[str] = set()
    # The veto also reads the printed text (compare._ocr_surface), so the
    # printed forms of different entities are swept too, each with its key.
    surfaces: dict[str, set[tuple[str, str]]] = {"parties": set(), "ports": set()}
    for path in sorted((root / "inbox").glob("email_*.json")):
        email = EmailRecord.from_json(json.loads(path.read_text(encoding="utf-8")))
        for c in (pipeline.process(email).comparisons or []):
            pool = parties if c.field in PARTY_FIELDS else ports if c.field in PORT_FIELDS else None
            if pool is None:
                continue
            for side in (c.si, c.bl):
                if side.normalised:
                    pool.add(side.normalised)
                    if side.raw:
                        surfaces["parties" if pool is parties else "ports"].add(
                            (_ocr_surface(side.raw), side.normalised))

    assert parties and ports, "the sweep read nothing — the bundle may be empty"
    for name, pool in (("parties", parties), ("ports", ports)):
        confusable = [(a, b) for a, b in itertools.combinations(sorted(pool), 2)
                      if ocr_confusable(a, b)]
        assert not confusable, f"{name}: {confusable[:3]}"
        printed = [(a, b) for (a, ka), (b, kb) in itertools.combinations(sorted(surfaces[name]), 2)
                   if ka != kb and ocr_confusable(a, b)]
        assert not printed, f"{name} (printed text): {printed[:3]}"
