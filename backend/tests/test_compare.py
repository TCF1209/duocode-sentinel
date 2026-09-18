"""Tests for `sdoc.compare`.

Two kinds of test here, on purpose:

* **Real-file tests** run the actual readers over attachments in
  `data/bundle/` and compare the result. They are what proves the module works
  on the documents we will be scored on, including the PDF pair whose columns
  have to be reconstructed from word coordinates.
* **Trap tests** pin the specific near-identical values named in
  `docs/DATA_NOTES.md` §4. Each one is a value pair that a fuzzy or substring
  comparison would get wrong, and each is a regression guard: if someone later
  "improves" the comparison with a similarity threshold, these fail.

Nothing here consults `data/_grader/`. The expected verdicts for the PDF pair
were established by reading both PDFs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sdoc import labels, normalize, readers
from sdoc.compare import (
    NO_MISMATCH_TEXT,
    UNCOMPARABLE_REASONS,
    WEIGHT_TOLERANCE_KG,
    compare_documents,
    compare_field,
    defect_fields,
    summarise,
    uncomparable_fields,
)
from sdoc.schema import (
    COMPARE_FIELDS,
    MATCH,
    MISMATCH,
    UNCOMPARABLE,
    DocFields,
    Evidence,
    FieldValue,
    ParsedDoc,
)

DATA = Path(__file__).resolve().parents[2] / "data" / "bundle"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def _read_fields(rel_path: str, role: str) -> DocFields:
    """Read an attachment and lay its chunks onto the 7 fields.

    A deliberately thin stand-in for `extract/fields.py`, so these tests
    exercise `compare.py` against *real documents* without inheriting the
    extractor's scoring decisions — a comparison bug and an extraction bug then
    fail in different files. It reuses `labels.resolve` and
    `normalize.normalise_field`, so it makes the same canonical decisions the
    real extractor does; the first chunk that resolves to a field wins, which
    is what keeps the per-container rows of the PDF container table from
    overwriting the `TOTAL GROSS WEIGHT:` line beneath them. The real extractor
    is exercised separately, at the bottom of this file.
    """
    doc = readers.read_attachment(DATA, rel_path)
    out = DocFields(doc=doc)
    for chunk in doc.chunks:
        name = labels.resolve(chunk.label)
        if name is None or name in out.fields:
            continue
        canonical, number = normalize.normalise_field(name, chunk.value)
        out.fields[name] = FieldValue(
            field=name,
            raw=chunk.value,
            normalised=canonical,
            number=number,
            present=canonical is not None,
            blank=normalize.is_blank(chunk.value),
            evidence=Evidence(
                doc_role=role,
                locator=chunk.locator,
                label=chunk.label,
                snippet=chunk.value[:200],
            ),
        )
    return out


def _pair(email_id: str, ext: str) -> tuple[DocFields, DocFields]:
    return (
        _read_fields(f"attachments/{email_id}_SI.{ext}", "SI"),
        _read_fields(f"attachments/{email_id}_BL.{ext}", "BL"),
    )


def _value(field: str, raw, *, blank: bool = False) -> FieldValue:
    """A hand-built FieldValue, for the trap tests."""
    canonical, number = (None, None) if raw is None else normalize.normalise_field(field, raw)
    return FieldValue(
        field=field,
        raw=raw,
        normalised=canonical,
        number=number,
        present=canonical is not None,
        blank=blank or (raw is not None and normalize.is_blank(str(raw))),
    )


def _verdict(field: str, si_raw, bl_raw) -> str:
    return compare_field(field, _value(field, si_raw), _value(field, bl_raw)).verdict


def _synthetic_docfields(values: dict[str, object], role: str) -> DocFields:
    doc = DocFields(doc=ParsedDoc(path=f"<{role}>", ext=".txt", role_hint=role))
    for field, raw in values.items():
        doc.fields[field] = _value(field, raw)
    return doc


_CLEAN = {
    "shipper": "APRIL FINE PAPER TRADING",
    "consignee": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
    "notify_party": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
    "port_of_loading": "NANTONG, CHINA (CNNTG)",
    "port_of_discharge": "HOCHIMINH CITY, VIETNAM (VNSGN)",
    "container_count": "5 x 40'HC",
    "gross_weight_kg": "118,270 KG",
}


# --------------------------------------------------------------------------
# Shape of the result
# --------------------------------------------------------------------------
def test_one_comparison_per_field_in_schema_order():
    si, bl = _pair("email_001", "txt")
    comparisons = compare_documents(si, bl)
    assert [c.field for c in comparisons] == list(COMPARE_FIELDS)


def test_every_comparison_carries_both_sides_with_evidence():
    """The UI shows SI and BL side by side; neither side may be dropped."""
    si, bl = _pair("email_031", "txt")
    for c in compare_documents(si, bl):
        assert c.si is not None and c.bl is not None
        assert c.si.field == c.field and c.bl.field == c.field
        assert c.si.evidence is not None, f"{c.field}: SI evidence lost"
        assert c.bl.evidence is not None, f"{c.field}: BL evidence lost"
        assert c.si.evidence.doc_role == "SI"
        assert c.bl.evidence.doc_role == "BL"
        assert c.si.evidence.locator and c.si.evidence.label


def test_compare_does_not_mutate_the_extractors_fieldvalues():
    si, bl = _pair("email_031", "txt")
    before = {f: (v.raw, v.normalised, v.number) for f, v in si.fields.items()}
    compare_documents(si, bl)
    after = {f: (v.raw, v.normalised, v.number) for f, v in si.fields.items()}
    assert before == after


# --------------------------------------------------------------------------
# End to end on real .txt pairs
# --------------------------------------------------------------------------
def test_txt_pair_that_does_not_differ():
    """email_001: the SI and the BL say the same thing in different words.

    Every one of the seven labels is written differently on the two documents
    ("No. of Containers or Packages" vs "Container Count", "Discharge Port" vs
    "POD"), so a clean verdict here is also a check that label resolution and
    canonicalisation agree across the pair.
    """
    si, bl = _pair("email_001", "txt")
    comparisons = compare_documents(si, bl)

    assert [c.verdict for c in comparisons] == [MATCH] * len(COMPARE_FIELDS)
    assert defect_fields(comparisons) == []
    assert uncomparable_fields(comparisons) == []
    assert summarise(comparisons) == NO_MISMATCH_TEXT


def test_txt_pair_that_differs():
    """email_031: the draft BL inflates both the box count and the weight."""
    si, bl = _pair("email_031", "txt")
    comparisons = compare_documents(si, bl)
    by_field = {c.field: c for c in comparisons}

    assert defect_fields(comparisons) == ["container_count", "gross_weight_kg"]
    assert uncomparable_fields(comparisons) == []
    assert by_field["container_count"].si.number == 1
    assert by_field["container_count"].bl.number == 3
    assert by_field["gross_weight_kg"].si.number == pytest.approx(21114)
    assert by_field["gross_weight_kg"].bl.number == pytest.approx(23114)

    # the parties and ports are identical on both documents
    for field in ("shipper", "consignee", "notify_party",
                  "port_of_loading", "port_of_discharge"):
        assert by_field[field].verdict == MATCH, field


def test_stale_locode_does_not_hide_a_changed_port():
    """email_013: the BL changed the discharge port but kept the SI's UN/LOCODE.

    `MOMBASA, KENYA (KEMBA)` -> `TUTICORIN, INDIA (KEMBA)`. Comparing codes
    instead of names would clear this BL.
    """
    si, bl = _pair("email_013", "txt")
    by_field = {c.field: c for c in compare_documents(si, bl)}

    assert normalize.locode(by_field["port_of_discharge"].si.raw) == "KEMBA"
    assert normalize.locode(by_field["port_of_discharge"].bl.raw) == "KEMBA"
    assert by_field["port_of_discharge"].verdict == MISMATCH
    assert defect_fields(compare_documents(si, bl)) == ["port_of_discharge"]


# --------------------------------------------------------------------------
# End to end on the PDF pair (DATA_NOTES.md §3)
# --------------------------------------------------------------------------
def test_pdf_pair_email_313():
    """The two-column PDF form, read from word coordinates.

    Expectations established by reading both PDFs:

        SI  Shipper/Exporter  APRIL FINE PAPER TRADING / ON BEHALF OF ...
        BL  Shipper (Principal or Seller)   same
        SI  To the Order of   KPP-ANTALIS (SINGAPORE) PTE. LTD.
        BL  Consignee         same
        SI  Load Port         RUGAO/NANTONG/SHANGHAI, CHINA
        BL  POL               same
        SI  Total Containers  5 x 40'HC        BL  Total Containers  4 x 40'HC
        SI  TOTAL GROSS WEIGHT 118,270 KG      BL  ...(KGS)  117,770 KG

    So exactly two fields differ. A line-oriented PDF parser would instead
    report the consignee as `77 ROBINSON ROAD, #21-01` and raise three or four
    extra false alarms.
    """
    si, bl = _pair("email_313", "pdf")
    comparisons = compare_documents(si, bl)
    by_field = {c.field: c for c in comparisons}

    assert defect_fields(comparisons) == ["container_count", "gross_weight_kg"]
    assert uncomparable_fields(comparisons) == []
    for field in ("shipper", "consignee", "notify_party",
                  "port_of_loading", "port_of_discharge"):
        assert by_field[field].verdict == MATCH, (
            f"{field}: SI={by_field[field].si.raw!r} BL={by_field[field].bl.raw!r}"
        )

    assert (by_field["container_count"].si.number,
            by_field["container_count"].bl.number) == (5, 4)
    assert by_field["gross_weight_kg"].si.number == pytest.approx(118270)
    assert by_field["gross_weight_kg"].bl.number == pytest.approx(117770)


def test_pdf_pair_email_313_consignee_is_the_party_not_its_address():
    """Guards the exact failure DATA_NOTES.md §3 describes."""
    si, _ = _pair("email_313", "pdf")
    consignee = si.get("consignee")
    assert consignee.normalised == "KPP ANTALIS SINGAPORE"
    assert "ROBINSON" not in (consignee.normalised or "")


# --------------------------------------------------------------------------
# The near-identical value traps (DATA_NOTES.md §4)
# --------------------------------------------------------------------------
def test_shipper_with_extra_legal_entity_is_a_mismatch():
    """Different legal entities in different countries, not a spelling variant."""
    assert _verdict("shipper",
                    "APRIL FINE PAPER TRADING",
                    "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE") == MISMATCH


def test_port_that_is_a_substring_of_the_other_is_a_mismatch():
    assert _verdict("port_of_loading",
                    "NANTONG, CHINA",
                    "RUGAO/NANTONG/SHANGHAI, CHINA") == MISMATCH


def test_legal_suffix_variants_are_the_same_company():
    assert _verdict("consignee",
                    "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
                    "KPP-ANTALIS SINGAPORE") == MATCH


def test_the_three_traps_hold_together():
    """The point of §4: no single threshold satisfies all three at once.

    The suffix pair must merge while the other two must not — which is only
    possible because canonicalisation is rule-based (drop legal-form tokens)
    rather than a similarity score.
    """
    assert _verdict("consignee", "TOPKOPY MIDDLE EAST FZE", "EAST BRIGHT FZ-LLC") == MISMATCH
    assert _verdict("consignee", "KTP CO., LTD", "KTP CO LTD") == MATCH


# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------
def test_container_count_reads_the_quantity_not_the_box_size():
    assert _verdict("container_count", "6 x 40'HC", "6") == MATCH
    assert _verdict("container_count", "6 x 40'HC", "40") == MISMATCH
    assert _verdict("container_count", "3 x 20'GP", "4 x 20'GP") == MISMATCH


def test_gross_weight_units_are_reconciled():
    assert _verdict("gross_weight_kg", "138 MT", "138,000 KG") == MATCH
    assert _verdict("gross_weight_kg", "216,950", 216950) == MATCH


@pytest.mark.parametrize("si_kg, bl_kg", [
    (118270, 117770),      # -500 kg, the smallest planted weight defect
    (200000, 200500),      # +500 kg on a big shipment: 0.25%
    (215950, 217950),      # +2000 kg, the largest planted weight defect
])
def test_planted_weight_defects_are_not_swallowed_by_tolerance(si_kg, bl_kg):
    """A percentage tolerance would hide every one of these on a 200 t shipment."""
    assert _verdict("gross_weight_kg", f"{si_kg:,} KG", f"{bl_kg:,} KG") == MISMATCH


def test_weight_tolerance_only_absorbs_floating_point_noise():
    assert WEIGHT_TOLERANCE_KG < 1.0
    assert _verdict("gross_weight_kg", 118270.0, 118270.0000001) == MATCH
    assert _verdict("gross_weight_kg", 118270, 118271) == MISMATCH


# --------------------------------------------------------------------------
# UNCOMPARABLE: a blank is never a defect (CLAUDE.md rule 4)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("placeholder", ["???", "_______", "TBA", "TBC", "N/A", "", "   ", "____MT"])
@pytest.mark.parametrize("field", list(COMPARE_FIELDS))
def test_blank_on_either_side_is_uncomparable_never_mismatch(field, placeholder):
    good = _CLEAN[field]

    si_blank = compare_field(field, _value(field, placeholder), _value(field, good))
    assert si_blank.verdict == UNCOMPARABLE
    assert si_blank.reason == "si_blank"

    bl_blank = compare_field(field, _value(field, good), _value(field, placeholder))
    assert bl_blank.verdict == UNCOMPARABLE
    assert bl_blank.reason == "bl_blank"


def test_missing_field_reports_which_side_is_missing():
    absent = FieldValue(field="shipper")
    present = _value("shipper", "APRIL FINE PAPER TRADING")

    assert compare_field("shipper", absent, present).reason == "si_missing"
    assert compare_field("shipper", present, absent).reason == "bl_missing"
    assert compare_field("shipper", absent, absent).reason == "si_missing"


def test_unparseable_value_reports_which_side_is_unparseable():
    """Text is there, but it carries no usable fact — not a defect either."""
    good = _value("gross_weight_kg", "118,270 KG")
    prose = _value("gross_weight_kg", "AS PER PACKING LIST")
    assert compare_field("gross_weight_kg", prose, good).reason == "si_unparseable"
    assert compare_field("gross_weight_kg", good, prose).reason == "bl_unparseable"

    bare_locode = _value("port_of_loading", "(SGSIN)")
    port = _value("port_of_loading", "SINGAPORE (SGSIN)")
    assert compare_field("port_of_loading", bare_locode, port).reason == "si_unparseable"


def test_every_reason_is_from_the_published_vocabulary():
    si = _synthetic_docfields({**_CLEAN, "shipper": "???", "consignee": None}, "SI")
    bl = _synthetic_docfields({**_CLEAN, "port_of_loading": "TBA"}, "BL")
    for c in compare_documents(si, bl):
        if c.verdict == UNCOMPARABLE:
            assert c.reason in UNCOMPARABLE_REASONS
        else:
            assert c.reason is None


def test_blank_in_a_real_file_is_escalated_not_flagged():
    """email_516 leaves the SI gross weight as `N/A`; email_519 leaves two
    values empty after the label. Neither is a discrepancy."""
    si, bl = _pair("email_516", "txt")
    by_field = {c.field: c for c in compare_documents(si, bl)}
    assert by_field["gross_weight_kg"].si.raw.strip() == "N/A"
    assert by_field["gross_weight_kg"].verdict == UNCOMPARABLE
    assert by_field["gross_weight_kg"].reason == "si_blank"
    assert "gross_weight_kg" not in defect_fields(list(by_field.values()))

    si, bl = _pair("email_519", "txt")
    comparisons = compare_documents(si, bl)
    assert uncomparable_fields(comparisons) == ["container_count", "shipper"]
    assert all(c.reason == "si_blank"
               for c in comparisons if c.verdict == UNCOMPARABLE)


def test_unreadable_document_degrades_to_seven_escalations_not_seven_defects():
    """A BL we could not read must never look like a BL that is wrong."""
    si = _synthetic_docfields(_CLEAN, "SI")
    empty = DocFields(doc=ParsedDoc(path="<bl>", ext=".pdf", readable=False,
                                    unreadable_reason="no_text_layer"))
    comparisons = compare_documents(si, empty)

    assert defect_fields(comparisons) == []
    assert uncomparable_fields(comparisons) == sorted(COMPARE_FIELDS)
    assert {c.reason for c in comparisons} == {"bl_missing"}
    assert summarise(comparisons) == NO_MISMATCH_TEXT


# --------------------------------------------------------------------------
# summarise()
# --------------------------------------------------------------------------
def test_summarise_exact_wording_when_nothing_differs():
    si = _synthetic_docfields(_CLEAN, "SI")
    bl = _synthetic_docfields(_CLEAN, "BL")
    assert summarise(compare_documents(si, bl)) == "No mismatch detected."


def test_summarise_names_the_field_and_both_values():
    si = _synthetic_docfields({**_CLEAN, "container_count": "3 x 20'GP"}, "SI")
    bl = _synthetic_docfields({**_CLEAN, "container_count": "4 x 20'GP"}, "BL")
    assert summarise(compare_documents(si, bl)) == "container count - SI: 3 / BL: 4"


def test_summarise_lists_several_differences_in_document_order():
    si, bl = _pair("email_313", "pdf")
    line = summarise(compare_documents(si, bl))
    assert line == ("container count - SI: 5 / BL: 4; "
                    "gross weight kg - SI: 118270 / BL: 117770")


def test_summarise_shows_the_raw_party_name_a_reviewer_will_look_for():
    si = _synthetic_docfields({**_CLEAN, "shipper": "APRIL FINE PAPER TRADING"}, "SI")
    bl = _synthetic_docfields(
        {**_CLEAN, "shipper": "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"}, "BL")
    assert summarise(compare_documents(si, bl)) == (
        "shipper - SI: APRIL FINE PAPER TRADING"
        " / BL: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    )


# --------------------------------------------------------------------------
# Integration with the real extractor
# --------------------------------------------------------------------------
# The tests above drive `compare.py` through a fixture so that the module is
# testable on its own. These two run the pipeline's actual extractor instead,
# so a change to `extract/fields.py` that breaks the contract compare relies on
# — raw text preserved, `blank` set on a placeholder — fails here rather than
# silently in a scored run.
def _extracted_pair(email_id: str, ext: str) -> tuple[DocFields, DocFields]:
    from sdoc.extract.fields import extract_fields

    return (
        extract_fields(readers.read_attachment(DATA, f"attachments/{email_id}_SI.{ext}"), "SI"),
        extract_fields(readers.read_attachment(DATA, f"attachments/{email_id}_BL.{ext}"), "BL"),
    )


def test_integration_with_extractor_on_the_pdf_pair():
    pytest.importorskip("sdoc.extract.fields")
    si, bl = _extracted_pair("email_313", "pdf")
    comparisons = compare_documents(si, bl)

    assert defect_fields(comparisons) == ["container_count", "gross_weight_kg"]
    assert uncomparable_fields(comparisons) == []
    assert summarise(comparisons) == ("container count - SI: 5 / BL: 4; "
                                      "gross weight kg - SI: 118270 / BL: 117770")


def test_integration_with_extractor_keeps_blanks_out_of_the_defect_list():
    pytest.importorskip("sdoc.extract.fields")
    si, bl = _extracted_pair("email_519", "txt")
    comparisons = compare_documents(si, bl)

    assert defect_fields(comparisons) == []
    assert uncomparable_fields(comparisons) == ["container_count", "shipper"]
    assert {c.reason for c in comparisons if c.verdict == UNCOMPARABLE} == {"si_blank"}
