"""Regression tests for the truncation repair in `sdoc.compare`.

A party name too long for its column wraps onto the next line and the reader
keeps only the first line, so the SI reads `APRIL FINE PAPER TRADING (MIDDLE`
against a BL that reads `APRIL FINE PAPER TRADING (MIDDLE EAST) FZE`. The
adversarial harness measured what that costs: wrapping long party names
produced 74 silently wrong values and 64 discrepancies that do not exist. The
repair takes the false discrepancies to 0.

These tests exist because the repair is the one place in the pipeline where a
value is *changed* after extraction, and a repair that could invent agreement
would be far worse than the wrapping it fixes — it would turn a real defect
into a clean BL. So every test here pins one half of that bargain:

* the repair completes a value we cut short, and
* the repair cannot manufacture a match that the documents do not support.

The second half is the load-bearing one, and `test_genuinely_different_parties_
survive_the_repair_on_the_real_email_145_pair` runs it against a real file, not
a fixture, so it fails if the narrowness is ever relaxed.

Nothing here consults `data/_grader/`. `email_145` is used because its SI and BL
genuinely name different shippers with a shared prefix — the exact shape the
repair must refuse to close.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import requires_bundle
from sdoc import normalize, readers
from sdoc.compare import (
    _REPAIRABLE,
    _is_token_prefix,
    compare_documents,
    defect_fields,
)
from sdoc.schema import (
    MATCH,
    MISMATCH,
    NUMERIC_FIELDS,
    DocFields,
    Evidence,
    FieldValue,
    ParsedDoc,
)

DATA = Path(__file__).resolve().parents[2] / "data" / "bundle"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def _value(field: str, raw: str, role: str, locator: str) -> FieldValue:
    """A hand-built FieldValue that carries evidence.

    Evidence is not optional padding in these tests. The repair has to extend
    the snippet so a reviewer sees both lines of the wrap, and a fixture with
    `evidence=None` would let that contract rot unnoticed.
    """
    canonical, number = normalize.normalise_field(field, raw)
    return FieldValue(
        field=field,
        raw=raw,
        normalised=canonical,
        number=number,
        present=canonical is not None,
        blank=normalize.is_blank(raw),
        evidence=Evidence(doc_role=role, locator=locator, label=field, snippet=raw[:200]),
    )


def _document(text: str, role: str, values: dict[str, tuple[str, str]]) -> DocFields:
    """A DocFields whose `doc.text` is the document the values were cut from.

    The repair reads the continuation out of `doc.text`, so unlike the
    synthetic fixtures in `test_compare.py` these documents must carry real
    text — a fixture with an empty `text` would make every test here pass for
    the wrong reason (`_extend` returns the value untouched when there is
    nothing to read).
    """
    doc = DocFields(doc=ParsedDoc(path=f"<{role}>", ext=".txt", role_hint=role, text=text))
    for field, (raw, locator) in values.items():
        doc.fields[field] = _value(field, raw, role, locator)
    return doc


def _by_field(si: DocFields, bl: DocFields) -> dict:
    return {c.field: c for c in compare_documents(si, bl)}


# The layout is copied from `data/bundle/attachments/email_145_SI.txt`: label,
# value, then an indented continuation block. That block is exactly why the
# repair cannot simply glue the next line on — on a real document the next line
# is usually the address, and only sometimes the rest of the name.
_SI_WRAPPED = """SHIPPING INSTRUCTION
========================================

SHIPPER: APRIL FINE PAPER TRADING (MIDDLE
  EAST) FZE
  ON BEHALF OF VITAL SOLUTIONS PTE LTD; 77 ROBINSON ROAD, #21-01; SINGAPORE 068896
Port of Loading: RUGAO/NANTONG/SHANGHAI,
  CHINA (CNNTG)
Port of Discharge (POD): BUSAN, SOUTH KOREA (KRPUS)
"""

_BL_FULL = """BILL OF LADING (DRAFT)
========================================

