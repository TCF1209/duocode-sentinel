"""Normalisation engine — "the same information can look different".

Everything here answers one question: *are these two strings the same shipping
fact written differently?*  It must be strict enough not to miss a real
discrepancy and forgiving enough not to raise a false alarm over punctuation,
a legal suffix or a thousands separator.

Design rule: after normalisation we compare with **exact equality**, never
fuzzy similarity.  Fuzzy matching is dangerous here because the entity pools
contain genuinely near-identical names, e.g.

    "APRIL FINE PAPER TRADING"  vs  "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    "NANTONG, CHINA"            vs  "RUGAO/NANTONG/SHANGHAI, CHINA"

Those are *different* parties/ports and a similarity threshold would happily
merge them, silently swallowing a real defect. Fuzzy matching is used only for
matching **labels** (see labels.py), never for **values**.
"""
from __future__ import annotations

import re
from typing import Optional

# --------------------------------------------------------------------------
# Blank / placeholder detection
#
# A blank is NOT a discrepancy — it means the document does not tell us the
# value, so the case must go to a human instead of being reported as a
# mismatch. These are the shapes a blank takes in practice.
# --------------------------------------------------------------------------
_BLANK_WORDS = {
    "", "-", "--", "N/A", "NA", "NIL", "NONE", "NULL",
    "TBA", "TBC", "TBD", "TO BE ADVISED", "TO BE CONFIRMED", "PENDING",
    "???", "?", "XXX", "XXXX",
}

# "_______", "???", "____MT", "--- KG", "___ KGS" ...
_BLANK_RE = re.compile(r"^[\s_\?\-\.\*x]*(?:MT|MTS|KG|KGS|TON|TONS)?[\s_\?\-\.\*]*$", re.I)


def is_blank(value: Optional[str]) -> bool:
    """True when a value is present in the document but carries no information."""
    if value is None:
        return True
    s = str(value).strip()
    if s.upper() in _BLANK_WORDS:
        return True
    if _BLANK_RE.match(s):
        return True
    # a value made only of placeholder characters, e.g. "?? / __"
    stripped = re.sub(r"[\s_\?\-\.\*/]", "", s)
    return stripped == ""


# --------------------------------------------------------------------------
# Generic text normalisation
# --------------------------------------------------------------------------
def basic(s: Optional[str]) -> str:
    """Upper-case, ASCII-alphanumeric tokens only, single-spaced.

    Drops CJK characters, punctuation and accents, so
    "Gross Weight毛重(KGS)" and "GROSS WEIGHT (KGS)" collapse to the same form.
    """
    if s is None:
        return ""
    s = str(s).upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return " ".join(s.split())


def first_segment(value: Optional[str]) -> str:
    """The part of a multi-line / piped value that holds the entity name.

    Readers hand us values that may carry the address after the name:

        txt   "EAST BRIGHT FZ-LLC\\n  RAKEZ AMENITY CENTER; ..."
        docx  "EAST BRIGHT FZ-LLC\\nRAKEZ AMENITY CENTER\\n..."
        xlsx  "EAST BRIGHT FZ-LLC | RAKEZ AMENITY CENTER; ..."

    In all three the entity name is the first line, and for xlsx it is the part
    before the pipe. Addresses are deliberately *not* compared: the generator
    can change a party name while leaving the old address block in place, so an
    address match would mask a real defect.
    """
    if value is None:
        return ""
    s = str(value).strip()
    s = s.split("|")[0]
    s = s.splitlines()[0] if s.splitlines() else s
    return s.strip(" \t;,")


# --------------------------------------------------------------------------
# Organisations (shipper / consignee / notify party)
# --------------------------------------------------------------------------
# Legal-form tokens that carry no identity. Dropping them makes
# "KTP CO., LTD" == "KTP CO LTD" == "KTP".
_LEGAL_TOKENS = {
    "PTE", "PTY", "LTD", "LTDA", "LIMITED", "LLC", "LLP", "PLC", "INC",
    "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "GMBH", "AG",
    "SA", "SAS", "SARL", "SRL", "SPA", "NV", "BV", "AB", "AS", "OY",
    "SDN", "BHD", "FZE", "FZC", "FZ", "LLC", "DMCC", "JLT", "WLL",
    "UAB", "OOO", "ZAO", "PT", "TBK", "JSC", "JOINT", "STOCK",
    "PVT", "PRIVATE", "GROUP", "HOLDINGS", "HOLDING",
}


