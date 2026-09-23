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
    # Reference-number fields, not the party itself — the same trap as
    # "Booking Reference" above, but for the shipper. Found on a real
    # carrier's own SI template (CMA CGM), where "Shipper/Forwarders
    # Reference" contains the word "Shipper" and, without this entry, the
    # pass-2 rule `\b(SHIPPER|EXPORTER|CONSIGNOR)\b` reads a tracking number
    # into the shipper field instead of the party's name.
    "Shipper/Forwarders Reference", "Shipper's Reference",
    "Forwarder's Reference", "Forwarders Reference",
]

# Build the reverse lookup once.
_EXACT: dict[str, str] = {}
for _field, _variants in SYNONYMS.items():
    for _v in _variants:
        _EXACT[basic(_v)] = _field
_IGNORE: set[str] = {basic(x) for x in IGNORE_LABELS}

# Pass 3 fuzzy-matches against the synonyms, but only the ones long enough to
# be a *phrase*. Below six characters a synonym is an abbreviation — "POL",
# "POD", "G.W." are the only three we hold — and rapidfuzz's WRatio scores an
# abbreviation sitting inside a longer string at ~90, because it folds in a
# partial-ratio component whenever one side is at least 1.5x the other. With
# those three in the pool, real lines out of this dataset resolved to a port:
# "43-45 METROPOLITAN ROAD", "GDANSK, POLAND (PLGDN)" (a port *value* read as
# a port *label*) and "MARCOPOLO 810 V.BS005" (a vessel name), plus every
# NAPOLI / PODIUM / POLK / ACROPOLIS / SEVASTOPOL address line.
#
# Nothing is lost by dropping them, but only because each has another route:
# all three are matched letter-for-letter by pass 1, POL and POD have their
# own alternatives in the pass-2 port rules, and "G.W." now has a pass-2 rule
# of its own — it did not, and a review caught that every decorated spelling
# ("G.W. (KGS)", "TOTAL G.W.") had quietly stopped resolving. A query short
# enough to *be* a damaged "POL" never reaches pass 3 anyway, so a three-
# character key can only ever be hit by a query several times its length,
# which is the bug and not a use.
#
# Be clear about what this does NOT do. It raises the price of the fragment
# match; it does not end it. WRatio still scores any pool key at ~90 against a
# query 1.5x its length that contains it, so "12 SHIPPERTON LANE" resolves to
# shipper and "LOAD PORTLAND AVENUE" to port_of_loading today. Six is a
# threshold on the same continuum as the cutoff, chosen because it is the
# widest bar with zero measured collateral — a word-boundary guard would be
# the principled fix, and it cannot be used here because the manglings this
# pass exists for are exactly keys glued to other characters
# ("Total No. of Containersm" scores 97.8). The residual class is recorded in
# docs/ADVERSARIAL.md. The bar stays at six rather than four so a shorthand
# added later — "CNEE", "SHPR" — is exact-matched instead of quietly
# reintroducing the same fragment matching.
_MIN_FUZZY_SYNONYM_CHARS = 6
_FUZZY_KEYS: list[str] = [k for k in _EXACT if len(k) >= _MIN_FUZZY_SYNONYM_CHARS]


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
    # "G.W." is a synonym the table already holds, and it is the one
    # abbreviation with no other rule to catch it — the port abbreviations
    # have POL/POD alternatives above, "G.W." had only the fuzzy pass. When
    # that pass stopped matching short keys (see _MIN_FUZZY_SYNONYM_CHARS),
    # every decorated spelling of it — "G.W. (KGS)", "TOTAL G.W.",
    # "G.W. 毛重(KGS)" — silently resolved to nothing, while the bare form
    # still matched exactly. `basic()` has already folded the punctuation by
    # here, so this sees "G W". Checked against every label, value and text
    # line the readers produce across all four datasets: it matches none of
    # them, and it correctly declines "N.W. (KGS)", "NET WT", "TARE WT",
    # "BUILDING G WEST" and "BLOCK G, WING 2".
    ("gross_weight_kg", re.compile(r"\bG\s*W\b")),

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
    >>> resolve("43-45 METROPOLITAN ROAD")  # an address, not a label
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
    # Both sides need that substance, which is why the pool is `_FUZZY_KEYS`
    # and not every synonym: the guard above rejects a short *query*, and
    # `_MIN_FUZZY_SYNONYM_CHARS` rejects a short *candidate*. Two alternatives
    # were measured against the same battery and both cost real reads.
    # Requiring the query and the hit to be comparable in length rejects
    # "SHIPPERS NOTE", "NOTIFYING AGENT" and "RECEIVER GENERAL" at 1.5x and
    # still rejects "NOTIFYING AGENT" at 2x, because a real label legitimately
    # carries words our table does not; the ratio would then be tuned on the
    # manglings we happen to have seen. Swapping WRatio for a scorer with no
    # partial component loses "Final Destination Port", the unseen wording the
    # adversarial harness perturbs to. Pruning the pool is decided once, off a
    # property of our own table, and leaves every other query scored exactly
    # as before.
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
