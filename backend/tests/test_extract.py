"""Tests for extract/fields.py — chunks -> the seven fields, with evidence.

Everything here runs against the real bundle in `data/bundle/`, one file per
format, plus the specific traps written down in `docs/DATA_NOTES.md`. The
synthetic documents are only used where the bundle does not (yet) contain a
layout we must survive — a container table whose heading row reconstructs as a
label/value pair. They describe a document *shape*, never a single email.
"""
from __future__ import annotations

import pytest
from conftest import DATA, requires_bundle, skip_without_bundle

from sdoc import labels
from sdoc.extract.fields import (
    SNIPPET_MAX,
    extract_fields,
    field_candidates,
)
from sdoc.readers import read_attachment, role_hint
from sdoc.schema import COMPARE_FIELDS, Chunk, ParsedDoc

ATTACHMENTS = DATA / "attachments"


def read_fields(rel: str, role: str):
    """Read one real attachment and extract its fields."""
    skip_without_bundle()
    doc = read_attachment(DATA, rel)
    return doc, extract_fields(doc, role)


def fake_doc(*chunks: Chunk) -> ParsedDoc:
    """A ParsedDoc standing in for a layout, not for a particular email."""
    return ParsedDoc(path="synthetic", ext=".pdf", readable=True,
                     text="synthetic", chunks=list(chunks))


# ==========================================================================
# 1. .txt pair — the plainest format
# ==========================================================================
def test_txt_pair_extracts_all_seven_fields():
    _, si = read_fields("attachments/email_004_SI.txt", "SI")
    _, bl = read_fields("attachments/email_004_BL.txt", "BL")

    assert set(si.fields) == set(COMPARE_FIELDS)
    assert all(si.get(f).present for f in COMPARE_FIELDS)
    assert all(bl.get(f).present for f in COMPARE_FIELDS)

    # The SI and the BL label these differently ("Total Containers" vs
    # "Container Count", "Gross Wt (kgs)" vs "Gross Weight (KG)") — both must
    # land on the same field with the same value.
    assert si.get("shipper").raw == "APRIL FAR EAST (M) SDN BHD"
    assert si.get("consignee").raw == "EAST BRIGHT FZ-LLC"
    assert si.get("notify_party").raw == "EAST BRIGHT FZ-LLC"
    assert si.get("port_of_loading").raw == "NANTONG, CHINA (CNNTG)"
    assert si.get("port_of_discharge").raw == "KARACHI, PAKISTAN (PKKHI)"
    assert si.get("container_count").number == 6
    assert si.get("gross_weight_kg").number == 131058.0

    assert bl.get("shipper").raw == "APRIL FAR EAST (M) SDN BHD"
    assert bl.get("consignee").raw == "UAB NOVAKOPA"
    assert bl.get("notify_party").raw == "UAB NOVAKOPA"
    assert bl.get("container_count").number == 6
    assert bl.get("gross_weight_kg").number == 131058.0

    # the fields that agree, agree after normalisation...
    for name in ("shipper", "port_of_loading", "port_of_discharge"):
        assert si.get(name).normalised == bl.get(name).normalised
    # ...and the planted party swap survives normalisation as a real difference
    assert si.get("consignee").normalised != bl.get("consignee").normalised


def test_txt_value_stops_at_the_entity_name():
    """Addresses are deliberately not part of the compared value (§4).

    In the .txt SI the address is an indented continuation line that the reader
    appends to the value; keeping it would let an unchanged address block mask
    a changed party name.
    """
    doc, si = read_fields("attachments/email_004_SI.txt", "SI")

    shipper_chunk = next(c for c in doc.chunks if labels.resolve(c.label) == "shipper")
    assert "KUALA LUMPUR" in shipper_chunk.value          # the reader kept it
    assert si.get("shipper").raw == "APRIL FAR EAST (M) SDN BHD"
    assert "TOWER 2" not in si.get("shipper").raw         # the extractor dropped it


# ==========================================================================
# 2. .pdf pair — the two-column form (DATA_NOTES §3)
# ==========================================================================
def test_pdf_pair_extracts_all_seven_fields():
    _, si = read_fields("attachments/email_313_SI.pdf", "SI")
    _, bl = read_fields("attachments/email_313_BL.pdf", "BL")

    assert all(si.get(f).present for f in COMPARE_FIELDS)
    assert all(bl.get(f).present for f in COMPARE_FIELDS)

    assert si.get("shipper").raw == "APRIL FINE PAPER TRADING"
    assert si.get("consignee").raw == "KPP-ANTALIS (SINGAPORE) PTE. LTD."
    assert si.get("notify_party").raw == "KPP-ANTALIS (SINGAPORE) PTE. LTD."
    assert si.get("port_of_loading").raw == "RUGAO/NANTONG/SHANGHAI, CHINA"
    assert si.get("port_of_discharge").raw == "HOCHIMINH CITY, VIETNAM"
    assert si.get("container_count").number == 5
    assert si.get("gross_weight_kg").number == 118270.0

    assert bl.get("container_count").number == 4          # the planted defect
    assert bl.get("gross_weight_kg").number == 117770.0


