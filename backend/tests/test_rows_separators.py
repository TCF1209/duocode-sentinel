"""Alternative label separators in `readers/rows.py` — and the guard on them.

A colon is not the only thing a carrier puts between a label and its value. An
em dash, a pipe, a tab, or simply a wide gap are all just as readable to the
person filling the form in, and all of them appear in real stationery.
Recognising only the colon was measured against the adversarial harness as a
*safe* failure and a useless one: an em-dash separator, a missing colon, or an
indented field list each cost all 1281 field reads, every one of them escalated
rather than misread. With `_alt_split` in place all three read 1281/1281.

The dangerous half of that is the recognition, not the escalation, so most of
what is pinned here is the guard. A wide gap is far too common in prose, in
address blocks and in the container table to be a label boundary on its own,
and the only thing keeping the splitter honest is that the left-hand side must
resolve via `labels.resolve()` to one of the seven compared fields. Section 2
is therefore the centre of this file: it asserts what must *not* split.

`split_label_value()` is the single-string entry point, and it is reached from
all four readers — `pdf.py`, `office.py` (both the .docx paragraph path and the
.xlsx single-cell path) and `fallback.py`. Those are exactly the formats the
adversarial harness declares out of scope, so nothing there is measured and a
regression would be silent. Section 6 reads the real bundle documents back and
pins each of those four call sites.
"""
from __future__ import annotations

import pytest
from conftest import DATA, requires_bundle

from sdoc import labels
from sdoc.readers import read_attachment
from sdoc.readers.fallback import _chunks_from_markdown
from sdoc.readers.rows import chunks_from_lines, split_label_value


def one_chunk(line: str):
    """The single chunk `line` produces on its own, or None if it produces none."""
    chunks = chunks_from_lines([line])
    assert len(chunks) <= 1, f"{line!r} produced {len(chunks)} chunks"
    return chunks[0] if chunks else None


# ==========================================================================
# 1. The separators a form may use instead of a colon
# ==========================================================================
# The dash characters are easy to confuse by eye, so each row says which one it
# carries: U+2014 em dash, U+2013 en dash, U+2015 horizontal bar.
SEPARATOR_ROWS = [
    ("Port of Loading — SINGAPORE",                     # em dash
     "port_of_loading", "Port of Loading", "SINGAPORE"),
    ("Port of Discharge – KARACHI, PAKISTAN",           # en dash
     "port_of_discharge", "Port of Discharge", "KARACHI, PAKISTAN"),
    ("Consignee ― AL GURG STATIONERY LLC",              # horizontal bar
     "consignee", "Consignee", "AL GURG STATIONERY LLC"),
    ("Load Port\tSINGAPORE",
     "port_of_loading", "Load Port", "SINGAPORE"),
    ("Total Containers | 12 x 20'FCL",
     "container_count", "Total Containers", "12 x 20'FCL"),
    ("Gross Wt (kgs)    243,588",
     "gross_weight_kg", "Gross Wt (kgs)", "243,588"),
    ("NOTIFY PARTY  AL GURG STATIONERY LLC",            # the minimum: two spaces
     "notify_party", "NOTIFY PARTY", "AL GURG STATIONERY LLC"),
]


@pytest.mark.parametrize("line,field,label,value", SEPARATOR_ROWS)
def test_a_form_that_omits_the_colon_is_still_read(line, field, label, value):
    chunk = one_chunk(line)
    assert chunk is not None, f"{line!r} was not recognised as a field"
    assert (chunk.label, chunk.value) == (label, value)
    assert labels.resolve(chunk.label) == field


def test_a_single_space_is_not_a_separator():
    """One space is how words are written, not how a form is laid out.

    Two spaces is the floor on purpose. "Load Port SINGAPORE" is exactly what
    markitdown hands back for a two-column row (see `fallback.py`), and there
    is no honest way to tell that boundary from a label that simply contains
    the word — so it stays unrecovered rather than guessed at.

    "POD KARACHI" is the line that actually measures the floor, and it is here
    because the "Load Port" lines do not. `_ALT_SEPARATOR`'s label is
    non-greedy, so loosening the gap to `\\s{1,}` makes it match "Load" first,
    `labels.resolve("Load")` is None and the guard rejects the line anyway —
    the same answer by a different mechanism, which means those two assertions
    pass just as happily with the floor removed. "POD" and "POL" resolve on
    their own, twice over: each is an exact synonym and each is matched again
    by the ordered rules in `labels.py`, so the resolve() guard cannot be what
    rejects them and the two-space floor is the only thing left that can. The
    same lines with two spaces are fields, which is what makes the gap and not
    the label the thing under test.
    """
    assert labels.resolve("POD") == "port_of_discharge"
    assert labels.resolve("POL") == "port_of_loading"

    assert split_label_value("POD KARACHI") is None
    assert split_label_value("POL SINGAPORE") is None
    assert split_label_value("POD  KARACHI") == ("POD", "KARACHI")
    assert split_label_value("POL  SINGAPORE") == ("POL", "SINGAPORE")

    assert split_label_value("Load Port SINGAPORE") is None
    assert split_label_value("Load Port RUGAO/NANTONG/SHANGHAI, CHINA") is None