Shipper (Principal or Seller): APRIL FINE PAPER TRADING (MIDDLE EAST) FZE
  ON BEHALF OF VITAL SOLUTIONS PTE LTD; 77 ROBINSON ROAD, #21-01; SINGAPORE 068896
Port of Loading (POL): RUGAO/NANTONG/SHANGHAI, CHINA (CNNTG)
POD: BUSAN, SOUTH KOREA (KRPUS)
"""


def _wrapped_si() -> DocFields:
    return _document(_SI_WRAPPED, "SI", {
        "shipper": ("APRIL FINE PAPER TRADING (MIDDLE", "line 4"),
        "port_of_loading": ("RUGAO/NANTONG/SHANGHAI,", "line 7"),
        "port_of_discharge": ("BUSAN, SOUTH KOREA (KRPUS)", "line 9"),
    })


def _full_bl() -> DocFields:
    return _document(_BL_FULL, "BL", {
        "shipper": ("APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", "line 4"),
        "port_of_loading": ("RUGAO/NANTONG/SHANGHAI, CHINA (CNNTG)", "line 6"),
        "port_of_discharge": ("BUSAN, SOUTH KOREA (KRPUS)", "line 7"),
    })


# --------------------------------------------------------------------------
# 1. A value we cut short is completed from its own document
# --------------------------------------------------------------------------
def test_wrapped_party_name_is_completed_from_its_own_document():
    """The 74-silent-wrong-values case: the SI shipper wrapped, the BL did not.

    The completion is taken from the SI's own next line and has to reproduce
    the BL's canonical key exactly, which is the only reason we are allowed to
    conclude that we cut the value short rather than that the two documents
    disagree.
    """
    shipper = _by_field(_wrapped_si(), _full_bl())["shipper"]

    assert shipper.verdict == MATCH
    assert shipper.si.raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert shipper.si.normalised == "APRIL FINE PAPER TRADING MIDDLE EAST"
    assert shipper.si.normalised == shipper.bl.normalised


def test_a_wrapped_port_name_is_repaired_the_same_way():
    """Ports wrap too, and `RUGAO/NANTONG/SHANGHAI,` is the long one in this set."""
    port = _by_field(_wrapped_si(), _full_bl())["port_of_loading"]

    assert port.verdict == MATCH
    assert port.si.raw == "RUGAO/NANTONG/SHANGHAI, CHINA (CNNTG)"
    assert port.si.normalised == "RUGAO NANTONG SHANGHAI CHINA"


def test_the_repair_works_on_whichever_document_was_cut_short():
    """Nothing about wrapping is specific to the SI — the BL's column is narrower.

    The SI is the reference document for *verdicts*, but not for repairs: the
    short side is whichever one the reader truncated.
    """
    si_text = _BL_FULL.replace("BILL OF LADING (DRAFT)", "SHIPPING INSTRUCTION")
    bl_text = _SI_WRAPPED.replace("SHIPPING INSTRUCTION", "BILL OF LADING (DRAFT)")
    si = _document(si_text, "SI", {
        "shipper": ("APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", "line 4"),
    })
    bl = _document(bl_text, "BL", {
        "shipper": ("APRIL FINE PAPER TRADING (MIDDLE", "line 4"),
    })
    shipper = _by_field(si, bl)["shipper"]

    assert shipper.verdict == MATCH
    assert shipper.bl.raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert shipper.si.raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"


def test_the_repair_leaves_the_extractors_fieldvalues_alone():
    """`compare.py` owns no document state; the repaired value is a copy.

    The report prints what the extractor read *and* what was compared, so a
    repair that mutated the extractor's FieldValue would erase the evidence
    that the document was wrapped at all.
    """
    si = _wrapped_si()
    compare_documents(si, _full_bl())

    assert si.get("shipper").raw == "APRIL FINE PAPER TRADING (MIDDLE"
    assert si.get("shipper").extractor == "rule"


# --------------------------------------------------------------------------
# 2. The repair cannot invent agreement
# --------------------------------------------------------------------------
@requires_bundle
def test_genuinely_different_parties_survive_the_repair_on_the_real_email_145_pair():
    """email_145 is the case the repair must refuse to close, and it is real.

        SI  SHIPPER: APRIL FINE PAPER TRADING
              ON BEHALF OF VITAL SOLUTIONS PTE LTD; 77 ROBINSON ROAD, ...
        BL  Shipper (Principal or Seller): APRIL FINE PAPER TRADING (MIDDLE EAST) FZE

    The SI value is a token prefix of the BL value, so the repair *is*
    attempted — that is asserted below, otherwise this test would pass simply
    because nothing happened. The SI's next line is its "on behalf of" and
    address block, the completion does not reproduce the BL's canonical key,
    and the mismatch stands. These are two different legal entities in two
    different countries, and this is a planted defect we are scored on.
    """
    pytest.importorskip("sdoc.extract.fields")
    from sdoc.extract.fields import extract_fields

    si = extract_fields(readers.read_attachment(DATA, "attachments/email_145_SI.txt"), "SI")
    bl = extract_fields(readers.read_attachment(DATA, "attachments/email_145_BL.txt"), "BL")
    comparisons = compare_documents(si, bl)
    shipper = {c.field: c for c in comparisons}["shipper"]

    # the repair was reached, not skipped: this is the prefix relation that
    # sends `_repaired` into `_extend` in the first place
    assert _is_token_prefix(normalize.org(si.get("shipper").raw),
                            normalize.org(bl.get("shipper").raw))

    assert shipper.verdict == MISMATCH
    assert shipper.si.raw == "APRIL FINE PAPER TRADING"
    assert shipper.si.extractor == "rule"          # no "+wrap": nothing was adopted
    assert defect_fields(comparisons) == ["shipper"]


def test_an_address_block_is_never_adopted_as_the_rest_of_a_name():
    """The synthetic twin of email_145, so the mechanism is pinned in isolation."""
    text = """SHIPPING INSTRUCTION
