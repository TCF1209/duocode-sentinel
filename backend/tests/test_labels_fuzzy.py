"""The fuzzy third pass of `labels.resolve()` — its reach, and its limits.

Pass 3 exists for one reason, written down in `docs/DATA_NOTES.md` §3b: PDF
rendering mangles labels ("TOTAL Gross Weightss(KGS)", "Export Carrier
(vessel, voyageM)") and an exact table cannot follow. It pays for that reach
with rapidfuzz's `WRatio`, which folds in a partial-ratio component whenever
one side is at least 1.5x the other — so a *short* candidate sitting inside a
*long* query scores around 90 and clears the 88 cutoff.

The table holds three synonyms short enough for that to bite: "POL", "POD"
and "G.W.". With them in the candidate pool every address line carrying those
letters resolved to a port — NAPOLI CENTRALE, PODIUM TOWER, POLK STREET 12,
"43-45 METROPOLITAN ROAD" — and the wide-gap splitter in `readers/rows.py`
then split the address into a field with a confident, invented value. That is
the precise defect `pdf.py` was rebuilt around, arriving by another door.

The guard is `labels._MIN_FUZZY_SYNONYM_CHARS`: a synonym under six
characters is an abbreviation, and abbreviations are matched letter for
letter, never approximately. This file pins the three things that makes true
at once — the manglings still resolve, the abbreviations still resolve, and
the addresses do not — and section 4 pins *which pass* answers, because the
whole argument for the guard rests on "POL" being answered before pass 3 ever
runs.
"""
from __future__ import annotations

import pytest
from rapidfuzz import fuzz, process

from sdoc import labels
from sdoc.normalize import basic


def resolving_pass(label: str) -> str:
    """Which of the three passes decides `label`.

    A duplicate of `resolve()`'s control flow rather than an instrument added
    to it: the production path stays free of test scaffolding, and a change
    that moves a label from one pass to another shows up here as a failure
    instead of passing quietly because the final answer happens to agree.
    """
    key = basic(label)
    if not key:
        return "empty"
    if key in labels._IGNORE:
        return "exact-ignore"
    if key in labels._EXACT:
        return "exact"
    for _field, pattern in labels._RULES:
        if pattern.search(key):
            return "rule"
    if len(key) < 8 and len(key.split()) < 2:
        return "too-short"
    if process.extractOne(key, labels._FUZZY_KEYS,
                          scorer=fuzz.WRatio, score_cutoff=88):
        return "fuzzy"
    return "unmatched"


# ==========================================================================
# 1. The bug — a short synonym hiding inside a long query
# ==========================================================================
# Every one of these is an ordinary line from a party's address block, and
# every one of them used to come back as a port. The letters are the whole
# problem: POL in NAPOLI, POLK, METROPOLITAN, ACROPOLIS, SEVASTOPOL and
# INTERPOL; POD in PODIUM and PODGORICA.
ADDRESS_LINES_CARRYING_POL_OR_POD = [
    "NAPOLI CENTRALE",
    "PODIUM TOWER",
    "POLK STREET 12",
    "43-45 METROPOLITAN ROAD",
    "ACROPOLIS AVENUE",
    "SEVASTOPOL ROAD",
    "INTERPOL HOUSE",
    "PODGORICA BUSINESS PARK",
    "LEOPOLDSTRASSE 12",
]


@pytest.mark.parametrize("line", ADDRESS_LINES_CARRYING_POL_OR_POD)
def test_an_address_carrying_a_port_abbreviation_is_not_a_port(line):
    """The expensive failure: a street resolving to a compared field.

    A wrong field is worse than a missing one. A missing port escalates and a
    human reads the document; a port read off the consignee's street address
    is compared against the other document and reported as a discrepancy that
    was never there, which is a false alarm on the axis `docs/SCORING.md` §1
    says costs us precision.
    """
    assert labels.resolve(line) is None


def test_a_port_name_is_not_a_port_label():
    """Naming a port is not labelling one.

    "NAPOLI" is a value the port-of-loading field may legitimately hold. It is
    not a label, and a resolver that cannot tell the difference reads the
    document's contents as its own headings.
    """
    assert labels.resolve("NAPOLI") is None
    assert labels.resolve("NAPOLI, ITALY") is None
    assert labels.resolve("TRIPOLI, LIBYA") is None