def test_a_label_with_nothing_after_the_separator_is_not_a_field():
    """A trailing dash on a heading rule is punctuation, not an empty value."""
    assert split_label_value("Port of Loading —") is None
    assert split_label_value("Total Containers |   ") is None


# ==========================================================================
# 2. The guard — what must NOT split
# ==========================================================================
# Realistic lines from the documents and covering notes this system reads. A
# wide gap appears in all of them and none may be mistaken for a field.
PROSE_LINES = [
    "Please confirm the draft B/L by 1700 hrs today    as the vessel closes tomorrow.",
    "Kindly note the shipment has been rolled to the next sailing    due to a berth delay.",
    "We have attached the revised Shipping Instruction    for your review and approval.",
]

ADDRESS_LINES = [
    "77 ROBINSON ROAD, #21-01    SINGAPORE 068896",
    "P.O. BOX 5069    DUBAI, UNITED ARAB EMIRATES",
    "LOT 6, JALAN P/7    SECTION 13, 43650 BANDAR BARU BANGI",
]

CONTAINER_TABLE_LINES = [
    "CONTAINER NO.   DESCRIPTION   GROSS WEIGHT (KG)",
    "GSLB0479748   40'HC UNCOATED WOODFREE PAPER IN REA   21,887",
    "ADNE4565060 | 40'HC | UNCOATED WOODFREE PAPER IN REA | 21,887",
]


@pytest.mark.parametrize("line", PROSE_LINES)
def test_a_prose_sentence_with_a_wide_gap_is_not_a_field(line):
    assert split_label_value(line) is None
    assert one_chunk(line) is None


@pytest.mark.parametrize("line", ADDRESS_LINES)
def test_an_address_line_with_a_wide_gap_is_not_a_field(line):
    """The expensive failure this guard prevents.

    Splitting an address line invents a field out of the party block sitting
    underneath the real one, and the value it invents is a confident piece of
    nonsense — the precise defect `pdf.py` was rebuilt around.
    """
    assert split_label_value(line) is None
    assert one_chunk(line) is None


@pytest.mark.parametrize("line", CONTAINER_TABLE_LINES)
def test_a_container_table_row_is_not_a_field(line):
    """Every container row carries an id, a description and a weight.

    Column gaps are what a table is made of, so without the resolve() guard
    each of these rows would offer itself as a gross-weight or container-count
    candidate and the per-container figure would compete with the total.
    """
    assert split_label_value(line) is None
    assert one_chunk(line) is None


def test_the_guard_is_the_resolve_call_and_not_the_shape_of_the_line():
    """Same shape, opposite outcomes: only the left-hand side decides.

    Worth stating directly, because it is the whole reason the wide gap can be
    allowed at all. These two lines are indistinguishable as text — a short
    left side, a gap, a value — and the only thing separating them is that one
    left side is a label we compare on and the other is a street.
    """
    assert split_label_value("Load Port    SINGAPORE") == ("Load Port", "SINGAPORE")
    assert split_label_value("Jalan Bangsar    SINGAPORE") is None