========================================

SHIPPER: APRIL FINE PAPER TRADING
  ON BEHALF OF VITAL SOLUTIONS PTE LTD; 77 ROBINSON ROAD, #21-01; SINGAPORE 068896
"""
    si = _document(text, "SI", {"shipper": ("APRIL FINE PAPER TRADING", "line 4")})
    shipper = _by_field(si, _full_bl())["shipper"]

    assert shipper.verdict == MISMATCH
    assert shipper.si.raw == "APRIL FINE PAPER TRADING"
    assert shipper.si.extractor == "rule"


def test_the_near_identical_port_trap_is_untouched_by_the_repair():
    """`NANTONG, CHINA` vs `RUGAO/NANTONG/SHANGHAI, CHINA` (DATA_NOTES.md §4).

    These are different load ports and the short one is a *substring*, not a
    token prefix, of the long one — so the repair never even looks at the next
    line. Put the long name on that next line anyway: the verdict must not move.
    """
    text = """SHIPPING INSTRUCTION

Port of Loading: NANTONG, CHINA
  (CNNTG); RUGAO/NANTONG/SHANGHAI, CHINA
"""
    si = _document(text, "SI", {"port_of_loading": ("NANTONG, CHINA", "line 3")})
    bl = _document("POL: RUGAO/NANTONG/SHANGHAI, CHINA\n", "BL",
                   {"port_of_loading": ("RUGAO/NANTONG/SHANGHAI, CHINA", "line 1")})
    port = _by_field(si, bl)["port_of_loading"]

    assert port.verdict == MISMATCH
    assert port.si.extractor == "rule"


def test_a_value_that_does_not_end_at_a_line_break_is_never_completed():
    """A wrap breaks at a line end, so anything else means we did not cut here.

    `_extend` locates the value in its own document and reads on from the end
    of it. If the very next character is not whitespace then the search did not
    land on a value boundary at all — it landed before the comma of
    `NANTONG, CHINA`, or mid-token inside `NANTONG/SHANGHAI` — and the text
    that follows is the remainder of something we were already in the middle
    of, not a continuation line.

    Gluing it on regardless manufactures a raw value the document does not
    contain: `NANTONG , CHINA`, stray space and all, shown to a reviewer as
    what the SI says. Without this guard the pair below is reported MATCH,
    `rule+wrap`, on the strength of that invented string. The repair is allowed
    to recognise that we cut a value short; it is not allowed to write text
    into the document to get there, so the honest answer here is the difference
    we can actually see, escalated.
    """
    text = """SHIPPING INSTRUCTION

