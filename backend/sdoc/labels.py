"""Label resolution — mapping a document's wording onto our 7 canonical fields.

The SI and the BL deliberately label the *same* fact differently:

    SI: "Port of Loading (POL)"      BL: "Load Port"
    SI: "Total Containers"           BL: "Container Count"
    SI: "Consignee (Non-Negotiable)" BL: "To the Order of"
    SI: "Gross Wt (kgs)"             BL: "Gross Weight毛重(KGS)"

and PDF rendering mangles some of them outright ("TOTAL Gross Weightss(KGS)",
"Export Carrier (vessel, voyageM)").  So resolution runs in three passes:

    1. exact match against a known-synonym table   (fast, unambiguous)
    2. ordered regex rules                          (handles unseen wording)
    3. fuzzy match against the synonym table        (handles mangled labels)

Order matters in pass 2. "Notify Party/Intermediate Consignee" contains the
word *Consignee*; checking NOTIFY first is what stops the notify party from
being read as the consignee.
"""
from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz, process

from .normalize import basic

# --------------------------------------------------------------------------
# Pass 1 — known synonyms.
# Anything observed in a real SI/BL belongs here; it is the cheapest and
# safest path. Keys are stored in normalise.basic() form.
# --------------------------------------------------------------------------
SYNONYMS: dict[str, list[str]] = {
    "shipper": [
        "Shipper", "Shipper/Exporter", "Shipper (Principal or Seller)",
        "Exporter", "Consignor", "Shipper or Exporter", "Shipper Name",
        "Shipper/Consignor",
    ],
    "consignee": [
        "Consignee", "Consignee (Non-Negotiable)", "To the Order of",
        "To Order of", "Consignee Name", "Consigned to", "Receiver",
        "Consignee (Complete Name and Address)",
    ],
    "notify_party": [
        "Notify Party", "Notify", "Notify Party/Intermediate Consignee",
        "Notify Address", "Also Notify", "Notify Party (Complete Name and Address)",
        "Intermediate Consignee",
    ],
    "port_of_loading": [
        "Port of Loading", "Port of Loading (POL)", "Load Port", "POL",
        "Loading Port", "Port of Receipt", "Port of Lading",
    ],
    "port_of_discharge": [
        "Port of Discharge", "Port of Discharge (POD)", "Discharge Port", "POD",
        "Discharging Port", "Port of Delivery", "Destination Port",
    ],
    "container_count": [
        "No. of Containers", "Total Containers", "No. of Containers or Packages",
        "Container Count", "Number of Containers", "Container Qty",
        "Quantity of Containers", "Total No. of Containers", "Containers",
        "No of Ctnrs", "Ctr Count",
    ],
    "gross_weight_kg": [
        "Gross Weight (KG)", "Gross Wt (kgs)", "Gross Weight", "GROSS WEIGHT",
        "Total Gross Weight", "Gross Weight (KGS)", "Gross Wt", "G.W.",
        "Gross Weight in KG", "Total Gross Wt",
    ],
}

# Labels that must never be mistaken for one of the 7 — mostly because they
# share a keyword with a field we do care about.
IGNORE_LABELS: list[str] = [
    "Container No.", "Container Number", "Container Numbers", "Container No",
    "Net Weight", "Net Wt", "N.W.", "Tare Weight", "Measurement",
    "Description of Goods", "Kinds of Packages; Description of Goods",
    "Description", "Commodity", "Marks and Numbers",
    "Vessel", "Ocean Vessel", "Vessel Name", "Export Carrier (vessel, voyage)",
    "Voyage", "Voyage No.", "Voy.", "Voy. No",
    "Booking Reference", "Booking No.", "Booking Ref", "B/L No.", "BL No.",
    "Bill of Lading No.", "B/L Number", "HS Code", "Freight", "OC No.",
    "Order No.", "Invoice No.", "Place of Delivery", "Place of Receipt",
]

# Build the reverse lookup once.
_EXACT: dict[str, str] = {}
for _field, _variants in SYNONYMS.items():
    for _v in _variants:
        _EXACT[basic(_v)] = _field