def test_pdf_fields_are_not_address_lines():
    """The line-oriented reading of this form yields confident nonsense.

    `pdftotext -layout` puts "77 ROBINSON ROAD, #21-01" beside "To the Order of"
    and "8 TEMASEK BOULEVARD" beside "Load Port". Neither may appear as a value.
    """
    _, si = read_fields("attachments/email_313_SI.pdf", "SI")

    assert "ROBINSON" not in si.get("consignee").raw
    assert "TEMASEK" not in si.get("port_of_loading").raw
    assert "SUNTEC" not in si.get("port_of_discharge").raw


def test_pdf_gross_weight_is_the_total_not_a_container_row():
    """§3a — every container row carries a weight; only the total is the field."""
    _, si = read_fields("attachments/email_313_SI.pdf", "SI")
    weight = si.get("gross_weight_kg")

    assert weight.number == 118270.0
    assert weight.number != 23654.0                      # a per-container row
    assert "TOTAL" in weight.evidence.label.upper()

    # and on the BL, where the PDF font mangled the same label
    _, bl = read_fields("attachments/email_313_BL.pdf", "BL")
    assert bl.get("gross_weight_kg").number == 117770.0
    assert bl.get("gross_weight_kg").number != 29442.0
    assert "TOTAL" in bl.get("gross_weight_kg").evidence.label.upper()


def test_pdf_container_count_is_not_the_container_no_column():
    """§3a — "CONTAINER NO." is the id column of the table, not a count."""
    assert labels.resolve("CONTAINER NO.") is None

    doc, si = read_fields("attachments/email_313_SI.pdf", "SI")
    count = si.get("container_count")

    assert count.number == 5
    assert count.evidence.label.upper().startswith("TOTAL CONTAINERS")
    assert "DESCRIPTION" not in count.raw.upper()

    # the header row exists in the document and produced no candidate at all
    assert any("CONTAINER NO" in c.label.upper() for c in doc.chunks)
    header_locators = {c.locator for c in doc.chunks
                       if "CONTAINER NO" in c.label.upper()}
    chosen = {c.chunk.locator for c in field_candidates(doc)["container_count"]}
    assert not (chosen & header_locators)


def test_table_header_row_loses_to_the_total_line():
    """A heading row that reconstructs as label/value must not win.

    Guards the value side of §3a for any column split where "GROSS WEIGHT (KG)"
    lands in the label column instead of the value column.
    """
    doc = fake_doc(
        Chunk(label="GROSS WEIGHT (KG)", value="DESCRIPTION GROSS WEIGHT (KG)",
              locator="p1 r18", order=0),
        Chunk(label="Gross Weight (KG)", value="23,654", locator="p1 r19", order=1),
        Chunk(label="TOTAL GROSS WEIGHT", value="118,270 KG",
              locator="p1 r25", order=2),
    )
    cands = field_candidates(doc)["gross_weight_kg"]
    assert len(cands) == 3

    winner = next(c for c in cands if c.won)
    assert winner.locator == "p1 r25"
    assert winner.number == 118270.0

    header = next(c for c in cands if c.locator == "p1 r18")
    assert header.score < 0
    assert not header.won
    assert any("table header" in r for r in header.reasons)

    # the per-container row parses fine, and still loses to the TOTAL line
    row = next(c for c in cands if c.locator == "p1 r19")
    assert row.parsed and not row.won

    fields = extract_fields(doc, "SI")
    assert fields.get("gross_weight_kg").number == 118270.0


def test_document_order_breaks_a_tie():
    """Two equally good candidates: the form's header block comes first."""
    doc = fake_doc(
        Chunk(label="Port of Loading (POL)", value="SINGAPORE",
              locator="line 7", order=0),
        Chunk(label="Load Port", value="NANTONG, CHINA", locator="line 20", order=1),
    )
    cands = field_candidates(doc)["port_of_loading"]
    assert [c.score for c in cands] == [cands[0].score, cands[0].score]
    assert cands[0].locator == "line 7"
    assert extract_fields(doc, "BL").get("port_of_loading").raw == "SINGAPORE"