Port of Loading: NANTONG, CHINA
"""
    si = _document(text, "SI", {"port_of_loading": ("NANTONG", "line 3")})
    bl = _document("POL: NANTONG, CHINA\n", "BL",
                   {"port_of_loading": ("NANTONG, CHINA", "line 1")})
    port = _by_field(si, bl)["port_of_loading"]

    # the repair was reached, not skipped: without this the test could pass
    # simply because `_repaired` never called `_extend`
    assert _is_token_prefix(normalize.port("NANTONG"), normalize.port("NANTONG, CHINA"))

    assert port.verdict == MISMATCH
    assert port.si.raw == "NANTONG"
    assert port.si.extractor == "rule"
    assert port.si.raw in text, "the compared value is not text the SI contains"


def test_a_completion_that_overshoots_the_other_sides_name_is_not_adopted():
    """The completion must reproduce the other side's canonical form *exactly*.

    Equality is the whole guard. Accepting a completion that merely *starts*
    with the other side's canonical form lets the SI's next line run straight
    past the name the BL gave: `APRIL FINE` + `PAPER TRADING (MIDDLE EAST) FZE`
    begins with the BL's `APRIL FINE PAPER TRADING` and keeps going into the
    Middle East subsidiary, which DATA_NOTES.md §4 records as a different legal
    entity in a different country.

    The verdict cannot catch this on its own and stays MISMATCH either way,
    because the final comparison is still exact on canonical keys — which is
    exactly why the assertions below are on the raw value, the extractor and
    the snippet. What a looser test costs is the row the reviewer reads: a raw
    value rewritten to a company neither document put in that field, stamped
    `+wrap` as though a wrap had been confirmed, with an evidence snippet
    carrying a second line that was never part of the value. A silently wrong
    value is the one failure mode this module exists to prevent, and it is no
    less wrong for sitting beside a correct verdict.
    """
    text = """SHIPPING INSTRUCTION

SHIPPER: APRIL FINE
  PAPER TRADING (MIDDLE EAST) FZE
  77 ROBINSON ROAD, #21-01; SINGAPORE 068896
"""
    si = _document(text, "SI", {"shipper": ("APRIL FINE", "line 3")})
    bl = _document("Shipper (Principal or Seller): APRIL FINE PAPER TRADING\n", "BL",
                   {"shipper": ("APRIL FINE PAPER TRADING", "line 1")})
    shipper = _by_field(si, bl)["shipper"]

    # the repair was reached, and the SI's next line really does complete the
    # name — just not to the name the BL printed
    assert _is_token_prefix(normalize.org("APRIL FINE"),
                            normalize.org("APRIL FINE PAPER TRADING"))
    assert normalize.org("APRIL FINE PAPER TRADING (MIDDLE EAST) FZE").startswith(
        normalize.org("APRIL FINE PAPER TRADING"))       # what we must not accept

    assert shipper.verdict == MISMATCH
    assert shipper.si.raw == "APRIL FINE"
    assert shipper.si.normalised == "APRIL FINE"
    assert shipper.si.extractor == "rule"
    assert shipper.si.evidence.snippet == "APRIL FINE"


# --------------------------------------------------------------------------
# 3. `_is_token_prefix` is whole words only
# --------------------------------------------------------------------------
def test_a_prefix_is_whole_words_not_characters():
    """`KLANG` must not count as a prefix of `KLANGER`.

    A plain `str.startswith` would say yes here, and the repair would start
    chasing coincidences between unrelated ports.
    """
    assert "KLANGER MALAYSIA".startswith("KLANG")       # what we must not do
    assert not _is_token_prefix("KLANG", "KLANGER MALAYSIA")
    assert _is_token_prefix("KLANG", "KLANG MALAYSIA")


@pytest.mark.parametrize("short, long", [
    ("", "APRIL FINE"),                                  # nothing is not a prefix
    ("APRIL FINE", "APRIL FINE"),                        # equal is not a prefix
    ("APRIL FINE PAPER", "APRIL FINE"),                  # longer is not a prefix
    ("FINE PAPER", "APRIL FINE PAPER TRADING"),          # must start at the start
])
def test_what_does_not_count_as_a_token_prefix(short, long):
    assert not _is_token_prefix(short, long)


# --------------------------------------------------------------------------
# 4. Only the line immediately below the value is considered
# --------------------------------------------------------------------------
def test_a_completion_two_lines_down_is_not_adopted():
    """A wrap continues on the very next line; anything else is another field.

    Here the rest of the name really is in the document, but an address line
    sits between it and the value. Searching past that line would mean reading
    the neighbouring block, which is how the consignee gets confused with its
    own address in the first place.
    """
    text = """SHIPPING INSTRUCTION