# ==========================================================================
# 2. The labels the fuzzy pass exists for — these must still resolve
# ==========================================================================
# Taken from `docs/DATA_NOTES.md` §2 and §3b: real wording out of the .docx
# bilingual forms and out of `pdftotext` on a real SI, plus the unseen wording
# the adversarial harness perturbs to (`backend/tools/adversarial.py`,
# UNSEEN_LABELS). These are load-bearing; a guard that silences them has
# traded one failure for a worse one.
MANGLED_AND_VARIANT_LABELS = [
    ("TOTAL Gross Weightss(KGS)", "gross_weight_kg"),
    ("Gross Weight毛重(KGS)", "gross_weight_kg"),
    ("GROSS WEIGHT (毛重 KGS)", "gross_weight_kg"),
    ("Shipper/Exporter (发货人)", "shipper"),
    ("Notify Party/Intermediate Consignee (通知人)", "notify_party"),
    ("Final Destination Port", "port_of_discharge"),
    ("Consignee (Non-Negotiablee)", "consignee"),
    ("Total No. of Containersm", "container_count"),
    ("Consignee Complete Name and Addressm", "consignee"),
    ("Port of Loadinq", "port_of_loading"),
]


@pytest.mark.parametrize("label,field", MANGLED_AND_VARIANT_LABELS)
def test_a_mangled_label_still_resolves(label, field):
    assert labels.resolve(label) == field


def test_the_labels_that_must_stay_ignored_stay_ignored():
    """A mangled label that is not one of the seven must not become one.

    "Export Carrier (vessel, voyageM)" is the §3b example that has to come
    back empty: it is the vessel row, it lost a character to the same broken
    font as the weight row above it, and reading it as a field would attach a
    voyage number to a party slot.
    """
    assert labels.resolve("Export Carrier (vessel, voyageM)") is None
    assert labels.resolve("CONTAINER NO.") is None
    assert labels.resolve("Net Weight") is None
    assert labels.resolve("Description of Goods") is None


def test_a_reference_number_field_is_not_the_shipper():
    """Found on a real carrier's own SI template, not our own generator.

    CMA CGM's public "Standard Shipping Instructions Template" has a
    "Shipper/Forwarders Reference" field for a tracking number. It contains
    the word "Shipper", so without the `IGNORE_LABELS` entry the pass-2 rule
    `\\b(SHIPPER|EXPORTER|CONSIGNOR)\\b` reads a reference code into the
    shipper field — and because it appears earlier in the document than the
    real "Shipper" party block, `extract/fields.py` keeps it as the winning
    candidate. Comparing a reference number against the other document's real
    company name produced a false MISMATCH on an otherwise-matching shipper.
    The same trap "Booking Reference" already guards against, one field over.
    """
    assert labels.resolve("Shipper/Forwarders Reference") is None
    assert labels.resolve("Shipper's Reference") is None
    assert labels.resolve("Forwarder's Reference") is None


def test_the_fuzzy_pass_is_what_reaches_the_unseen_wording():
    """Guards the reason pass 3 is allowed to exist at all.

    "Final Destination Port" is not in the table, is not matched by any rule,
    and is what the adversarial harness renames the discharge port to. If this
    ever answers from an earlier pass the guard below stops being a guard and
    starts being decoration.
    """
    assert resolving_pass("Final Destination Port") == "fuzzy"
    assert labels.resolve("Final Destination Port") == "port_of_discharge"


# ==========================================================================
# 3. The short labels are real labels, and still resolve
# ==========================================================================
# "POL" and "POD" head a column on plenty of carrier stationery. Excluding
# them from the *fuzzy pool* must not exclude them from the resolver.
SHORT_LABELS = [
    ("POL", "port_of_loading"),
    ("POD", "port_of_discharge"),
    ("POL:", "port_of_loading"),
    ("POD ", "port_of_discharge"),
    ("pol", "port_of_loading"),
    (" POD:", "port_of_discharge"),
    ("G.W.", "gross_weight_kg"),
    ("Port of Loading (POL)", "port_of_loading"),
    ("Port of Discharge (POD)", "port_of_discharge"),
]


@pytest.mark.parametrize("label,field", SHORT_LABELS)
def test_a_bare_abbreviation_is_still_a_label(label, field):
    assert labels.resolve(label) == field


# ==========================================================================
# 4. Which pass answers — the argument the guard rests on
# ==========================================================================
def test_the_abbreviations_are_answered_before_the_fuzzy_pass():
    """Why pruning the pool cannot cost us an abbreviation.

    Both spellings have to be covered, and the *decorated* spelling is the one
    that matters: the bare abbreviation is in the synonym table so pass 1
    matches it letter for letter, but a real document writes "G.W. (KGS)" or
    "LOAD PORT (POL)", and those need a pass 2 rule to match on a word
    boundary — which is exactly what "NAPOLI" fails.

    All three dropped keys are asserted here, not two. An earlier version of
    this test checked the compound form only for POL and POD, and the one key
    it left in its bare form was the one with no rule behind it: "G.W." had
    only the fuzzy pass, so pruning the pool silently took every decorated
    spelling of it to None while `resolving_pass("G.W.") == "exact"` went on
    passing. The pool invariant is only guarded if every key it drops is
    checked in the shape a document actually writes.
    """
    assert resolving_pass("POL") == "exact"
    assert resolving_pass("POD") == "exact"
    assert resolving_pass("G.W.") == "exact"

    assert resolving_pass("LOAD PORT (POL)") == "rule"
    assert resolving_pass("DISCHARGE PORT (POD)") == "rule"
    assert resolving_pass("G.W. (KGS)") == "rule"