def org(value: Optional[str]) -> str:
    """Canonical form of a company name.

    >>> org("KPP-ANTALIS (SINGAPORE) PTE. LTD.")
    'KPP ANTALIS SINGAPORE'
    >>> org("TOAN LUC PAPER JOINT STOCK COMPANY")
    'TOAN LUC PAPER'
    """
    name = basic(first_segment(value))
    if not name:
        return ""
    tokens = [t for t in name.split() if t not in _LEGAL_TOKENS]
    # never normalise a name out of existence — fall back to the full form
    return " ".join(tokens) if tokens else name


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------
# UN/LOCODE looks like "SGSIN", "CNNTG" — 5 letters, usually in parentheses.
_LOCODE_RE = re.compile(r"\(\s*([A-Z]{2}[A-Z0-9]{3})\s*\)")

# Words that decorate a port name without changing which port it is.
_PORT_NOISE = {"PORT", "OF", "SEAPORT", "TERMINAL"}


def locode(value: Optional[str]) -> Optional[str]:
    """Pull a UN/LOCODE out of a port string, if the document printed one."""
    if not value:
        return None
    m = _LOCODE_RE.search(str(value).upper())
    return m.group(1) if m else None


def port(value: Optional[str]) -> str:
    """Canonical form of a port name, with any UN/LOCODE removed.

    >>> port("NANTONG, CHINA (CNNTG)")
    'NANTONG CHINA'
    >>> port("PORT KLANG (WESTPORT), MALAYSIA")
    'KLANG WESTPORT MALAYSIA'
    """
    s = first_segment(value)
    s = _LOCODE_RE.sub(" ", str(s).upper())
    tokens = [t for t in basic(s).split() if t not in _PORT_NOISE]
    return " ".join(tokens)


def ports_equal(a: Optional[str], b: Optional[str]) -> bool:
    """Two ports are the same if the names agree, or the UN/LOCODEs do.

    The locode is only ever used to *confirm* a match, never to overrule a
    name difference — a document can print a stale code next to a new port.
    """
    na, nb = port(a), port(b)
    if na and na == nb:
        return True
    ca, cb = locode(a), locode(b)
    return bool(ca and cb and ca == cb and na == nb)


# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------
_NUM_RE = re.compile(r"[-+]?\d[\d,\s]*(?:\.\d+)?")


def _to_float(token: str) -> Optional[float]:
    token = token.replace(",", "").replace(" ", "")
    try:
        return float(token)
    except ValueError:
        return None


# Characters an OCR engine returns in place of a digit. Exactly the confusion
# set the adversarial harness injects (`backend/tools/adversarial.py`), because
# that is the set with a measured failure behind it rather than an imagined one.
_DIGIT_LOOKALIKES = "OIlSB"


def digits_contaminated(s: str) -> bool:
    """Is the number we would read out of `s` glued to a digit lookalike?

    This exists because `_NUM_RE` is a *prefix* match, and a prefix match on a
    damaged number is worse than no match at all. "216,9S0 KG" matched "216,9"
    and became **2169 kg** — a confident, plausible, wrong answer, on a field
    whose defects are planted at +/-500 kg. "13B MT" became 13,000 instead of
    138,000. Neither reached a human, because nothing downstream could tell a
    truncated number from a short one.

    The test is deliberately at the *edges of the matched number* rather than
    anywhere in the value. Shipping notation is full of digits and letters
    sharing a line, and only the ones touching the number we parsed can have
    changed what we parsed: in "6 x 4O'HC" the damage is in the container
    size, the count is still a legible 6, and refusing to read it would cost
    an escalation for nothing. Measured: checking the whole value instead
    turns 72 readable container counts into escalations and buys no accuracy.

    Checked against every distinct raw value of both numeric fields across all
    four datasets (643 of them): zero legitimate values are rejected.

    It can only ever turn a value into `None`, which reads as "unparseable"
    and ends in `NEEDS_REVIEW`. It cannot make two values agree.

    >>> digits_contaminated("216,9S0 KG")
    True
    >>> digits_contaminated("13B MT")
    True
    >>> digits_contaminated("216,950 KGS")
    False
    >>> digits_contaminated("6 x 4O'HC")
    False
    """
    m = _NUM_RE.search(s)
    if m is None:
        return False
    if m.start() > 0 and s[m.start() - 1] in _DIGIT_LOOKALIKES:
        return True
    return m.end() < len(s) and s[m.end()] in _DIGIT_LOOKALIKES