SHIPPER: APRIL FINE PAPER TRADING (MIDDLE
  77 ROBINSON ROAD, #21-01; SINGAPORE 068896
  EAST) FZE
"""
    si = _document(text, "SI", {"shipper": ("APRIL FINE PAPER TRADING (MIDDLE", "line 3")})
    shipper = _by_field(si, _full_bl())["shipper"]

    assert shipper.verdict == MISMATCH
    assert shipper.si.raw == "APRIL FINE PAPER TRADING (MIDDLE"
    assert shipper.si.extractor == "rule"


def test_a_blank_line_between_the_two_halves_does_not_stop_the_repair():
    """Blank lines are layout, not content, and readers leave them in the text.

    Skipping empties is not the same as searching on: the *first line carrying
    text* is still the only candidate, so this does not weaken the rule above.
    """
    text = """SHIPPING INSTRUCTION

SHIPPER: APRIL FINE PAPER TRADING (MIDDLE

  EAST) FZE
"""
    si = _document(text, "SI", {"shipper": ("APRIL FINE PAPER TRADING (MIDDLE", "line 3")})
    shipper = _by_field(si, _full_bl())["shipper"]

    assert shipper.verdict == MATCH
    assert shipper.si.raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"


# --------------------------------------------------------------------------
# 5. Parties and ports only
# --------------------------------------------------------------------------
def test_the_repair_is_confined_to_party_and_port_fields():
    assert set(_REPAIRABLE).isdisjoint(NUMERIC_FIELDS)


def test_a_number_is_never_completed_from_the_next_line():
    """A weight or a box count does not wrap, and must not be stitched together.

    The document below is built so that the naive stitch would work — `118`
    followed by `,270 KG` canonicalises to the BL's 118270 — and the verdict
    still has to be MISMATCH. Strictly the field guard in `_repaired` is belt
    and braces here, because a numeric canonical form is always a single token
    and `_is_token_prefix` needs at least two on the long side; the guard is
    what makes that a decision rather than an accident, so both are pinned.
    """
    text = """SHIPPING INSTRUCTION

GROSS WEIGHT: 118
  ,270 KG
Total Containers: 5
  x 40'HC
