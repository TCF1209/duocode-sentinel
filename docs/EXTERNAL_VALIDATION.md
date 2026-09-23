# External validation

`docs/SCORING.md` §4.2 and `docs/ADVERSARIAL.md` both say the same thing
plainly: four datasets from one generator prove we do not memorise a draw,
not that we survive a real document. The adversarial harness closes part of
that gap by perturbing our own generator's output. This closes a different
part of it — a document from **outside** the generator entirely.

## Source

CMA CGM's public **Standard Shipping Instructions Template**
(<https://www.cma-cgm.com/assets/public/pdf/SI%20TEMPLATE.pdf>) — a blank,
publicly hosted form, no confidential data. The **label wording and
document structure are real and external**; the shipment data filled in to
test it is synthetic, built the same way `backend/tests/test_api.py`'s
fixtures are. State it that way — this is not a claim of having tested a
real shipment.

## Scope

Run locally (`uvicorn` on a scratch port), against `POST /compare`,
`use_llm=false`. Not run against the deployed API — nothing about this
needed the live deployment.

Tested: the `.docx` paragraph and table readers (`readers/office.py`) and
label resolution (`labels.py`). **Not tested**: `readers/pdf.py`'s
coordinate-based column reconstruction — building a real filled PDF would
have needed a PDF-writing dependency not already in `requirements.txt`, and
adding one wasn't worth the risk two days before a live pitch. `python-docx`
is an existing dependency and reads/writes `.docx` equally well, so the test
used that format instead — the thing under test (unfamiliar real-world
label wording and structure) is orthogonal to which reader parses it.

## Findings

**Held.** `consignee`, `notify_party`, `port_of_loading` and
`port_of_discharge` all matched correctly despite CMA CGM's different
wording and field order — e.g. `POL (Port of Loading)`, abbreviation
first, where the generator's own documents usually write the full name
first. The pass-2 regex rules key on the word, not its position, so this
held without any change.

**Found and fixed.** `Shipper/Forwarders Reference` is a tracking-number
field, but contains the word "Shipper" — `labels.py`'s pass-2 rule read a
reference code into the `shipper` field, ahead of the real party block
later in the document, producing a false `MISMATCH` against the other
side's real company name. Fixed by adding it to `IGNORE_LABELS` (the same
trap `Booking Reference` already guards against, one field over), pinned
by `test_a_reference_number_field_is_not_the_shipper` in
`test_labels_fuzzy.py`. Verified: the added label strings appear nowhere
in `bundle_data/`, the committed 520-email set, and a full re-run of
`backend/tools/adversarial.py` against it — 16 modes, 94 pairs, 188
documents, 20,496 field reads — matches `docs/ADVERSARIAL.md` exactly,
zero movement.

**Found, then fixed the same day.** CMA CGM's real container table is six
columns, one row per container (`Nr`, `Container Nr`, `Seal Nr`, packages,
description, gross weight). `readers/office.py`'s `.docx` table reader
assumed a two-column label:value table — the module's own docstring said
so — so neither `container_count` nor `gross_weight_kg` was read from it.
The failure was safe: both came back `missing`, not guessed, and the case
correctly escalated rather than reporting a fabricated comparison.

Fixed the narrower, safer half: `read_docx` now recognises a table whose
header row names a "container" column and has 3+ columns as a manifest —
one row per container — and derives `container_count` from the row count,
emitted as an ordinary `Chunk(label="Container Count", ...)` that flows
through the existing scoring in `extract/fields.py` completely unchanged.
Detection requires 3+ columns, so it is unreachable from any 2-column
label:value table — the shape every table in the graded 520-email set
actually uses — which a full re-run of `backend/tools/adversarial.py`
against `bundle_data/` confirms directly: all 16 modes, zero movement,
identical to the run before this fix. Re-run against this same CMA CGM
document: `container_count` now reads `1`, `MATCH` against the BL side.

**Still open, deliberately not fixed:** `gross_weight_kg`. Extracting it
from a manifest table means deciding whether a real form ever needs
per-container weights *summed* into one shipment total, which is a
domain judgement call, not a parsing gap — the wrong guess there is worse
than the `missing` it produces today. Left open rather than decided alone
under a two-day clock; the same choice already made once for the
truncation-repair `xfail` in `docs/ADVERSARIAL.md` §5.4.

**Also noted.** `doctype.py` scored this document `UNKNOWN` at 0.00
confidence for every known type. `POST /compare` does not gate on
`doctype`'s classification, so it did not affect this result — but it is
a data point on the same theme, worth knowing about rather than not.