# A container size as printed: a length with a type code ("40HC", "20' GP"),
# a length with a foot mark ("40'"), or an ISO 6346 size-type code ("22G1").
_CTR_SIZE = (
    r"(?:(?:20|40|45)\s*(?:'|’|FT)?\s*(?:GP|HC|HQ|DV|DC|RF|RH|OT|FR|TK|SD|SH|ST|STD|FCL|NOR)\b"
    r"|(?:20|40|45)\s*(?:'|’)"
    r"|[24L][0-9A-Z][A-Z]\d\b)"
)
_NUM_WORDS = {
    w: i for i, w in enumerate(
        "ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE".split(), start=1)
}
# Each of these must be the WHOLE value. A line that restates or breaks down
# a count ("2 X 40'HC (SAY TWO X 40'HC ONLY)", "3 CONTAINERS INCL. 1 X 20RF")
# or carries a box dimension ("1 CONTAINER 40' X 8'6\"") is read exactly as
# before, by its first number: wider rules were reviewed old-against-new and
# broke those. Summing mixed equipment ("1x40HC + 2x20GP") was withdrawn for
# the same reason: a value that names the same boxes twice, or a total and its
# breakdown, summed to double.
_CTR_SIZE_FIRST_ONLY = re.compile(rf"^\s*{_CTR_SIZE}\s*[X×*]\s*(\d{{1,3}})\s*$", re.I)
_CTR_WORD_ONLY = re.compile(
    rf"^\s*({'|'.join(_NUM_WORDS)})\s*[X×*]\s*{_CTR_SIZE}\s*(?:CONTAINERS?|CNTRS?|CTRS?)?\s*$", re.I)


def container_count(value) -> Optional[int]:
    """Containers as an integer.

    Handles "6", "6 x 40'HC", "6X40HC", "TOTAL 6 CONTAINERS", 6, 6.0.

    The count is always the number that comes *before* the container-size
    token, which is why we take the first number and not the largest: in
    "6 x 40'HC" the 40 is the box size, not a quantity.

    Two shapes found on real documents outside the generator
    (docs/EXTERNAL_VALIDATION.md) are read differently, and only when they are
    the whole value: the size first ("40HC x 3", where the first number is the
    box length, so "40HC x 3" and "40HC x 2" both read 40 and a missing box was
    cleared), and the count as a word ("THREE X 40' HC").
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    s = first_segment(str(value))
    if is_blank(s) or digits_contaminated(s):
        return None
    size_first = _CTR_SIZE_FIRST_ONLY.match(s)
    word = _CTR_WORD_ONLY.match(s)
    if size_first:
        return int(size_first.group(1)) or None
    if word:
        return _NUM_WORDS[word.group(1).upper()]
    m = _NUM_RE.search(s)
    if not m:
        return None
    n = _to_float(m.group(0))
    if n is None:
        return None
    n = int(round(n))
    return n if 0 < n < 100000 else None


_WEIGHT_UNIT_RE = re.compile(r"\b(KGS?|KILOS?|KILOGRAMS?|MTS?|TONS?|TONNES?)\b", re.I)


def gross_weight_kg(value) -> Optional[float]:
    """Gross weight in kilograms.

    Handles "131,058 KG", "131058", 216950, "216 950 kgs", "138 MT" (-> kg).
    Metric tonnes are converted so a document quoting MT still compares against
    one quoting KG.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = first_segment(str(value))
    if is_blank(s) or digits_contaminated(s):
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    n = _to_float(m.group(0))
    if n is None:
        return None
    unit = _WEIGHT_UNIT_RE.search(s)
    if unit and unit.group(1).upper().startswith(("MT", "TON")):
        n *= 1000.0
    # Pounds are still read as kilograms ("26,455 LBS" is 26,455). Known and
    # left open (docs/EXTERNAL_VALIDATION.md): three versions of a conversion
    # were reviewed old-against-new and each broke real shapes, the narrowest
    # because it converts one document's pounds and not the other's, which
    # turns the same weight printed two ways into a false defect. A fix needs
    # the comparison to see both sides' units, not this one value.
    return n if n > 0 else None


# --------------------------------------------------------------------------
# Field-level dispatch
# --------------------------------------------------------------------------
def normalise_field(field: str, value) -> tuple[Optional[str], Optional[float]]:
    """Return (canonical_text, number) for a field value.

    `number` is populated only for the two numeric fields; comparison uses it
    in preference to the text so that "6 x 40'HC" == "6 X 40 HC" == 6.
    """
    if value is None or is_blank(value if isinstance(value, str) else str(value)):
        return None, None

    if field in ("shipper", "consignee", "notify_party"):
        n = org(value)
        return (n or None), None

    if field in ("port_of_loading", "port_of_discharge"):
        n = port(value)
        return (n or None), None

    if field == "container_count":
        n = container_count(value)
        return (str(n) if n is not None else None), (float(n) if n is not None else None)

    if field == "gross_weight_kg":
        n = gross_weight_kg(value)
        return (f"{n:.0f}" if n is not None else None), n

    n = basic(value)
    return (n or None), None
