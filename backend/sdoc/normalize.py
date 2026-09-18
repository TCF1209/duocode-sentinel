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


def container_count(value) -> Optional[int]:
    """Containers as an integer.

    Handles "6", "6 x 40'HC", "6X40HC", "TOTAL 6 CONTAINERS", 6, 6.0.

    The count is always the number that comes *before* the container-size
    token, which is why we take the first number and not the largest: in
    "6 x 40'HC" the 40 is the box size, not a quantity.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    s = first_segment(str(value))
    if is_blank(s):
        return None
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
    if is_blank(s):
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