# ==========================================================================
# 3. .xlsx + .docx pair — different types for the same number
# ==========================================================================
def test_xlsx_docx_pair_extracts_all_seven_fields():
    _, si = read_fields("attachments/email_097_SI.xlsx", "SI")
    _, bl = read_fields("attachments/email_097_BL.docx", "BL")

    assert all(si.get(f).present for f in COMPARE_FIELDS)
    assert all(bl.get(f).present for f in COMPARE_FIELDS)

    # .xlsx packs "NAME | ADDRESS" into one cell, .docx stacks them as lines;
    # both must reduce to the same entity name.
    assert si.get("shipper").raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert bl.get("shipper").raw == "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert si.get("shipper").normalised == bl.get("shipper").normalised
    assert "DUBAI" not in si.get("shipper").raw

    # §2a — "Notify Party/Intermediate Consignee" contains the word Consignee.
    assert bl.get("consignee").raw == "ROXCEL TRADING GMBH"
    assert bl.get("notify_party").raw == "NAGAPPA EXPORTS"


def test_xlsx_int_and_docx_thousands_separator_normalise_the_same():
    """The .xlsx stores the weight as a number, the .docx as "215,950".

    Same fact, different typing: the separator must not create a difference.
    """
    _, si = read_fields("attachments/email_097_SI.xlsx", "SI")
    _, bl = read_fields("attachments/email_097_BL.docx", "BL")

    assert si.get("gross_weight_kg").raw == "216950"      # xlsx, stored numeric
    assert si.get("gross_weight_kg").number == 216950.0
    assert si.get("gross_weight_kg").normalised == "216950"

    assert bl.get("gross_weight_kg").raw == "215,950"     # docx, formatted text
    assert bl.get("gross_weight_kg").number == 215950.0
    assert bl.get("gross_weight_kg").normalised == "215950"

    # and the same number written both ways compares equal
    as_number = extract_fields(
        fake_doc(Chunk(label="GROSS WEIGHT", value=216950, locator="S.I.!A10")),
        "SI").get("gross_weight_kg")
    as_text = extract_fields(
        fake_doc(Chunk(label="GROSS WEIGHT (KGS)", value="216,950 KG",
                       locator="table 1 row 7")),
        "BL").get("gross_weight_kg")
    assert as_number.number == as_text.number == 216950.0
    assert as_number.normalised == as_text.normalised


def test_container_count_takes_the_quantity_not_the_box_size():
    """"10 x 40'HC" is ten containers, not forty."""
    _, si = read_fields("attachments/email_097_SI.xlsx", "SI")
    _, bl = read_fields("attachments/email_097_BL.docx", "BL")

    assert si.get("container_count").number == 10
    assert bl.get("container_count").number == 11         # the planted defect


# ==========================================================================
# 4. Blank values — an escalation, never a discrepancy (§5)
# ==========================================================================
# Found by reading the attachment text: a label is present and its value is a
# placeholder. Never by consulting any answer key.
BLANK_CASES = [
    ("attachments/email_516_SI.txt", {"gross_weight_kg"}),              # "N/A"
    ("attachments/email_517_SI.txt", {"port_of_loading",
                                      "port_of_discharge"}),            # "____MT", "TBA"
    ("attachments/email_518_SI.txt", {"port_of_discharge",
                                      "gross_weight_kg"}),              # "N/A", "____MT"
    ("attachments/email_519_SI.txt", {"shipper", "container_count"}),    # empty
    ("attachments/email_520_SI.txt", {"consignee"}),                     # empty
]


@pytest.mark.parametrize("rel,expected_blank", BLANK_CASES)
def test_blank_field_si(rel, expected_blank):
    _, si = read_fields(rel, "SI")

    for name in expected_blank:
        fv = si.get(name)
        assert fv.blank is True, f"{rel}:{name} should be blank"
        assert fv.present is False, f"{rel}:{name} must not be usable"
        assert fv.normalised is None and fv.number is None
        # the label *was* found, so the reviewer still gets evidence
        assert fv.raw is not None
        assert fv.evidence is not None
        assert fv.evidence.doc_role == "SI"

    # every other field still extracts normally
    for name in COMPARE_FIELDS:
        if name in expected_blank:
            continue
        fv = si.get(name)
        assert fv.present is True, f"{rel}:{name} should still extract"
        assert fv.blank is False
        assert fv.normalised


def test_blank_is_kept_rather_than_replaced_by_a_worse_candidate():
    """A blank beats nothing, but loses to any real value for the same field."""
    only_blank = field_candidates(
        fake_doc(Chunk(label="GROSS WEIGHT", value="???", locator="line 9"))
    )["gross_weight_kg"]
    assert len(only_blank) == 1 and only_blank[0].won and only_blank[0].blank

    both = extract_fields(
        fake_doc(
            Chunk(label="Gross Weight (KG)", value="???", locator="line 9", order=0),
            Chunk(label="Total Gross Weight", value="131,058 KG",
                  locator="line 10", order=1),
        ),
        "SI",
    ).get("gross_weight_kg")
    assert both.present and both.number == 131058.0 and not both.blank