"""
    si = _document(text, "SI", {
        "gross_weight_kg": ("118", "line 3"),
        "container_count": ("5", "line 5"),
    })
    bl = _document("Gross Weight (KGS): 118,270 KG\n", "BL", {
        "gross_weight_kg": ("118,270 KG", "line 1"),
        "container_count": ("5 x 40'HC", "line 1"),
    })
    by_field = _by_field(si, bl)

    assert by_field["gross_weight_kg"].verdict == MISMATCH
    assert by_field["gross_weight_kg"].si.raw == "118"
    assert by_field["gross_weight_kg"].si.extractor == "rule"
    # the count happens to agree (5 == 5), so all this pins is that agreeing
    # did not involve a repair
    assert by_field["container_count"].si.extractor == "rule"


# --------------------------------------------------------------------------
# 6. What the reviewer sees afterwards
# --------------------------------------------------------------------------
def test_a_repaired_value_says_so_and_shows_both_lines():
    """A repair is a change to a document value, so it has to be visible.

    The extractor is suffixed `+wrap` and the snippet carries both halves, so a
    reviewer opening the case sees the wrap rather than a value that silently
    disagrees with the line they are looking at. The locator and label are
    untouched: they still point at where the value starts.
    """
    shipper = _by_field(_wrapped_si(), _full_bl())["shipper"]

    assert shipper.si.extractor == "rule+wrap"
    assert shipper.si.evidence is not None
    assert shipper.si.evidence.snippet == "APRIL FINE PAPER TRADING (MIDDLE / EAST) FZE"
    assert shipper.si.evidence.locator == "line 4"
    assert shipper.si.evidence.doc_role == "SI"
    assert shipper.si.evidence.label == "shipper"


def test_evidence_is_never_dropped_by_the_repair():
    """CLAUDE.md rule 6: no code path may produce a bare value.

    Only the fields these fixtures actually carry are checked. A field neither
    document mentions is an `UNCOMPARABLE/si_missing` placeholder that never
    had evidence to lose, and asserting on it would test `DocFields.get`
    rather than the repair.
    """
    si, bl = _wrapped_si(), _full_bl()
    populated = set(si.fields) & set(bl.fields)
    assert populated, "fixture carries no comparable field"

    for c in compare_documents(si, bl):
        if c.field not in populated:
            continue
        assert c.si.evidence is not None, f"{c.field}: SI evidence lost"
        assert c.bl.evidence is not None, f"{c.field}: BL evidence lost"


def test_the_untouched_side_keeps_its_plain_extractor():
    """Only the document that was cut short is marked; the other is not evidence
    of anything having happened to it."""
    shipper = _by_field(_wrapped_si(), _full_bl())["shipper"]
    assert shipper.bl.extractor == "rule"


# --------------------------------------------------------------------------
# 7. Equal keys short-circuit before any repair is attempted
# --------------------------------------------------------------------------
def test_values_that_already_agree_are_never_rewritten():
    """The SI here genuinely is wrapped — and is still left exactly as read.

    `KPP-ANTALIS (SINGAPORE) PTE.` continues on the next line with `LTD.`, but
    `normalize.org` drops legal-form tokens, so the two canonical forms already
    agree and there is nothing to repair. Rewriting the raw value anyway would
    mean the report showed the reviewer text that is not what the extractor
    read, for no gain.
    """
    text = """SHIPPING INSTRUCTION

Consignee: KPP-ANTALIS (SINGAPORE) PTE.
  LTD.
  77 ROBINSON ROAD, #21-01; SINGAPORE 068896