def test_an_address_containing_a_port_abbreviation_is_not_a_field():
    """A hole this file found, and the fix that closed it.

    `labels.resolve()` refuses to fuzzy-match a *query* shorter than eight
    characters, but for a while nothing stopped a short *synonym* matching
    inside a long query: "POL" sits in the middle of "METROPOLITAN", WRatio
    scored it 90, and "43-45 METROPOLITAN ROAD    ENFIELD NSW 2136" split as a
    port of loading. NAPOLI, PODIUM and POLK did the same.

    The trap predates the wide-gap splitter — anything resolving a label could
    hit it — but the splitter is what puts an address line in front of
    resolve() in the first place, which is why the case is pinned here. The
    fix is `labels._MIN_FUZZY_SYNONYM_CHARS`: pass 3 now matches only against
    synonyms long enough to be a phrase, so an abbreviation can be found by
    pass 1 or pass 2 and never as a fragment.

    This test was written as a strict xfail so it would go loud the day the
    fix landed. It did, and the marker came off with it.
    """
    assert split_label_value("43-45 METROPOLITAN ROAD    ENFIELD NSW 2136") is None
    assert labels.resolve("43-45 METROPOLITAN ROAD") is None
    for trap in ("NAPOLI CENTRALE", "PODIUM TOWER", "POLK STREET 12"):
        assert labels.resolve(trap) is None, trap

    # The abbreviations themselves are still real labels, reached by the
    # earlier passes — pruning the fuzzy pool must not cost us those.
    assert labels.resolve("POL") == "port_of_loading"
    assert labels.resolve("POD") == "port_of_discharge"


# ==========================================================================
# 3. A colon still wins
# ==========================================================================
def test_a_colon_beats_a_dash_further_along_the_same_line():
    """Ordering, not preference: trying the dash first reads a real document wrong.

    "Port of Loading: SINGAPORE — PSA TERMINAL" splits on the dash into a left
    side of "Port of Loading: SINGAPORE", which still resolves to the port of
    loading — so the guard cannot catch it — and the value silently becomes the
    terminal instead of the port.
    """
    assert labels.resolve("Port of Loading: SINGAPORE") == "port_of_loading"

    label, value = split_label_value("Port of Loading: SINGAPORE — PSA TERMINAL")
    assert label == "Port of Loading"
    assert value == "SINGAPORE — PSA TERMINAL"


def test_a_colon_beats_a_wide_gap_on_the_same_line():
    """A value indented away from its colon must not drag the colon into the label."""
    assert split_label_value("Total Gross Weight:  131,322 KG") == (
        "Total Gross Weight", "131,322 KG"
    )
    assert split_label_value("Container Count:   6 x 40'HC") == (
        "Container Count", "6 x 40'HC"
    )


def test_a_pipe_inside_a_value_stays_inside_the_value():
    """The .xlsx documents pack "NAME | ADDRESS" into one cell.

    The colon has already fixed the boundary by then, so the pipe is ordinary
    punctuation and the address stays attached for the extractor to strip.
    """
    label, value = split_label_value(
        "Consignee: AL GURG STATIONERY LLC | P.O. BOX 5069; DUBAI, UAE"
    )
    assert label == "Consignee"
    assert value == "AL GURG STATIONERY LLC | P.O. BOX 5069; DUBAI, UAE"


# ==========================================================================
# 4. Indentation
# ==========================================================================
def test_an_indented_address_block_still_continues_its_party():
    """The .txt documents indent the address under the party it belongs to.

    Keeping that as a continuation is what lets the extractor drop the address
    and compare the entity name alone; promoting any of these lines to a field
    would break the shipper in two.
    """
    chunks = chunks_from_lines([
        "SHIPPING INSTRUCTION",
        "Shipper/Exporter: APRIL FINE PAPER TRADING",
        "  ON BEHALF OF VITAL SOLUTIONS PTE LTD",
        "  77 ROBINSON ROAD, #21-01",
        "  ATTN: MR LIM  TEL: +65 6220 9088",
        "Consignee (Non-Negotiable): AL GURG STATIONERY LLC",
        "  P.O. BOX 5069",
        "  DUBAI, UNITED ARAB EMIRATES",
    ])

    assert [labels.resolve(c.label) for c in chunks] == ["shipper", "consignee"]
    assert chunks[0].value.startswith("APRIL FINE PAPER TRADING")
    assert "77 ROBINSON ROAD, #21-01" in chunks[0].value
    # "ATTN: MR LIM" is a colon line and an unrecognised label, so indentation
    # is the only thing keeping it out of the field list.
    assert "ATTN: MR LIM" in chunks[0].value
    assert chunks[1].value.endswith("DUBAI, UNITED ARAB EMIRATES")


def test_an_indented_field_list_is_still_a_field_list():
    """A form that indents every field under its title is still a form.

    All four of these lines are indented and all four resolve, so indentation
    loses to the label. Without this the entire document folds into the value
    of whatever came first.
    """
    chunks = chunks_from_lines([
        "BILL OF LADING (DRAFT)",
        "    Shipper/Exporter: APRIL FINE PAPER TRADING",
        "    Port of Loading — SINGAPORE",
        "    POD\tKARACHI, PAKISTAN",
        "    Total Containers | 12 x 20'FCL",
    ])

    assert [labels.resolve(c.label) for c in chunks] == [
        "shipper", "port_of_loading", "port_of_discharge", "container_count",
    ]
    assert [c.value for c in chunks] == [
        "APRIL FINE PAPER TRADING", "SINGAPORE", "KARACHI, PAKISTAN", "12 x 20'FCL",
    ]
    # the locator still counts the title line, so a reviewer can find the row
    assert [c.locator for c in chunks] == ["line 2", "line 3", "line 4", "line 5"]


