"""Tests for sdoc.doctype — deciding what a document IS, from its content.

These run against the real attachments in data/bundle. No answer key is read:
where a test needs to know that an attachment is "really" a Commercial Invoice
it establishes that from the file's own first line, which is what a human
opening the file would see.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import DATA, skip_without_bundle
from sdoc.doctype import (
    CONFIDENT,
    NON_PAIR_TYPES,
    DocTypeResult,
    classify_document,
    pair_problem,
    score_document,
)
from sdoc.readers import read_attachment
from sdoc.schema import (
    DOC_BL,
    DOC_COO,
    DOC_INVOICE,
    DOC_PACKING_LIST,
    DOC_SI,
    DOC_UNKNOWN,
    ParsedDoc,
)

ATTACHMENTS = DATA / "attachments"


# --------------------------------------------------------------------------
# Helpers — reading a real attachment once and reusing it.
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def read_doc():
    skip_without_bundle()
    cache: dict[str, ParsedDoc] = {}

    def _read(name: str) -> ParsedDoc:
        if name not in cache:
            doc = read_attachment(DATA, f"attachments/{name}")
            classify_document(doc)
            cache[name] = doc
        return cache[name]

    return _read


@pytest.fixture(scope="module")
def corpus():
    """Every attachment in the bundle, read and classified once."""
    skip_without_bundle()
    docs: dict[str, ParsedDoc] = {}
    for path in sorted(ATTACHMENTS.iterdir()):
        if path.name.startswith("~$"):        # Office lock file, not a document
            continue
        doc = read_attachment(DATA, f"attachments/{path.name}")
        classify_document(doc)
        docs[path.name] = doc
    return docs


# --------------------------------------------------------------------------
# 1. A .txt SI and a .txt BL are told apart
# --------------------------------------------------------------------------
def test_txt_pair_is_told_apart(read_doc):
    si = read_doc("email_001_SI.txt")
    bl = read_doc("email_001_BL.txt")

    assert si.doc_type == DOC_SI
    assert bl.doc_type == DOC_BL
    assert si.doc_type_confidence >= CONFIDENT
    assert bl.doc_type_confidence >= CONFIDENT
    assert pair_problem(si, bl) is None


def test_txt_signals_are_recorded(read_doc):
    """The evidence a reviewer sees must name the heading it read."""
    si_result = score_document(read_doc("email_001_SI.txt").text)
    bl_result = score_document(read_doc("email_001_BL.txt").text)

    assert "title:SHIPPING INSTRUCTION" in si_result.signals
    assert "title:BILL OF LADING" in bl_result.signals
    # The BL carries "B/L No."; the SI carries only a booking reference.
    assert "label:B/L No." in bl_result.signals
    assert "label:B/L No." not in si_result.signals


# --------------------------------------------------------------------------
# 2. THE TRAP: the PDF SI is titled "BILL OF LADING INSTRUCTION"
# --------------------------------------------------------------------------
def test_pdf_si_titled_bill_of_lading_instruction_is_an_si(read_doc):
    si = read_doc("email_059_SI.pdf")
    bl = read_doc("email_059_BL.pdf")

    assert si.text.splitlines()[0].strip() == "BILL OF LADING INSTRUCTION"
    assert si.doc_type == DOC_SI, "an instruction to produce a BL is not a BL"
    assert bl.doc_type == DOC_BL
    assert pair_problem(si, bl) is None


def test_pdf_si_keeps_si_despite_a_preprinted_bl_number(read_doc):
    """The PDF SI template prints "B/L NUMBER:" too, so that signal must lose."""
    result = score_document(read_doc("email_059_SI.pdf").text)

    assert "label:B/L No." in result.signals        # the BL signal really fires
    assert result.doc_type == DOC_SI                # and is still outvoted
    assert result.scores[DOC_SI] > result.scores[DOC_BL]
    assert result.confidence >= CONFIDENT


@pytest.mark.parametrize(
    "email", ["059", "160", "208", "273", "313", "351", "407", "411", "434", "499"]
)
def test_every_readable_pdf_pair_resolves(read_doc, email):
    """All ten readable .pdf pairs use the trap title; none may flip."""
    assert read_doc(f"email_{email}_SI.pdf").doc_type == DOC_SI
    assert read_doc(f"email_{email}_BL.pdf").doc_type == DOC_BL


def test_instruction_wins_even_when_the_title_is_split_over_two_lines():
    """Synthetic layout: the heading and the word INSTRUCTION on separate lines.

    An SI is an instruction to *produce* a BL, so INSTRUCTION anywhere in the
    header block decides the document — not just when it sits in the same
    phrase as "BILL OF LADING".
    """
    text = (
        "BILL OF LADING\n"
        "INSTRUCTION TO CARRIER\n"
        "Shipper: APRIL FINE PAPER TRADING\n"
        "Booking Ref: MSDUL0942518196\n"
    )
    result = score_document(text)
    assert result.doc_type == DOC_SI
    assert any("INSTRUCTION" in s for s in result.signals)


def test_a_bill_of_lading_mentioning_instructions_in_its_body_stays_a_bl():
    """Only the header block decides; prose further down must not flip it."""
    text = (
        "BILL OF LADING (DRAFT)\n"
        "Shipper: APRIL FINE PAPER TRADING\n"
        "Consignee: KPP-ANTALIS (SINGAPORE) PTE. LTD.\n"
        "Port of Loading: SINGAPORE\n"
        "Port of Discharge: KARACHI, PAKISTAN\n"
        "B/L No.: MEDUUD104332\n"
        "Remarks: issued per the shipper's instruction of 12-JAN-2026.\n"
    )
    assert score_document(text).doc_type == DOC_BL


# --------------------------------------------------------------------------
# 3. The xlsx + docx pair
# --------------------------------------------------------------------------
def test_xlsx_si_and_docx_bl_pair(read_doc):
    si = read_doc("email_055_SI.xlsx")
    bl = read_doc("email_055_BL.docx")

    assert si.doc_type == DOC_SI, "the .xlsx SI heading cell reads 'BL INSTRUCTION'"
    assert bl.doc_type == DOC_BL
    assert pair_problem(si, bl) is None

    si_result = score_document(si.text)
    # The title is not on row 1 of the sheet — row 1 is the exporter's name.
    assert "title:BL INSTRUCTION" in si_result.signals


def test_xlsx_bl_says_bill_of_lading_in_the_same_cell(read_doc):
    """email_005 is an xlsx+xlsx pair: one word separates the two templates."""
    si = read_doc("email_005_SI.xlsx")
    bl = read_doc("email_005_BL.xlsx")
    assert (si.doc_type, bl.doc_type) == (DOC_SI, DOC_BL)
    assert pair_problem(si, bl) is None


def test_docx_chinese_labels_do_not_disturb_classification(read_doc):
    """The .docx BL labels carry CJK ("B/L NO.(提单号)"); basic() strips them."""
    bl = read_doc("email_097_BL.docx")
    result = score_document(bl.text)
    assert result.doc_type == DOC_BL
    assert "label:B/L No." in result.signals


# --------------------------------------------------------------------------
# 4. The five wrong_doc_type edge cases
#
# Found by reading the attachments, not by consulting any answer key: the file
# says what it is on its first line, and the classifier must reach the same
# conclusion from the whole document.
# --------------------------------------------------------------------------
WRONG_DOC_EMAILS = ("email_501", "email_502", "email_503", "email_504", "email_505")

_TITLE_TO_TYPE = {
    "COMMERCIAL INVOICE": DOC_INVOICE,
    "PACKING LIST": DOC_PACKING_LIST,
    "CERTIFICATE OF ORIGIN": DOC_COO,
}


@pytest.mark.parametrize("email_id", WRONG_DOC_EMAILS)
def test_misfiled_attachment_is_classified_by_content(read_doc, email_id):
    bl_slot = read_doc(f"{email_id}_BL.txt")

    # What a human opening the file would see on line 1.
    expected = _TITLE_TO_TYPE[bl_slot.text.splitlines()[0].strip()]

    assert bl_slot.role_hint == "BL", "the filename claims this is the draft BL"
    assert bl_slot.doc_type == expected
    assert bl_slot.doc_type_confidence >= CONFIDENT
    assert bl_slot.doc_type in NON_PAIR_TYPES


@pytest.mark.parametrize("email_id", WRONG_DOC_EMAILS)
def test_misfiled_attachment_makes_the_pair_unusable(read_doc, email_id):
    si = read_doc(f"{email_id}_SI.txt")
    bl = read_doc(f"{email_id}_BL.txt")

    assert si.doc_type == DOC_SI, "the SI half of these emails is genuine"
    assert pair_problem(si, bl) == "wrong_doc_type"


def test_invoice_disclaimer_does_not_flip_it_to_an_si(read_doc):
    """email_501 literally contains the words "SHIPPING INSTRUCTION".

    It appears in a footer reading "NOT A SHIPPING INSTRUCTION". A substring
    test over the whole document would call this an SI; the title block and the
    invoice's own vocabulary must win.
    """
    doc = read_doc("email_501_BL.txt")
    assert "SHIPPING INSTRUCTION" in doc.text.upper()

    result = score_document(doc.text)
    assert result.doc_type == DOC_INVOICE
    assert result.scores[DOC_INVOICE] > result.scores[DOC_SI]
    assert "title:COMMERCIAL INVOICE" in result.signals


def test_packing_list_recognised_without_its_title():
    """A packing list whose heading was lost still reads as a packing list.

    Carton numbers, net weight, dimensions and the complete absence of port or
    vessel details are together enough — that is the point of scoring signals
    rather than switching on the title alone.
    """
    text = (
        "Shipper: ASIA PACIFIC PAPERBOARD TRADING PTE LTD\n"
        "Consignee: ROXCEL TRADING GMBH\n"
        "Carton No.      Net Wt (kg)     Gross Wt (kg)     Dimensions\n"
        "CTN-001          571             635             120x100x110\n"
    )
    assert score_document(text).doc_type == DOC_PACKING_LIST


def test_certificate_of_origin_recognised_without_its_title():
    text = (
        "Exporter: APRIL FAR EAST (M) SDN BHD\n"
        "Consignee: INTERNATIONAL FOREST PRODUCTS LLC\n"
        "Country of Origin: MALAYSIA / INDONESIA / CHINA\n"
        "Certificate No.: COO-50388\n"
        "Issuing Authority: MINISTRY OF INTERNATIONAL TRADE\n"
    )
    assert score_document(text).doc_type == DOC_COO


def test_shipper_principal_or_seller_is_not_an_invoice_seller_label(read_doc):
    """"Shipper (Principal or Seller)" contains the invoice's "Seller" label.

    It is a shipper label, so the invoice signal must stay silent — which is
    why that signal is anchored to the start of a line.
    """
    si = read_doc("email_013_SI.txt")
    assert "Principal or Seller" in si.text
    result = score_document(si.text)
    assert "label:Seller" not in result.signals
    assert result.doc_type == DOC_SI


# --------------------------------------------------------------------------
# 5. Unreadable documents
# --------------------------------------------------------------------------
def test_unreadable_parseddoc_returns_unknown_without_raising():
    doc = ParsedDoc(path="attachments/scan.pdf", ext=".pdf", role_hint="BL")
    doc.readable = False
    doc.unreadable_reason = "no_text_layer"

    result = classify_document(doc)

    assert isinstance(result, DocTypeResult)
    assert result.doc_type == DOC_UNKNOWN
    assert result.confidence == 0.0
    assert doc.doc_type == DOC_UNKNOWN
    assert doc.doc_type_confidence == 0.0
    assert any("no_text_layer" in n for n in doc.notes)


def test_real_image_only_pdf_is_unknown_not_misclassified(read_doc):
    """email_513_SI.pdf is a scan: no text layer, so no type can be read."""
    doc = read_doc("email_513_SI.pdf")
    assert doc.readable is False
    assert doc.doc_type == DOC_UNKNOWN
    assert doc.doc_type_confidence == 0.0


def test_empty_and_garbage_text_are_unknown():
    for text in ("", "   \n\n\t", "Dear team, please see attached. Regards."):
        result = score_document(text)
        assert result.doc_type == DOC_UNKNOWN
        assert result.confidence == 0.0


# --------------------------------------------------------------------------
# pair_problem
# --------------------------------------------------------------------------
def test_pair_problem_never_complains_about_a_missing_half(read_doc):
    """0 or 1 documents is `missing_attachment`, decided from the email."""
    si = read_doc("email_001_SI.txt")
    assert pair_problem(None, None) is None
    assert pair_problem(si, None) is None
    assert pair_problem(None, si) is None


def test_pair_problem_flags_two_of_the_same_kind(read_doc):
    si_a = read_doc("email_001_SI.txt")
    si_b = read_doc("email_004_SI.txt")
    bl_a = read_doc("email_001_BL.txt")
    bl_b = read_doc("email_004_BL.txt")

    assert pair_problem(si_a, si_b) == "wrong_doc_type"
    assert pair_problem(bl_a, bl_b) == "wrong_doc_type"


def test_pair_problem_tolerates_a_swapped_pair(read_doc):
    """The set is still {SI, BL}; content beats the filename."""
    si = read_doc("email_001_SI.txt")
    bl = read_doc("email_001_BL.txt")
    assert pair_problem(bl, si) is None


def test_pair_problem_is_quiet_about_an_unrecognised_layout(read_doc):
    """Readable but unfamiliar is a reading problem, not a wrong document."""
    unknown = ParsedDoc(path="attachments/email_999_BL.txt", ext=".txt",
                        role_hint="BL")
    unknown.text = "Dear team,\nplease find the paperwork attached.\n"
    classify_document(unknown)
    assert unknown.doc_type == DOC_UNKNOWN

    assert pair_problem(read_doc("email_001_SI.txt"), unknown) is None


def test_pair_problem_is_quiet_about_an_unreadable_half(read_doc):
    scan = ParsedDoc(path="attachments/email_513_BL.pdf", ext=".pdf",
                     role_hint="BL")
    scan.readable = False
    scan.unreadable_reason = "no_text_layer"
    assert pair_problem(read_doc("email_001_SI.txt"), scan) is None


def test_pair_problem_does_not_raise_on_a_broken_document():
    """It runs on the escalation path; an exception there loses the case."""
    broken = ParsedDoc(path="x", ext=".txt")
    broken.text = None                                  # type: ignore[assignment]
    assert pair_problem(broken, broken) is None


# --------------------------------------------------------------------------
# classify_document contract
# --------------------------------------------------------------------------
def test_classify_document_writes_back_to_the_doc():
    doc = ParsedDoc(path="attachments/x_SI.txt", ext=".txt", role_hint="SI")
    doc.text = "SHIPPING INSTRUCTION\nBooking Ref: MSDUL0942518196\n"

    result = classify_document(doc)

    assert doc.doc_type == result.doc_type == DOC_SI
    assert doc.doc_type_confidence == result.confidence > 0
    assert doc.notes and "doc type:" in doc.notes[-1]


def test_classify_document_is_idempotent():
    doc = ParsedDoc(path="attachments/x_SI.txt", ext=".txt", role_hint="SI")
    doc.text = "SHIPPING INSTRUCTION\nBooking Ref: MSDUL0942518196\n"

    first = classify_document(doc)
    second = classify_document(doc)

    assert first.doc_type == second.doc_type
    assert len(doc.notes) == 1, "re-classifying must not pile up duplicate notes"


def test_score_document_does_not_mutate_anything(read_doc):
    doc = read_doc("email_001_SI.txt")
    before = (doc.doc_type, doc.doc_type_confidence, list(doc.notes))
    score_document(doc.text)
    assert (doc.doc_type, doc.doc_type_confidence, list(doc.notes)) == before


def test_confidence_is_derived_from_the_margin():
    clean = score_document("SHIPPING INSTRUCTION\nBooking Ref: PSGSE4981829\n")
    contested = score_document(
        "BILL OF LADING INSTRUCTION\nB/L NUMBER: OOLU3584143842\n"
    )
    assert clean.confidence > contested.confidence > CONFIDENT


# --------------------------------------------------------------------------
# Whole-corpus regression: nothing in the bundle is confidently wrong
# --------------------------------------------------------------------------
def test_every_readable_attachment_is_classified(corpus):
    unclassified = [
        name for name, doc in corpus.items()
        if doc.readable and doc.doc_type == DOC_UNKNOWN
    ]
    assert unclassified == []


def test_unknown_is_reserved_for_documents_we_could_not_read(corpus):
    unknown = {name for name, doc in corpus.items() if doc.doc_type == DOC_UNKNOWN}
    unreadable = {name for name, doc in corpus.items() if not doc.readable}
    assert unknown == unreadable


def test_only_the_five_misfiled_attachments_are_non_pair_documents(corpus):
    """Exactly five attachments in the bundle are not an SI or a BL.

    Establishing the expectation from the files themselves, so this test does
    not depend on any label: a document whose first line names an invoice, a
    packing list or a certificate of origin is one, and nothing else may be.
    """
    by_first_line = {
        name for name, doc in corpus.items()
        if doc.readable and doc.text.splitlines()[0].strip() in _TITLE_TO_TYPE
    }
    by_classifier = {
        name for name, doc in corpus.items() if doc.doc_type in NON_PAIR_TYPES
    }
    assert by_classifier == by_first_line
    assert len(by_classifier) == 5


def test_filename_hint_and_content_agree_except_for_the_misfiled_five(corpus):
    """The filename is a hint; here it should be right 245 times out of 250."""
    expected = {"SI": DOC_SI, "BL": DOC_BL}
    disagreements = {
        name
        for name, doc in corpus.items()
        if doc.readable and doc.doc_type != expected.get(doc.role_hint)
    }
    assert disagreements == {f"{e}_BL.txt" for e in WRONG_DOC_EMAILS}


def test_every_readable_document_is_classified_confidently(corpus):
    """A low-confidence call on a template we have seen means a weak rule."""
    weak = {
        name: doc.doc_type_confidence
        for name, doc in corpus.items()
        if doc.readable and doc.doc_type_confidence < CONFIDENT
    }
    assert weak == {}


def test_pair_problem_over_the_whole_inbox(corpus):
    """Only emails 501-505 may be reported as carrying the wrong document."""
    flagged = []
    for path in sorted((DATA / "inbox").glob("*.json")):
        email = json.loads(path.read_text(encoding="utf-8"))
        si = bl = None
        for rel in email.get("attachments") or []:
            doc = corpus.get(Path(rel).name)
            if doc is None:
                continue
            if doc.role_hint == "SI":
                si = doc
            elif doc.role_hint == "BL":
                bl = doc
        if pair_problem(si, bl) == "wrong_doc_type":
            flagged.append(email["email_id"])

    assert flagged == list(WRONG_DOC_EMAILS)