"""
    si = _document(text, "SI", {"consignee": ("KPP-ANTALIS (SINGAPORE) PTE.", "line 3")})
    bl = _document("Consignee: KPP-ANTALIS SINGAPORE\n", "BL",
                   {"consignee": ("KPP-ANTALIS SINGAPORE", "line 1")})
    consignee = _by_field(si, bl)["consignee"]

    assert consignee.verdict == MATCH
    assert consignee.si.raw == "KPP-ANTALIS (SINGAPORE) PTE."
    assert consignee.si.extractor == "rule"
    assert consignee.si.evidence.snippet == "KPP-ANTALIS (SINGAPORE) PTE."


# --------------------------------------------------------------------------
# Known hazard: `_extend` locates the value by text search, not by locator
# --------------------------------------------------------------------------
# `_extend` does `text.find(value.raw)` and reads the line below *that*
# position, ignoring the evidence locator that says where the value actually
# came from. In this dataset the consignee and the notify party are very often
# the same company, so the same raw string occurs twice and the second
# occurrence's continuation is never reached.
#
# The document below makes that bite. Both fields begin with the same line;
# the consignee's block continues `EAST) FZE` and the notify party's continues
# `EAST ASIA) PTE LTD`, and those are two different companies. Against a BL
# naming the first of them, the honest verdicts are MATCH for the consignee
# and MISMATCH for the notify party.
#
# It has never fired on real data — the repair applied 0 times across the
# 520-email inbox on a wrong occurrence — so it is recorded rather than fixed.
# Recorded in two halves, though, and not as one test asserting the wrong
# answer: pinning MATCH on the notify party would make the correct fix arrive
# as a red suite, as though repairing the defect had broken something. The
# half that is right is a plain test; the half that is wrong states what the
# right behaviour *would* be under a strict xfail, the same way
# `test_rows_separators.py` records the `resolve("POL")` hole. Anchor `_extend`
# on the evidence locator and the marker is what the suite complains about.
_SHARED_FIRST_LINE_SI = """SHIPPING INSTRUCTION

Consignee (Non-Negotiable): APRIL FINE PAPER TRADING (MIDDLE
  EAST) FZE
  77 ROBINSON ROAD, #21-01; SINGAPORE 068896
Notify Party/Intermediate Consignee: APRIL FINE PAPER TRADING (MIDDLE
  EAST ASIA) PTE LTD
"""


def _shared_first_line_pair() -> tuple[DocFields, DocFields]:
    """An SI whose consignee and notify party are cut to the same first line."""
    si = _document(_SHARED_FIRST_LINE_SI, "SI", {
        "consignee": ("APRIL FINE PAPER TRADING (MIDDLE", "line 3"),
        "notify_party": ("APRIL FINE PAPER TRADING (MIDDLE", "line 6"),
    })
    bl = _document("Consignee: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE\n", "BL", {
        "consignee": ("APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", "line 1"),
        "notify_party": ("APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", "line 1"),
    })
    return si, bl


def test_a_wrap_is_still_repaired_when_a_later_field_shares_its_first_line():
    """The half that is right: the consignee is completed from its own block.

    A duplicated first line elsewhere in the document must not stop a value
    that genuinely wrapped from being repaired — `text.find` lands on the
    consignee here, which is where the consignee actually is.
    """
    consignee = _by_field(*_shared_first_line_pair())["consignee"]

    assert consignee.verdict == MATCH
    assert consignee.si.raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert consignee.si.extractor == "rule+wrap"


@pytest.mark.xfail(
    strict=True,
    reason="`_extend` does text.find(value.raw), so the notify party is "
           "completed from the consignee's block three lines above the one its "
           "evidence points at; the fix is to anchor on the evidence locator",
)
def test_a_continuation_is_read_from_the_block_the_evidence_points_at():
    """The half that is wrong, stated as the behaviour we want.

    The notify party's evidence says line 6, and line 6 continues
    `EAST ASIA) PTE LTD` — a different company from the `(MIDDLE EAST) FZE` on
    the BL, so nothing there completes the BL's name and the value should come
    back untouched and MISMATCH. What happens instead is that the search finds
    the consignee's identical first line on line 3, adopts *its* continuation,
    and reports MATCH.

    Asserted the right way round on purpose. The day `_extend` anchors on the
    evidence locator this passes, and strict xfail turns that into a loud
    "remove the marker" rather than either a silent green or a red suite
    blaming the repair for fixing a defect.
    """
    si, bl = _shared_first_line_pair()
    notify = _by_field(si, bl)["notify_party"]

    # the fixture really does put a different company under the locator
    assert notify.si.evidence.locator == "line 6"
    assert "EAST ASIA" in _SHARED_FIRST_LINE_SI.splitlines()[6]

    assert notify.verdict == MISMATCH
    assert notify.si.raw == "APRIL FINE PAPER TRADING (MIDDLE"
    assert notify.si.extractor == "rule"