def test_an_indented_line_we_do_not_recognise_never_starts_a_field():
    """The asymmetry is deliberate: only the seven may break the indentation.

    "Vessel" and "Booking Ref" are perfectly good labels and would start a
    chunk unindented. Indented, they are treated as part of the block above,
    because we cannot tell them apart from an address line that happens to
    contain a colon.
    """
    chunks = chunks_from_lines([
        "Notify Party: PACIFIC OFFICE (M) SDN BHD",
        "  Vessel: SOLID 16 V.044NW2",
        "  Booking Ref — PSGSE4981829",
    ])

    assert len(chunks) == 1
    assert labels.resolve(chunks[0].label) == "notify_party"
    assert "SOLID 16 V.044NW2" in chunks[0].value
    assert "PSGSE4981829" in chunks[0].value


# ==========================================================================
# 5. split_label_value() agrees with chunks_from_lines()
# ==========================================================================
# Four readers call the single-string entry point and one calls the line
# walker, so a divergence between them would mean the same row read one way in
# a .txt and another way in a .docx.
CONSISTENCY_CORPUS = (
    [row[0] for row in SEPARATOR_ROWS]
    + PROSE_LINES
    + ADDRESS_LINES
    + CONTAINER_TABLE_LINES
    + [
        "Port of Loading: SINGAPORE — PSA TERMINAL",
        "Total Gross Weight:  131,322 KG",
        "Load Port SINGAPORE",
        "BILL OF LADING (DRAFT)",
        "APRIL FINE PAPER TRADING",
        "HS CODE 48025700 FREIGHT PREPAID",
    ]
)


@pytest.mark.parametrize("line", CONSISTENCY_CORPUS)
def test_the_single_string_entry_point_reads_a_line_the_same_way(line):
    pair = split_label_value(line)
    chunk = one_chunk(line)

    if pair is None:
        assert chunk is None, f"{line!r}: the line walker split what the splitter did not"
    else:
        assert chunk is not None, f"{line!r}: the splitter split what the line walker did not"
        assert (chunk.label, chunk.value) == pair


# ==========================================================================
# 6. Blast radius — the four readers that call split_label_value()
# ==========================================================================
# pdf.py:101, office.py:60 (.xlsx) and :105 (.docx), fallback.py:119. None of
# these formats is measured by the adversarial harness, so each gets a real
# document from the bundle read back row for row.
@requires_bundle
def test_the_pdf_reader_still_reads_its_form_and_not_its_container_table():
    """`pdf.py:101` — the label column of every row goes through the splitter.

    `_join()` rebuilds the label column with single spaces, so the wide-gap
    branch can never fire there; the dash branch can, which is what the
    docstring's "TOTAL GROSS WEIGHT — 118,270 KG" is about. This document has
    six container rows whose ids sit in that same label column, and they must
    all still come back whole.
    """
    doc = read_attachment(DATA, "attachments/email_059_BL.pdf")
    assert doc.readable, doc.unreadable_reason
    by_field = {labels.resolve(c.label): c.value
                for c in doc.chunks if labels.resolve(c.label)}

    assert by_field["shipper"].startswith("APRIL FINE PAPER TRADING")
    assert by_field["consignee"].startswith("BALL & DOGGETT AUSTRALIA PTY LTD")
    assert by_field["notify_party"].startswith("PACIFIC OFFICE (M) SDN BHD")
    assert by_field["port_of_loading"] == "BUATAN, INDONESIA"
    assert by_field["port_of_discharge"] == "FREMANTLE, AUSTRALIA"
    assert by_field["container_count"] == "6 x 40'HC"
    assert by_field["gross_weight_kg"] == "131,322 KG"

    # the container rows kept their id as the label and their whole description
    # as the value — no separator was found inside either
    rows = [c for c in doc.chunks if c.label.startswith(("GSLB", "ADNE", "SRGL",
                                                         "ITVT", "LYEG", "EWKZ"))]
    assert len(rows) == 6
    for row in rows:
        assert labels.resolve(row.label) is None
        assert row.value == "40'HC UNCOATED WOODFREE PAPER IN REA 21,887"

    # and the table's heading row is still an ignored label, not a weight
    heading = next(c for c in doc.chunks if c.label == "CONTAINER NO.")
    assert heading.value == "DESCRIPTION GROSS WEIGHT (KG)"


