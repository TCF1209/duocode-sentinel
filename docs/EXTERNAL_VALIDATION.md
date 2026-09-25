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
under a two-day clock; the same kind of call `docs/ADVERSARIAL.md` §5.2
also leaves open, for the same reason. (§5.4, referenced here in an
earlier version of this page, was a different defect and was fixed later
the same day — see `docs/STATUS.md`'s 2026-09-24 entry.)

**Also noted.** `doctype.py` scored this document `UNKNOWN` at 0.00
confidence for every known type. `POST /compare` does not gate on
`doctype`'s classification, so it did not affect this result — but it is
a data point on the same theme, worth knowing about rather than not.

---

## Second round, 25 Sep 2026: five tests on real external data

One template was not enough, so the question was put properly: do the rules
hold on data the organisers' generator never produced? Five independent
tests, each run by one agent and then **re-run by a second agent before any
failure was believed** (84 of the 86 reported failures reproduced; the two
that were not re-run needed model calls the checker was not allowed to make). Only
small public files were fetched, from the sources below; they were used for
internal testing, kept outside the repository, and nothing from them is
committed or republished.

| Test | Source | Terms |
|---|---|---|
| Real carrier and industry forms | Blank official forms from Evergreen (.docx), Hapag-Lloyd, DHX, KLN, BIMCO, JSE (3); Maersk timed out | Public downloads, internal testing only |
| Real filled shipping documents | 14 shipping pages from RealDoc-Bench (Extend-AI, Hugging Face), taken from public NTSB dockets | Answers CC BY 4.0; documents internal only |
| Real values | India and Netherlands bill-of-lading samples (Trade-Database-Net, 2 × 1,000 rows); DCSA eBL v3 examples | CC BY 4.0 (tradedatabase.net); Apache-2.0 |
| Real email | 800 Enron emails (400 spam, 400 ham), 13,436 MaritimEmails (LREC 2026), 90 freight-forwarding emails | Research corpus; CC BY-NC 4.0; CC BY 4.0 |
| Real archived BLs and SIs | 16 OCR texts from the UCSF Industry Documents Library: P&O Nedlloyd, ACL, NYK, Columbus Line, Sea-Land, Mitsui OSK, Yang Ming and others, 1972–2002 | Read-only, internal testing |

### What held

**No real document was auto-decided wrongly.** Every comparison built on a
real document ended `NEEDS_REVIEW`: 66 of 66 on the filled carrier forms, 29
of 29 on the RealDoc-Bench scans, and every pair built from the archived BLs.
Zero false OK, zero false MISMATCH at case level.

That is the safety net holding, not the reader. Sentinel **cannot yet read
real form layouts**: on the six filled carrier forms, 0 of 42 fields were
read correctly (31 not found, 11 taken from the wrong box); on the 16
archived BLs, of 109 printed values 4 were read correctly, 87 escalated, 17
were taken from the wrong box and 1 raised a false alarm. Those wrong reads never reached a verdict, because
another field on the same document was always missing. The dominant cause is
a layout the generator never uses: a boxed form with the label above the
value.

Also held:
- **Values.** 16,000 of 16,000 real weights parsed in eight kilogram and tonne
  formats; 1,991 of 1,991 common company-suffix variants ("SDN. BHD." vs "SDN
  BHD", "CO.,LTD" vs "COMPANY LIMITED") matched; 140 real port names gave 140
  distinct keys, with no two different ports merged; 8,000 of 8,000 container
  counts built from real rows parsed.
- **Labels.** 52 of the 53 printed labels for the seven fields on eight real
  forms were recognised ("Consigned to the order of", "Notify Address (Carrier
  not responsible for failure to notify)").
- **Scans.** Every one of the 14 real scans was recognised as image-only and
  escalated. On 8 of them the optional vision transcript got 50 of 56 field
  slots right (30 of 35 printed values exact) for $0.017, which is still only
  advisory; the two misreads would have been false alarms.
- **Email.** 14,326 real emails, no crash, 0.22 ms each. None of the 400 Enron
  business emails and 4 of 13,436 chartering emails were routed to the BL
  check, and none of those 4 created a review item.

### Fixed in this round

Each of these was a confirmed way a real document could get a wrong value
past the rules. Only what survived three rounds of review is here (see below).

1. **Container counts written size-first or as a word.** "40HC x 3" and
   "40HC x 2" both read 40, so a BL one box short was cleared; "THREE X 40' HC"
   read 40. Now 3, 2 and 3, and only when that shape is the whole value.
2. **Labels that took the wrong field.** Reference and declared-value boxes
   printed beside the party boxes ("Shipper's Reference Number", "Consignee's
   Reference", "Shipper - reference", "Shipper's declared value", "Particulars
   furnished by Shipper"; exact wordings, like the CMA CGM fix above), the
   marks and container-number column ("MKS&NOS/CONTAINER NOS"), agent and
   endorsement boxes ("Carrier's agents endorsements (include agent at POD)"),
   an inland "Port of Final Delivery", fragments of form boxes the partial
   scorer found inside long synonyms ("NEGOTIABLE", "delivery.", "complete;"),
   "Port of :" (python-docx dropping a smart-tagged word, which took the
   loading port for whichever port the box was), and "Port of Unlading" /
   "Unloading Port", which fuzzy-matched the *loading* port.
3. **A valid PDF reported as corrupt.** A page whose labelled rows share no
   value column made the reader raise, and the operator was told "the file
   will not open". It now falls back to the column histogram.

**How they were checked.** All six local datasets and the adversarial harness
(on `bundle_data` and on a held-out seed) produce field-by-field identical
reports before and after; `submission.json` is byte-identical
(`1c08cd215b0ba4d3c607a7133212a6f9`); 86 new tests pin the behaviour, fixed
and unchanged, in `backend/tests/test_external_validation.py`.

**What was withdrawn, and why.** Every fix was reviewed old-against-new in
three rounds (weights alone: 339,835, then 2,018,889, then 2,680,137 realistic
inputs; containers and labels over hundreds of thousands more), with a second
agent confirming each regression. Each round found that part of the fix broke
real shapes the old code read correctly, and each such part was taken out:

- **Every weight change.** Wider parsers broke three-decimal tonnes ("24.500
  MT"), unit-first dual units ("KGS 12,000 LBS 26,455"), gross and net sharing
  one unit ("24.500/23.900 MT", clearing a 400 kg defect) and OCR spacing
  ("21,5 77 KGS"). Even the narrowest pound conversion failed: converting one
  document's pounds and not the other's turns the same weight, printed two
  ways, into a false defect, and a one-pound typo fell inside the 0.5 kg
  tolerance. Pounds need a comparison that sees both sides' units.
- **Summing mixed equipment** ("1x40HC + 2x20GP"): a value naming the same
  boxes twice, or a total and its breakdown, summed to double.
- **A cap on container counts**: it escalated real package counts ("1200CTNS").
- **General REF/PARTICULARS and UNLOADING rules, "Destination" and "Quantity"
  as ignored labels, and a minimum-letters guard on the fuzzy pass**: each let
  a later, wrong line win the field ("Unloading address" as the port; a
  wrapped "Shipper (Shipper's Reference / No.)" caption dropped; "Wt (kg)"
  losing to a per-container weight).
- **Accent folding in names**: it split bilingual names written on one line
  and names carrying a ™.

The shapes that exposed these are pinned as "read as before" tests.

**Pounds, a fourth attempt, and what shipped instead (25 Sep, afternoon).**
Pounds were then converted in `compare._weight_equal`, where both documents
are visible, and only when one side stated a single figure in pounds and the
other named kilograms or tonnes. The same old-against-new review, over 13.6
million pairs, confirmed six families of regression. All six came from one
cause: on a real form a unit printed beside a figure can belong to the next
box ("12,000 LBS" typed into the value of a "Gross Weight (KGS)" box with an
empty LBS box beside it), and one of them let a wrong BL clear. So pounds are
still not converted. What shipped instead converts nothing: when the two
weights agree only because one side is in pounds and the other in kilograms
or tonnes ("8,010 KG" against "8,010 LBS"), the field is `UNCOMPARABLE /
unit_differs` and the case is escalated to a person, whose reply draft asks the
customer which unit is right. Like `ocr_confusable`, it can only turn a MATCH
into a review. It never produces a MATCH or a MISMATCH, so a misreading costs
one review and cannot clear or condemn a BL. The review's pair families from
all four rounds, rerun old against new over 10,568,385 pairs, confirm it: no
pair changed except a MATCH turned into a review. 28,482 of those were false
clears now caught; the other 99,600 are layouts where a pound unit is printed
beside a kilogram figure, which a person should look at anyway. All six local datasets and the adversarial harness
are field-by-field identical; `submission.json` is byte-identical; 24 more
tests pin it.

### Found and deliberately left open

Recorded so they are not rediscovered as surprises. None of them affects the
graded data.

- **Reading real layouts** (the largest gap): label-above-value boxes,
  side-by-side boxes read as one label, terms-and-conditions pages whose
  sentences resolve as labels, Word cells holding several labels, values kept
  only in fillable PDF form fields, and OCR noise that fuzzy-matches a label.
  This is reader work, not rule work, and it is the next thing on the roadmap.
- **Weights:** pounds are still read at face value ("26,455 LBS" is 26,455).
  The same figure in pounds against kilograms is now caught and escalated
  (above), but the same weight printed in each unit ("12,000 KG" against
  "26,455 LBS") is a false MISMATCH, and a pound figure whose unit is not
  printed next to it is compared as a bare number. European notation ("12.500,00 KG" reads 12.5;
  "12,5 MT" reads 125 t); "24.500 KGS" against "24.900 KGS" falls inside the
  0.5 kg tolerance; tonne codes TNE, M/T and a bare T are read as kilograms.
- **Container counts:** mixed equipment ("1x40HC + 2x20GP") reads only the
  first group; a count read from the wrong column (a weight or a container
  serial read as thousands of containers).
- **Company names:** legal forms are dropped, so different legal entities
  merge ("JOHNSON & JOHNSON MEDICAL GmbH" vs "... SPA"; "... Holding B.V." vs
  "... B.V."), and non-ASCII letters are deleted ("Müller" equals "Möller").
  In the other direction, false alarms on "B.V." vs "BV", "SENDIRIAN BERHAD"
  vs "SDN BHD", a leading "THE", and an address on the same line after a comma.
- **Ports:** a five-letter parenthetical is taken for a UN/LOCODE ("MANILA
  (NORTH)" equals "MANILA (SOUTH)"); the same name with different codes
  merges ("Cartagena (COCTG)" vs "(ESCAR)"); false alarms on "Chennai" vs
  "CHENNAI, INDIA", aliases (Madras, Pusan), bare codes and US customs codes.
- **Labels:** "Destination" and "Quantity" can still take the port of
  discharge and the container count from an inland place or a package count;
  "Gross Weight (as declared by shipper)" resolves to the shipper; letters of
  a vertical banner ("N N") can fuzzy-match a party.
- **Classification of unfamiliar email.** The rules were written for this
  inbox and catch 12% of real 2000s spam; they send 0.75% of chartering
  emails to SPAM ("Dear Sir/Madam", "USD 3.2 million") and 0.9% to SI_REQUEST
  (fixture recaps with "Load Port:" lines). Almost all unrecognised mail fires
  no rule and is flagged for the model, which was not run in this test.

### What it means

On clean digital documents in the layouts it knows, Sentinel checks
automatically. On real stationery it does not yet read, it **triages**: every
case goes to a person with the reason, and none is cleared or condemned on a
value it could not read. The one-line version:

> We tested Sentinel on real forms from six carriers and industry bodies, 30
> real archived and scanned shipping documents and 14,000 real emails it had
> never seen. It can't read most real form layouts yet, and it never cleared
> or condemned a real document it couldn't read: every one went to a person.
> The same test found ways a real document could fool the rules. We fixed
> only what survived three rounds of old-versus-new review, and wrote the
> rest down, pounds first.