_IGNORE: set[str] = {basic(x) for x in IGNORE_LABELS}
_FUZZY_KEYS: list[str] = list(_EXACT.keys())


# --------------------------------------------------------------------------
# Pass 2 — ordered regex rules.
# Evaluated top to bottom; the FIRST match wins, so the most specific and the
# most easily-confused patterns come first.
# --------------------------------------------------------------------------
_RULES: list[tuple[Optional[str], re.Pattern[str]]] = [
    # ---- collision exclusions: these share a keyword with a real field ---
    # "CONTAINER NO." is the id column of the container table, not a count.
    (None, re.compile(r"^CONTAINERS?\s+(NO|NOS|NUMBERS?)$")),
    # "Net Weight" would otherwise be swept up by the gross-weight rule.
    (None, re.compile(r"^(NET|TARE)\s+(WEIGHT|WT)")),

    # ---- notify BEFORE consignee: it contains the word "consignee" -------
    ("notify_party", re.compile(r"\bNOTIFY\b")),

    ("shipper", re.compile(r"\b(SHIPPER|EXPORTER|CONSIGNOR)\b")),
    ("consignee", re.compile(r"\b(CONSIGNEE|TO THE ORDER OF|TO ORDER OF)\b")),

    ("port_of_loading", re.compile(r"\b(PORT OF LOADING|LOADING PORT|LOAD PORT|POL)\b")),
    ("port_of_discharge",
     re.compile(r"\b(PORT OF DISCHARGE|DISCHARGE PORT|DISCHARGING PORT|POD)\b")),

    ("container_count",
     re.compile(r"\bCONTAINERS?\b.*\b(COUNT|QTY|QUANTITY)\b"
                r"|\b(NO|NOS|NUMBER|TOTAL|QTY|QUANTITY)\b.*\bCONTAINERS?\b"
                r"|^CONTAINERS?$")),

    ("gross_weight_kg", re.compile(r"\bGROSS\b.*(WEIGHT|WT)")),

    # ---- generic exclusions, last: they must not shadow a party label
    # (e.g. "To the Order of" contains ORDER but is the consignee) ---------
    (None, re.compile(r"\b(DESCRIPTION|COMMODITY|MARKS)\b")),
    (None, re.compile(r"\b(VESSEL|VOYAGE|VOY|CARRIER)\b")),
    (None, re.compile(r"\b(BOOKING|HS\s*CODE|FREIGHT|INVOICE|ORDER)\b")),
    (None, re.compile(r"^(B\s*L|BILL OF LADING)\s*(NO|NUMBER)")),
]


def resolve(label: str, *, fuzzy_cutoff: int = 88) -> Optional[str]:
    """Map a raw document label onto one of COMPARE_FIELDS, or None.

    >>> resolve("Notify Party/Intermediate Consignee (通知人)")
    'notify_party'
    >>> resolve("TOTAL Gross Weightss(KGS)")
    'gross_weight_kg'
    >>> resolve("CONTAINER NO.")            # table header, not a field
    """
    key = basic(label)
    if not key:
        return None

    # pass 1 — exact
    if key in _IGNORE:
        return None
    if key in _EXACT:
        return _EXACT[key]

    # pass 2 — ordered rules
    for field_name, pattern in _RULES:
        if pattern.search(key):
            return field_name  # may be None => explicitly ignored

    # pass 3 — fuzzy, for labels mangled by PDF text extraction.
    # Only for labels with enough substance to be distinctive: a bare "TOTAL"
    # or "CONTAINER" scores high against "Total Containers" while actually
    # being a fragment of something else entirely.
    if len(key) < 8 and len(key.split()) < 2:
        return None
    hit = process.extractOne(key, _FUZZY_KEYS, scorer=fuzz.WRatio,
                             score_cutoff=fuzzy_cutoff)
    if hit:
        return _EXACT[hit[0]]
    return None


def looks_like_label(text: str) -> bool:
    """Cheap guard used by readers: could this text be a field label at all?

    Keeps the PDF row splitter from treating a container id or a paragraph of
    prose as a label.
    """
    s = text.strip()
    if not s or len(s) > 70:
        return False
    return bool(re.search(r"[A-Za-z]", s))