def test_a_pdf_row_drawn_as_one_string_splits_on_its_dash():
    """The case `split_label_value()`'s own docstring cites.

    When a form has no value column the whole row lands in `left_text`, and the
    dash is then the only boundary there is.
    """
    assert split_label_value("TOTAL GROSS WEIGHT — 118,270 KG") == (
        "TOTAL GROSS WEIGHT", "118,270 KG"
    )


@requires_bundle
def test_the_word_reader_still_reads_its_paragraphs_and_its_table():
    """`office.py:105` — every .docx paragraph goes through the splitter.

    The paragraph that matters is "ORDER NO.: 3658202970   FREIGHT PREPAID": it
    carries a colon *and* a wide gap, and only the colon may be used. Splitting
    on the gap would put the order number in the label and the freight term in
    the value.
    """
    doc = read_attachment(DATA, "attachments/email_055_BL.docx")
    assert doc.readable, doc.unreadable_reason
    by_locator = {c.locator: c for c in doc.chunks}

    assert by_locator["para 3"].label == "ORDER NO."
    assert by_locator["para 3"].value.startswith("3658202970")
    assert "FREIGHT PREPAID" in by_locator["para 3"].value
    assert by_locator["para 2"].label == "B/L NO.(提单号)"

    # the title paragraph has no separator of any kind and stays out
    assert not any(c.label == "BILL OF LADING (DRAFT)" for c in doc.chunks)

    by_field = {labels.resolve(c.label): c.value
                for c in doc.chunks if labels.resolve(c.label)}
    assert by_field["port_of_loading"] == "SINGAPORE"
    assert by_field["port_of_discharge"] == "KARACHI, PAKISTAN"
    assert by_field["container_count"] == "12 x 20'FCL"
    assert by_field["gross_weight_kg"] == "243,588"


@requires_bundle
def test_the_excel_reader_still_ignores_its_title_row():
    """`office.py:60` — a row with only column A goes through the splitter.

    Every .xlsx in the bundle opens with the mill's name alone in A1. It is one
    of the few single-cell rows the splitter ever sees, and turning it into a
    field would put a company name where a label belongs.
    """
    doc = read_attachment(DATA, "attachments/email_055_SI.xlsx")
    assert doc.readable, doc.unreadable_reason

    assert doc.text.startswith("APRIL FINE PAPER TRADING")
    assert not any(c.locator == "S.I.!A1" for c in doc.chunks)
    assert not any(c.label == "APRIL FINE PAPER TRADING" for c in doc.chunks)

    by_field = {labels.resolve(c.label): c.value
                for c in doc.chunks if labels.resolve(c.label)}
    assert by_field["port_of_loading"] == "SINGAPORE"
    assert by_field["port_of_discharge"] == "KARACHI, PAKISTAN"
    assert by_field["container_count"] == "12 x 20'FCL"
    assert by_field["gross_weight_kg"] == "243588"


def test_the_markitdown_fallback_recovers_a_dash_but_still_not_a_bare_gap():
    """`fallback.py:119` — a one-cell Markdown row goes through the splitter.

    `fallback.py` documents that markitdown returns "Load Port RUGAO/NANTONG/
    SHANGHAI, CHINA" with the boundary lost, and that recovering it would need
    a fixed list of labels or a model call. That stays true — a single space is
    not a separator — but a document that used a dash is now readable, and the
    container rows still produce nothing.
    """
    chunks = _chunks_from_markdown(
        "# BILL OF LADING (DRAFT)\n"
        "\n"
        "| Load Port RUGAO/NANTONG/SHANGHAI, CHINA |  |  |\n"
        "| Port of Discharge — HOCHIMINH CITY, VIETNAM |  |  |\n"
        "| CONTAINER NO. DESCRIPTION GROSS WEIGHT (KG) |  |  |\n"
        "| TSSU2036148 40'HC UNCOATED WOODFREE PAPER 23,654 |  |  |\n"
    )

    assert len(chunks) == 1
    assert chunks[0].label == "Port of Discharge"
    assert chunks[0].value == "HOCHIMINH CITY, VIETNAM"
    assert chunks[0].locator == "md line 4"