@pytest.mark.parametrize("label", [
    "G.W. (KGS)", "G.W. (KG)", "G.W.(KGS)", "G.W. KGS", "G.W. IN KG",
    "G. W. (KGS)", "Total G/W (KGS)", "TOTAL G.W.", "G.W. 毛重(KGS)",
])
def test_every_decorated_spelling_of_the_weight_abbreviation_resolves(label):
    """The family that regressed, pinned one spelling at a time.

    `DATA_NOTES.md` §2 and §2b record that every weight label in this dataset
    carries a unit or a Chinese gloss in parentheses, so a bare "G.W." is the
    one form a real form will *not* use. None of these appears in the 250
    attachments — the abbreviation is a synonym we hold for wording we have
    not seen yet, which is precisely the reach the fuzzy pass exists to give
    and precisely what a pool change can take away without moving the score.
    """
    assert labels.resolve(label) == "gross_weight_kg"


@pytest.mark.parametrize("label", [
    "N.W. (KGS)", "NET WT", "TARE WT", "Net Weight",
    "BUILDING G WEST", "BLOCK G, WING 2", "G WING",
])
def test_the_weight_abbreviation_rule_does_not_overreach(label):
    """`\\bG\\s*W\\b` is narrow on purpose — net and tare are not gross."""
    assert labels.resolve(label) != "gross_weight_kg"


def test_a_short_query_never_reaches_the_fuzzy_pass_either():
    """The other half of the symmetry, and why a short synonym is dead weight.

    `resolve()` already refuses to fuzzy-match a query under eight characters
    that is a single word. So the only query that could ever reach a
    three-character candidate is one several times its length — the embedded
    fragment, i.e. the bug. Pruning the pool takes away no legitimate reach.
    """
    assert resolving_pass("POLX") == "too-short"
    assert resolving_pass("PODZ") == "too-short"


def test_the_fuzzy_pool_holds_only_synonyms_with_substance():
    """The guard itself, stated as the invariant it is.

    Pinned rather than left implicit because the pool is derived from
    `SYNONYMS`: adding "CNEE" or "SHPR" to the table tomorrow would silently
    put a four-character fragment matcher back in front of every address line
    if this rule were ever relaxed.
    """
    floor = labels._MIN_FUZZY_SYNONYM_CHARS
    assert floor == 6
    assert all(len(k) >= floor for k in labels._FUZZY_KEYS)

    excluded = sorted(set(labels._EXACT) - set(labels._FUZZY_KEYS))
    assert excluded == ["G W", "POD", "POL"], (
        "the fuzzy pool should differ from the synonym table only by the "
        "abbreviations; anything else dropped out is a table edit that needs "
        "looking at"
    )

    # Every field is still reachable by fuzzy match. Losing a whole field from
    # the pool would mean a mangled label for it could only ever escalate.
    reachable = {labels._EXACT[k] for k in labels._FUZZY_KEYS}
    assert reachable == set(labels.SYNONYMS)


def test_the_guard_is_the_synonym_length_and_not_the_cutoff():
    """Same query, same scorer, opposite answers — only the pool differs.

    Written this way because raising `fuzzy_cutoff` was the other obvious
    lever and the numbers say not to. The address scores 90 on "POL" — a
    perfect partial ratio, which `WRatio` weights at 0.9 — and a real mangled
    label, "Port of Loadinq", scores 93.3. Three points of daylight, measured
    on the handful of manglings we happen to have seen, would be the whole
    safety margin of the pass for all seven fields. Pruning the pool instead
    moves the address from 90 to 48.5 and leaves every label we keep scoring
    exactly what it scored before.
    """
    address = basic("43-45 METROPOLITAN ROAD")
    mangled = basic("Port of Loadinq")

    hit = process.extractOne(address, list(labels._EXACT), scorer=fuzz.WRatio)
    assert (hit[0], round(hit[1], 1)) == ("POL", 90.0)
    hit = process.extractOne(address, labels._FUZZY_KEYS, scorer=fuzz.WRatio)
    assert round(hit[1], 1) < 88

    for pool in (list(labels._EXACT), labels._FUZZY_KEYS):
        hit = process.extractOne(mangled, pool, scorer=fuzz.WRatio)
        assert (hit[0], round(hit[1], 1)) == ("PORT OF LOADING", 93.3)
