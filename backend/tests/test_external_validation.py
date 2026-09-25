"""Behaviour found by testing Sentinel on documents from outside the generator.

docs/EXTERNAL_VALIDATION.md (25 Sep 2026) records the run: real carrier forms,
real bills of lading, real bill-of-lading records and real email. Each fix
below was a confirmed failure in that run, reproduced by a second checker, and
the graded data never contains any of these shapes: every change was checked
to leave all six local datasets and the adversarial harness identical, field
by field. So these are the only tests that hold them in place.

Every fix was then reviewed old-against-new over hundreds of thousands to
millions of realistic inputs, in three rounds, with a second agent confirming
each regression found. Whatever broke another real shape was withdrawn: every
weight change (pounds, European notation, tonne codes), summing mixed
container equipment, a container-count cap, general REF/PARTICULARS and
UNLOADING rules, and "Destination"/"Quantity" as ignored labels. What is left
survived all three rounds. The shapes that exposed the withdrawn parts are
pinned below as "read as before" cases, so they cannot regress.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sdoc import labels, normalize  # noqa: E402
from sdoc.readers import pdf as pdf_reader  # noqa: E402


# --------------------------------------------------------------------------
# Weights: unchanged (every attempted weight fix was withdrawn after review)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw, kg", [
    ("21,577 KG", 21577.0), ("235,550 KG", 235550.0), ("100445", 100445.0),
    ("216 950 kgs", 216950.0), ("138 MT", 138000.0), ("12.5 MT", 12500.0),
    ("24.0010 MT", 24001.0), ("44012.35", 44012.35), ("8,010.000 KGS", 8010.0),
    ("3,700KGS", 3700.0), ("24001 KGM", 24001.0),
    # Every line that names a kilogram or tonne unit is read exactly as before,
    # including the dual-unit lines two wider versions got wrong.
    ("KGS 12,000.000 LBS 26,455.000", 12000.0), ("KGS: 12,000 LBS: 26,455", 12000.0),
    ("KGS/LBS 12,000/26,455", 12000.0), ("8,010 KGS (17,659 LBS)", 8010.0),
    ("24.500 MT", 24500.0), ("118.270 MT", 118270.0), ("0.500 MT", 500.0), ("MT 24.500", 24500.0),
    ("24.500/23.900 MT", 24500.0), ("24.500 M.TONS 45.000 CBM", 24500.0),
    ("635.400 KGS", 635.4), ("21, 577 KG", 21577.0), ("21,5 77 KGS", 21577.0),
    ("121,577.000 204.000", 121577.0), ("21,577 T.G.W.", 21577.0),
    ("12,000 / 26,455 LBS", 12000.0), ("12,000 (26,455 LBS)", 12000.0),
])
def test_weights_are_read_as_before(raw: str, kg: float) -> None:
    assert normalize.gross_weight_kg(raw) == pytest.approx(kg)


# --------------------------------------------------------------------------
# Container counts
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw, n", [
    # The size written first: the first number is the box length, so "40HC x 3"
    # and "40HC x 2" both read 40 and a missing box was cleared.
    ("20GP x 2", 2), ("40HC x 3", 3), ("22G1 x 1", 1), ("45R1 x 2", 2), ("40' x 2", 2),
    # The count as a word.
    ("THREE X 40' HC", 3), ("FOUR X 40' HC CONTAINERS", 4),
])
def test_container_counts_in_real_notation(raw: str, n: int) -> None:
    assert normalize.container_count(raw) == n


@pytest.mark.parametrize("raw, n", [
    ("6", 6), ("6 x 40'HC", 6), ("6X40HC", 6), ("TOTAL 6 CONTAINERS", 6), ("1 x 40'HC", 1),
    ("3 x 20'FCL", 3), ("3 x 20'GP", 3), ("15 x 40'HC", 15), ("20 x 40'HC", 20),
    ("THREE (3) X 40' HC", 3), ("TWO (2) 40' CONTAINERS", 2), ("1 FCL", 1), ("6 x 4O'HC", 6),
    # Restated, broken-down, word-and-digit and dimensioned counts, read by the
    # first number exactly as before (each one broke under a wider rule).
    ("SAY TWENTY ONE (21) X 40'HC CONTAINERS ONLY", 21), ("TWENTY-FIVE (25) X 20GP", 25),
    ("2X40'HC SAY TWO (2X40'HC) CONTAINERS ONLY", 2), ("2 X 40'HC (SAY TWO X 40'HC ONLY)", 2),
    ("1 X 40'HC (PART OF 3 X 40'HC)", 1), ("3 CONTAINERS INCL. 1 X 20RF", 3),
    ("3 CNTRS (2X40HC+1X45G1)", 3), ("1 CONTAINER 40' X 8'6\" HIGH CUBE", 1),
    ("2 FLAT RACKS 40' X 12' WIDE (OOG)", 2), ("1,200 CARTONS", 1200), ("1200CTNS", 1200),
    # Mixed equipment is still the first group (summing it was withdrawn).
    ("1x40HC + 2x20GP", 1), ("1 X 40HC / 1 X 45G1", 1),
])
def test_other_counts_are_read_as_before(raw: str, n: int) -> None:
    assert normalize.container_count(raw) == n


# --------------------------------------------------------------------------
# Labels that took the wrong field
# --------------------------------------------------------------------------
@pytest.mark.parametrize("label", [
    "Shipper's Reference Number", "Consignee's Reference:", "Shipper - reference",
    "Shipper's declared value of", "Above Particulars as declared by Shipper",
    "MKS&NOS/CONTAINER NOS", "MARKS & NOS CONTAINER NOS",
    "CARRIER'S AGENTS ENDORSEMENTS (Include Agent(s) at POD)",
    "Port of Final Delivery", "Particulars furnished by Shipper",
    "NEGOTIABLE", "NON-NEGOTIABLE", "complete;", "delivery.", "Port of :",
])
def test_labels_that_are_not_one_of_the_seven(label: str) -> None:
    assert labels.resolve(label) is None


@pytest.mark.parametrize("label", ["Port of Unlading", "Unloading Port", "Port of Unloading"])
def test_unlading_is_the_port_of_discharge_not_of_loading(label: str) -> None:
    assert labels.resolve(label) == "port_of_discharge"


@pytest.mark.parametrize("label", ["Unloading address", "Loading/Unloading terms", "Unloading date"])
def test_other_unloading_lines_are_not_the_port_of_discharge(label: str) -> None:
    # A keyword rule on UNLOADING was reviewed and read these as the port.
    assert labels.resolve(label) != "port_of_discharge"


@pytest.mark.parametrize("label", ["Shipper (Shipper's Reference No.)", "Shipper (Shipper’s Reference No.)"])
def test_a_reference_sub_caption_does_not_hide_the_party_box(label: str) -> None:
    # The real JSE forms caption the shipper box this way; that box IS the
    # shipper, and excluding it let a terms-and-conditions line win instead.
    assert labels.resolve(label) == "shipper"


def test_the_one_unseen_wording_the_harness_relies_on_still_resolves() -> None:
    assert labels.resolve("Final Destination Port") == "port_of_discharge"


# --------------------------------------------------------------------------
# The PDF reader on a valid page with no recurring value column
# --------------------------------------------------------------------------
def test_no_recurring_value_column_is_not_a_crash() -> None:
    # Two labelled rows whose values start at different x. No bin reaches the
    # threshold; min() used to raise, and the whole PDF was reported corrupt.
    words = [
        {"text": "Shipper:", "x0": 50.0, "x1": 90.0, "top": 100.0, "bottom": 110.0, "fontname": "Helvetica-Bold"},
        {"text": "ACME", "x0": 120.0, "x1": 150.0, "top": 100.0, "bottom": 110.0, "fontname": "Helvetica"},
        {"text": "Consignee:", "x0": 50.0, "x1": 100.0, "top": 130.0, "bottom": 140.0, "fontname": "Helvetica-Bold"},
        {"text": "BETA", "x0": 260.0, "x1": 290.0, "top": 130.0, "bottom": 140.0, "fontname": "Helvetica"},
    ]
    assert pdf_reader._value_column_from_labelled_rows(words) is None
    assert isinstance(pdf_reader._value_column_x(words), float)