def test_net_weight_never_fills_the_gross_weight_slot():
    """Every SI in the set carries "NET WEIGHT: _______ MTS" under the gross
    weight; reading it would turn a good document into a blank one."""
    _, si = read_fields("attachments/email_517_SI.txt", "SI")
    assert si.get("gross_weight_kg").number == 340770.0
    assert si.get("gross_weight_kg").present


# ==========================================================================
# 5. Absent vs blank, and unreadable documents
# ==========================================================================
def test_unreadable_pdf_returns_all_absent_without_raising():
    doc, fields = read_fields("attachments/email_512_SI.pdf", "SI")
    assert doc.readable is False                  # image-only scan

    assert set(fields.fields) == set(COMPARE_FIELDS)
    for name in COMPARE_FIELDS:
        fv = fields.get(name)
        assert fv.present is False
        assert fv.blank is False                  # absent is NOT blank
        assert fv.raw is None
        assert fv.evidence is None
    assert field_candidates(doc) == {name: [] for name in COMPARE_FIELDS}


def test_wrong_document_type_leaves_fields_absent_not_blank():
    """A Commercial Invoice sent as the "BL" simply has no ports to find."""
    _, fields = read_fields("attachments/email_501_BL.txt", "BL")
    for name in ("port_of_loading", "port_of_discharge", "container_count",
                 "gross_weight_kg"):
        fv = fields.get(name)
        assert fv.present is False and fv.blank is False and fv.raw is None


def test_unparseable_value_is_not_present_and_not_blank():
    """We read something, but it is not a count. That is a review case, not a
    mismatch — but it must not look like a missing label either."""
    fields = extract_fields(
        fake_doc(Chunk(label="Total Containers", value="SEE ATTACHED MANIFEST",
                       locator="line 11")),
        "SI",
    )
    fv = fields.get("container_count")
    assert fv.present is False
    assert fv.blank is False
    assert fv.raw == "SEE ATTACHED MANIFEST"
    assert fv.evidence is not None


# ==========================================================================
# 6. Evidence invariants, over the whole bundle
# ==========================================================================
@requires_bundle
def test_every_present_field_carries_evidence_across_the_bundle():
    checked = 0
    for path in sorted(ATTACHMENTS.iterdir()):
        rel = f"attachments/{path.name}"
        role = role_hint(rel)
        doc = read_attachment(DATA, rel)
        fields = extract_fields(doc, role)

        assert set(fields.fields) == set(COMPARE_FIELDS), rel
        for name in COMPARE_FIELDS:
            fv = fields.get(name)
            assert fv.field == name
            if fv.present or fv.blank:
                assert fv.evidence is not None, f"{rel}:{name}"
                assert fv.evidence.doc_role == role
                assert fv.evidence.locator
                assert fv.evidence.snippet
                assert len(fv.evidence.snippet) <= SNIPPET_MAX
                assert "\n" not in fv.evidence.snippet
                assert fv.extractor == "rule"
                checked += 1
            else:
                assert fv.evidence is None, f"{rel}:{name}"
            if fv.present:
                assert fv.normalised
                assert not fv.blank
    assert checked > 1000       # the bundle is 250 attachments x 7 fields


def test_snippet_shows_the_label_and_the_value():
    _, si = read_fields("attachments/email_004_SI.txt", "SI")
    snippet = si.get("consignee").evidence.snippet
    assert snippet.startswith("Consignee (Non-Negotiable): EAST BRIGHT FZ-LLC")
    assert si.get("consignee").evidence.locator == "line 6"


def test_long_value_is_trimmed_for_the_reviewer():
    fields = extract_fields(
        fake_doc(Chunk(label="Shipper/Exporter",
                       value="APRIL FINE PAPER TRADING\n" + "ADDRESS LINE; " * 30,
                       locator="p1 r3")),
        "SI",
    )
    snippet = fields.get("shipper").evidence.snippet
    assert len(snippet) == SNIPPET_MAX
    assert snippet.endswith("...")
    assert snippet.startswith("Shipper/Exporter: APRIL FINE PAPER TRADING")


# ==========================================================================
# 7. The debug view
# ==========================================================================
@requires_bundle
def test_field_candidates_explains_every_candidate():
    doc = read_attachment(DATA, "attachments/email_313_SI.pdf")
    cands = field_candidates(doc)

    assert set(cands) == set(COMPARE_FIELDS)
    for name, lst in cands.items():
        assert lst, name
        assert sum(1 for c in lst if c.won) == 1
        for c in lst:
            assert c.field == name
            assert c.reasons
            assert isinstance(c.score, float)
        # best first
        assert lst == sorted(lst, key=lambda c: (-c.score, c.order))
