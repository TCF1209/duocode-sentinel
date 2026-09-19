# Adversarial self-consistency — where the reader holds, and where it breaks

> Regenerated 2026-09-19 against the current working tree, which is **525
> passed and one `xfail`**. That xfail is not decoration: it is the live
> defect in §5.4, marked strict so that fixing it breaks the build rather
> than passing quietly. A second strict xfail recorded the address-line hole
> in §4.3 and did exactly that when the fix landed — it went red, the fix was
> confirmed, and the marker came off. Both runs are reproducible: re-running
> either command reproduces every count in §2 and §3 byte for byte, before
> those fixes and after them.
> Every number here comes from `runs/adversarial.json` and
> `runs/adversarial_holdout.json` as they stand now. An earlier snapshot was
> taken *between* two fixes and reported a `wrapped_value` row that the code no
> longer produces; it has been replaced rather than explained away, because a
> table a judge cannot reproduce is worse than no table.

```bash
.venv/Scripts/python.exe backend/tools/adversarial.py --data data/bundle  --out runs/adversarial.json
.venv/Scripts/python.exe backend/tools/adversarial.py --data data/holdout --out runs/adversarial_holdout.json
```

Both runs use the deterministic pipeline (`PipelineConfig(llm=None)`): no key,
no network, no sampling. A measuring instrument whose answer depends on a
third party's model temperature is not a measurement.

---

## 1. The method, and why there is no answer key

The harness never opens `data/_grader/`. It does not need to:

```
Extraction from the UNPERTURBED document is the reference.
Perturb the document so that a human would still read it identically.
Extract again. Any field whose compared value moved is OUR failure.
```

One half of each SI/BL pair is perturbed at a time and the other is staged
verbatim, because corrupting both sides identically hides the damage — two
documents misread the same way still agree with each other. `control_rewrite`
parses and re-renders without changing a character; a non-zero row there means
the apparatus is broken and every other row is suspect. It is zero in both
runs.

**Why this is a stronger instrument than scoring against labels.** The
organisers' scorer answers "did we get this draw right". We already know the
answer to that — 1.0000 on the dev set and on three held-out seeds
(`SCORING.md` §4.1) — and it is the less interesting question, for four
reasons.

1. *It cannot be tuned against — but it can be gamed, and the way matters.*
   There is nothing to fit: a rule written to please an answer key still fails
   self-consistency the moment the wording changes, so no amount of reading
   the labels improves this number. It does have one degenerate optimum, and
   the scope note above names its mechanism: a field the baseline never
   extracted is excluded, so a reader that extracts *less* scores better on
   every column here. `unseen_labels` is that optimum in miniature — perfect
   on every safety column precisely because 1,100 fields are simply lost
   (§5.3). Read these columns together with the recall the run still has, not
   on their own.
2. *It generates its own population.* The graded set contains 46 defect
   emails. This harness measures 16 perturbation modes over 188 documents —
   20,496 field reads — and then does the whole thing again on a held-out
   seed, for 18,704 more.
3. *It separates failures a score merges.* Losing a field and escalating is a
   **good** outcome — recall lost, trust kept. Quietly reading a different
   value and auto-deciding on it is the expensive one. An accuracy number
   cannot tell those apart; the columns below are built to.
4. *It tests the thing the score cannot reach.* Four draws from one generator
   share one label vocabulary and one set of renderers. Perturbation is the
   only evidence we have about wording and layout the generator never emits,
   which is what an ops inbox is full of.

### Scope of each run

| | dev bundle (seed 42) | held-out (seed 20260922) |
|---|---:|---:|
| `.txt` SI/BL pairs | 94 | 86 |
| perturbed documents per mode | 188 | 172 |
| field reads measured per mode | 1,281 | 1,169 |
| perturbed documents in total | 3,008 | 2,752 |

The measured field reads are 1,281 of a possible 1,316 (188 × 7) because a
field the baseline never extracted has no reference to move away from and is
excluded by design — counting it would flatter or damn the harness at random.

### Reading the columns

`ok` / `chg` / `lost` and `silent` / `escal` are counted **per (document,
field)**. `falseD`, `maskD`, `escGain` and `decChg` are counted **per perturbed
document**, i.e. per case the pipeline decided.

| Column | Meaning |
|---|---|
| `ok` | value canonicalises to exactly what the unperturbed document gave |
| `chg` | extracted, but a different compared value — a misread |
| `lost` | no longer extracted at all |
| `silent` | value changed and the case was still auto-decided ← the bad one |
| `escal` | value moved or vanished and a human was asked ← the safe one |
| `falseD` | we reported a defect that is not in the document |
| `maskD` | a real defect stopped being reported, unescalated |
| `escGain` | auto-decided before, `NEEDS_REVIEW` after |
| `decChg` | status, defect set or review reason differs from baseline |

---

## 2. Results — dev bundle, seed 42

| perturbation | family | ok | chg | lost | silent | escal | falseD | maskD | decChg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `control_rewrite` | control | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `unseen_labels` | unseen label wording | 181 | 0 | 1100 | 0 | 1100 | 0 | 0 | 168 |
| `reflow_indented` | reflowed value | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `reflow_next_line` | reflowed value | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wrapped_value` | wrapped value | 1198 | 83 | 0 | 74 | 9 | **0** | **1** | 1 |
| `punct_no_colon` | punctuation drift | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_em_dash` | punctuation drift | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_nbsp` | punctuation drift | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_double_space` | punctuation drift | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_tab` | punctuation drift | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `case_upper_labels` | case and spacing noise | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `case_lower_labels` | case and spacing noise | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `label_inner_spaces` | case and spacing noise | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `label_indented` | case and spacing noise | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `ocr_confusions` | OCR-style confusion | 80 | 1181 | 20 | 982 | 219 | **151** | 0 | 168 |
| `reordered_fields` | reordered fields | 1281 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

`escGain`: 168 for `unseen_labels`, 17 for `ocr_confusions`, 0 elsewhere.

## 3. Results — held-out seed 20260922

Nothing was tuned between the two runs; the same working tree produced both,
and re-running either command reproduces its file byte for byte. A fix that
only works on the draw it was written against is not a fix.

| perturbation | family | ok | chg | lost | silent | escal | falseD | maskD | decChg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `control_rewrite` | control | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `unseen_labels` | unseen label wording | 166 | 0 | 1003 | 0 | 1003 | 0 | 0 | 152 |
| `reflow_indented` | reflowed value | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `reflow_next_line` | reflowed value | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wrapped_value` | wrapped value | 1074 | 95 | 0 | 80 | 15 | **0** | **0** | 0 |
| `punct_no_colon` | punctuation drift | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_em_dash` | punctuation drift | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_nbsp` | punctuation drift | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_double_space` | punctuation drift | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `punct_tab` | punctuation drift | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `case_upper_labels` | case and spacing noise | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `case_lower_labels` | case and spacing noise | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `label_inner_spaces` | case and spacing noise | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `label_indented` | case and spacing noise | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `ocr_confusions` | OCR-style confusion | 106 | 1058 | 5 | 949 | 114 | **150** | 0 | 154 |
| `reordered_fields` | reordered fields | 1169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

`escGain`: 152 for `unseen_labels`, 4 for `ocr_confusions`, 0 elsewhere.

The held-out draw agrees with the dev draw on the shape of every finding:
layout and punctuation modes are clean, unseen wording costs recall and
nothing else, OCR noise invents defects at a comparable rate (151/188 = 80% of
dev documents, 150/172 = 87% held out — the held-out draw is the worse of the
two, not the same), and the truncation repair holds. Two findings do not
replicate, and neither is smoothed over here.

1. The masked discrepancy in `wrapped_value` is 1 on dev and 0 here — see
   §5.2: it needs a particular pair of party names to be drawn, and this seed
   did not draw one. Its absence is luck, not immunity.
2. `escGain` for `ocr_confusions` is 17 on dev and 4 held out. So the second of
   the "two smaller findings" in §5.1 is a property of the dev draw, not of the
   pipeline: on this seed OCR noise almost never converts an auto-decision into
   an escalation — it converts it into a `MISMATCH`. Read 17 as one draw's
   number, not as a rate.

---

## 4. What is fixed, and by which change

> The "before" figures were produced by re-running the harness against a
> **scratch copy** of `backend/` with one guard disabled, not by quoting the
> superseded snapshot. Same data, same command, one line changed, so the
> attribution is measured rather than remembered.

### 4.1 Punctuation drift and indented forms — `readers/rows.py`

Two guards, added together: `_alt_split()`, which accepts an em dash, a tab or
a wide gap as a label/value separator *only when the left-hand side resolves to
one of the seven fields*; and the exception that lets an indented line start a
field when its label resolves, because a form that indents its whole field list
is still a form.

Both guards are the same bet: that `labels.resolve()` says no to an address
line. Read §4.3 before believing the rows below — it did not always say no,
and none of the rows below could tell.

| mode | before: ok / chg / lost | before: escal, falseD, decChg | after |
|---|---|---|---|
| `punct_no_colon` | 0 / 0 / **1281** | 1281, 0, 168 | 1281 / 0 / 0, all counters 0 |
| `punct_em_dash` | 0 / 0 / **1281** | 1281, 0, 168 | 1281 / 0 / 0, all counters 0 |
| `label_indented` | 0 / 0 / **1281** | 1281, 0, 168 | 1281 / 0 / 0, all counters 0 |

Three modes went from reading *nothing on the page* to reading everything.
Worth stating plainly: the old behaviour was **safe** — all 1,281 lost fields
escalated, none was misread, no defect was invented — but an inbox where **all
188** documents land in the review queue because a carrier prints
`Port of Loading — NANTONG, CHINA` is an inbox nobody uses. The 168 in the
`decChg` column is the number *newly* escalated; the other 20 are the 10 `.txt`
pairs already sitting at `NEEDS_REVIEW` at baseline, which had no
auto-decision left for the perturbation to take away. §5.3 states the same
figure the right way round.

Equally worth stating: `punct_nbsp`, `punct_double_space`, `punct_tab` and
`label_inner_spaces` were already clean before this change, because they keep
the colon. The fix earns three rows, not seven.

### 4.2 Wrapped party names — the truncation repair in `compare.py`

A party name too long for its column wraps, and the reader cannot tell that
continuation apart from the address block that normally follows a name:

```
Shipper (Principal or Seller): APRIL FINE PAPER TRADING
    (MIDDLE EAST) FZE
```

`_repaired()` fires only when one side's canonical value is a strict
whole-word prefix of the other's, completes the short side from a line in
**that document's own text**, and accepts the completion only if it reproduces
the other side's canonical form exactly. That last condition is what stops it
inventing agreement in the ordinary case: when the two documents genuinely
name different parties, the line it reads is an address block, the completion
fails and the mismatch stands.

Two things about that paragraph are worth stating rather than leaving to a
reader who checks. First, "from that document's own next line" would be the
claim we want, and it is not what the code does: `compare.py` locates the
value with `text.find(value.raw)` — the first textual occurrence of the raw
string anywhere in the document — and reads the line after *that*, not after
the span the evidence locator points at. Second, the gap between those two is
a live defect, not a theoretical one, and it is recorded in §5.4.

| `wrapped_value`, dev bundle | before | after |
|---|---:|---:|
| false discrepancies | **64** | **0** |
| decisions changed | 65 | 1 |
| masked discrepancies | 1 | 1 |
| fields read: ok / chg / lost | 1198 / 83 / 0 | 1198 / 83 / 0 |
| silent wrong values | 74 | 74 |

The last two rows do not move, and that is not a defect in the table. The
repair lives in the comparison, not in the reader: the extractor still hands
back the truncated `APRIL FINE PAPER TRADING` with its evidence intact, and the
comparison recognises the truncation for what it is. The per-field columns
measure what the parser read off the page; the decision columns measure what
the system did about it. Only the second is what reaches an operator — and of
those, only the false discrepancies went to zero: 64 → 0 on dev, and 0 on the
held-out seed as well. One decision still changes on dev and one real defect is
still masked, which the table three lines above prints as `1` and `1`. Both are
the same single case, `email_145`, and §5.2 is about why it stays.

### 4.3 The guard in §4.1 leaked — found by review, closed in `labels.py`

§4.1 rests the entire safety case for the wide gap on `labels.resolve()`
refusing an address line. It refused most of them, not all, and this document
asserted the guard without qualification until an adversarial read of it
checked. The hole was found by reading the code against the claim, **not** by
a harness row — for the reason in §6.

`resolve()` skips its fuzzy pass for a *query* shorter than eight characters,
but nothing stopped a short *synonym* matching inside a long query. `POL`
scores 90 against `METROPOLITAN` under rapidfuzz's `WRatio`, over the cutoff of
88, because `WRatio` folds in a partial-ratio component as soon as one side is
about 1.5× the other. Measured against the tree as it stood before the fix:

```python
>>> split_label_value("43-45 METROPOLITAN ROAD    ENFIELD NSW 2136")
('43-45 METROPOLITAN ROAD', 'ENFIELD NSW 2136')   # resolved: port_of_loading
```

`NAPOLI CENTRALE` and `POLK STREET 12` resolved to `port_of_loading` the same
way and `PODIUM TOWER` to `port_of_discharge`; the same trap was waiting in
ACROPOLIS, SEVASTOPOL and INTERPOL. The cost is not a lost read but an
invented one. `chunks_from_lines()` lets an indented line start a field when
its label resolves, so an address block stopped being a continuation of the
party above it:

```
Shipper: ACME PAPER PTE LTD
    43-45 METROPOLITAN ROAD    ENFIELD NSW 2136
    AUSTRALIA
```

read as `Shipper = ACME PAPER PTE LTD` plus a second chunk labelled
`43-45 METROPOLITAN ROAD`, offering `ENFIELD NSW 2136 / AUSTRALIA` as a port
of loading — a confident piece of nonsense competing with the real port line,
which is precisely what the "an address line with a wide gap is not a field"
block of `backend/tests/test_rows_separators.py` exists to prevent and is the
one shape that block did not cover.

Closed in `labels.py` rather than `rows.py`, because the leak is in resolution
and every caller of `resolve()` shared it: `_MIN_FUZZY_SYNONYM_CHARS = 6` drops
the three abbreviation synonyms — `POL`, `POD`, `G.W.` — from the fuzzy pool.
They are still matched letter-for-letter by pass 1 and with a word boundary by
pass 2, so `POL: SINGAPORE`, `POL    SINGAPORE`, `Load Port    SINGAPORE` and
`TOTAL GROSS WEIGHT — 118,270 KG` all still read. While the hole was open it
was pinned as a **strict** xfail; the fix turned it red, the fix was confirmed,
and the marker came off. `test_an_address_containing_a_port_abbreviation_is_not_a_field`
is a plain passing test now, and it also asserts that `POL` and `POD` still
resolve, because that is the half of the change that could have cost us
something.

**The prune had a cost, and a second review caught it.** Of the three keys it
drops, only two had the pass-2 rule this paragraph claims: `POL` and `POD`
appear as alternatives in the port rules, and `G.W.` had nothing — the fuzzy
pass was its only resolver. So `G.W. (KGS)`, `TOTAL G.W.` and
`G.W. 毛重(KGS)` silently began resolving to nothing, while the bare `G.W.`
went on matching by pass 1 and the test that was supposed to guard the
invariant checked only that bare form. `DATA_NOTES.md` §2b records that every
weight label in this set carries exactly that kind of parenthetical, so the
regressed spellings are the realistic ones. Fixed by giving the abbreviation
the rule the claim assumed it had — `\bG\s*W\b`, checked against every label,
value and text line the readers produce across all four datasets and matching
none of them — and `test_every_decorated_spelling_of_the_weight_abbreviation_resolves`
now pins the family a spelling at a time.

**And the prune raises the price of this class without ending it.** `WRatio`
still scores any pool key at ~90 against a query 1.5× its length containing
it, so `12 SHIPPERTON LANE` resolves to `shipper` and `LOAD PORTLAND AVENUE`
to `port_of_loading` today. Six characters is a threshold on the same
continuum as the cutoff itself. The principled fix — require the match to fall
on word boundaries — is unavailable here, because the manglings this pass
exists for are precisely keys glued to other characters
(`Total No. of Containersm` scores 97.8). This residual is open and unmeasured.

No row in §2 or §3 moved, and no row in §2 or §3 is evidence about this either
way: the harness cannot construct the input that triggers it. That blind spot
is the last item in §6, and it outlives this fix.

---

## 5. What is still open

### 5.1 OCR character confusion — 151 of 188 documents invent a defect

Swapping a single character per value — `O`/`0`, `I`/`1`, `S`/`5` and `B`/`8`
in both directions, plus a one-way lowercase `l` → `1` (`_OCR_MAP`,
`backend/tools/adversarial.py`) — is the worst row in the table by a distance:
1,181 of 1,281 field reads change, 982 of them silently, and 151 of the 188
perturbed dev documents (150 of 172 on the held-out seed) end in a `MISMATCH`
reporting a defect the shipment does not have. `NANTONG, CHINA` becomes `NANT0NG, CHINA`, a human reads it as Nantong,
and exact-equality comparison — correctly, by `DECISIONS.md` §D2 — calls it a
different port.

**The honest caveat.** This perturbation is not like the others. Every other
mode preserves the characters of the value, so a changed reading is
unambiguously our fault. This one edits the value itself. The document now
genuinely says `NANT0NG`, and no system can distinguish "the scanner misread a
digit" from "the document really says that" without a second source of truth.
Fuzzy value matching would appear to fix it and would be the wrong trade: the
entity pools hold `APRIL FINE PAPER TRADING` beside
`APRIL FINE PAPER TRADING (MIDDLE EAST) FZE`, and any threshold loose enough to
forgive one swapped glyph swallows a real planted defect. So this row is
reported, not closed. It is a worst case for *this* mode — `_ocr_swap`
alters at most one character per value — not an upper bound on character-level
noise in general; two swaps per value would cost more. It is not a to-do item
with an obvious fix.

**The mitigation that already exists.** Our own OCR never feeds a decision.
`readers/scan.py` transcribes an image-only PDF *for the reviewer only*: it
never sets `doc.readable`, never writes `doc.text` and never touches
`doc.chunks`, so the case still ends in `NEEDS_REVIEW` with reason
`unreadable`, and the transcript arrives as context attached to that
escalation. The failure mode measured here therefore requires a document that
was OCR'd *before it reached us* — a scan someone else converted and sent as
text. That is a real scenario in an ops inbox, which is why the row stays in
this document, but it is not a path our own pipeline can walk into.

Two smaller findings inside the same row, and neither is as good as it first
looks.

**`container_count` is misread far more often than it is lost.** The triple is
72 unchanged / **90 changed** / 20 lost on dev, and 102 / 59 / 5 held out. The
20 losses are the safe outcome — a missing number escalates, per rule 4 in
`CLAUDE.md` — but the field is misread 90 times, 4.5× more often than it is
safely lost on dev and nearly 12× on the held-out draw. The mechanism is
not "the count stops parsing": `container_count` takes the first number in the
value, so `10 x 20'FCL` → `I0 x 20'FCL` leaves a bare `0`, out of range, and
the read is lost — but `1 x 40'HC` → `I x 40'HC` leaves the *box size* as the
first number and the count comes back as **40**. That is a confident wrong
integer on a compared field, and it is the common case here, not the rare one.

**The escalation gain does not replicate.** 17 dev documents gained an
escalation they did not have before, but only 4 on the held-out seed (§3). It
is one draw's number.

### 5.2 One masked discrepancy in `wrapped_value` — unfixable by this repair

`email_145`, the BL's shipper:

```
SI  : SHIPPER: APRIL FINE PAPER TRADING
BL  : Shipper (Principal or Seller): APRIL FINE PAPER TRADING (MIDDLE EAST) FZE
```

That is a real planted defect — two different companies, exactly the pair
`DATA_NOTES.md` §4 warns about. Wrapping the BL's value truncates it to
`APRIL FINE PAPER TRADING`, which is precisely what the SI says, and the case
flips `MISMATCH ['shipper']` → `OK`.

The repair cannot catch this **by construction**. Its first guard is

```python
if not si_key or not bl_key or si_key == bl_key:
    return si_value, bl_value
```

— when both sides already canonicalise to the same key there is nothing to
repair, so it returns before looking at either document. Reaching this case
would mean re-examining pairs that already agree, on the suspicion that the
agreement is an artefact of truncation: every value whose next line continues
it would have to be re-read and re-compared, which turns a narrow repair into a
second extraction pass and puts a new class of false discrepancy on the table
(a value that legitimately ends where it ends, followed by an address line that
happens to extend it into the other side's name).

It is one case in 188 on dev and none in 172 on the held-out seed, and the
trade is real, so it is recorded here rather than fixed quietly. The mitigation
if we do take it on: the reader, not the comparison, should mark a value it
truncated at a wrap, and the comparison should refuse to auto-decide a *match*
that depends on a truncated value — escalate, do not guess.

### 5.3 Unseen label wording — safe, and still useless

`unseen_labels` loses 1,100 of 1,281 fields (1,003 of 1,169 held out), escalates
every one of them, and invents nothing: zero false discrepancies, zero silent
wrong values, 168 of 188 documents converted from an auto-decision to
`NEEDS_REVIEW`. This is the designed behaviour and it is the right failure
direction, but it is also the measured case for the LLM fallback: with no key,
a forwarder whose template says `Shipped By` instead of `Shipper` sends its
entire inbox to a human. The assisted path (`extract/llm.py`) is wired and is
meant for exactly this, but every number on this page is the deterministic
pipeline, so none of them describes what it recovers.

### 5.4 The truncation repair can mask a real discrepancy — found by review

§4.2 says the repair "cannot invent agreement". In the ordinary case that is
true, and the harness agrees: false discrepancies went to zero and stayed
there on both draws. But there is a case where it does invent one, and it
comes from the mechanism named in §4.2 — `text.find(value.raw)` locates the
**first** textual occurrence of the value, not the span the evidence locator
points at.

In this dataset the consignee and the notify party are frequently the same
company, so a document can carry the same first line twice with *different*
continuations:

```
Consignee:    APRIL FINE PAPER TRADING (MIDDLE
                EAST) FZE
Notify:       APRIL FINE PAPER TRADING (MIDDLE
                EAST ASIA) PTE LTD
```

Repairing the notify party reads from the consignee's block three lines above,
completes it to `...(MIDDLE EAST) FZE`, and reports `MATCH` against a BL that
says exactly that — while the document's own notify party is a different
company. A real discrepancy is masked, and unlike §5.2 this one is
manufactured *by* the repair rather than missed by it.

It is pinned as a strict `xfail` at
`backend/tests/test_compare_wrap.py::test_a_continuation_is_read_from_the_block_the_evidence_points_at`,
so it goes green and loud the day it is fixed. Two things bound it. It has
fired **zero** times across all four datasets — instrumenting `_extend` over
520 emails shows the prefix relationship hit once and the repair applied not
at all. And the fix is known and small: anchor `_extend` on the evidence
locator instead of on `text.find`, which is what the locator is for.

The harness cannot see this either. It wraps one value at a time, so it never
builds the two-blocks-same-first-line shape the defect needs.

---

## 6. Limits of the harness itself

**It perturbs `.txt` only.** 94 of the 220 `BL_COMPARISON` emails in the dev
bundle — 94 of the 124 emails carrying two attachments. The other 30 pairs
(13 `pdf+pdf`, 8 `docx+xlsx`, 7 `xlsx+xlsx`, 2 `pdf+txt`) are untouched, so the
PDF coordinate reader, the `.docx`/`.xlsx` readers and the markitdown fallback
have **no perturbation evidence at all** — and the PDF reader is the one
carrying the most delicate logic in the codebase (`DECISIONS.md` §D3). This is
deliberate rather than lazy: a text file *is* its own layout, so "put the value
on the next line" means exactly that, whereas rewriting a PDF's word
coordinates would simulate our own reader's input and a harness that tests a
mock is worth nothing. Closing the gap needs real re-rendered files.

**It measures the deterministic pipeline only.** `llm=None`, by default and for
both runs above. The model layer is a fallback, so the rule reader has to be
safe on its own; but it also means these numbers do not describe the assisted
path, and `unseen_labels` in particular would read very differently with it.

**Each mode changes every field at once.** A real template varies one label or
one separator; `_rewrite()` applies the change to all seven blocks in the
document. Each row is therefore a worst case for that mode, not a forecast of a
realistic document.

**A self-description bug, recorded not fixed.** The section comment above
`UNSEEN_LABELS` (`backend/tools/adversarial.py`, the banner at §1 of that
file — not a docstring) states that none of the seven labels appears in
`labels.SYNONYMS`. Six do not. `Final Destination Port` is not in the table
literally, but `labels.resolve()` reaches it on the third pass — fuzzy `WRatio`
at cutoff 88 against the synonym `Destination Port` — and returns
`port_of_discharge`. That is exactly why `port_of_discharge` shows 181/181
unchanged on dev and 166/166 held out while every other field is lost. So only
**6 of 7** labels are genuinely unseen, and the `unseen_labels` row understates
the finding by one field: with a seventh truly unknown label the loss would be
larger and the escalation count higher. The direction of the error matters —
it makes us look better than we are, so it is written down here.

**It cannot put a wide gap in an address line, so the clean punctuation rows
are silent on the risk §4.1 introduced.** `_Block.tail` — every continuation
line under a label, which is where address blocks live — is carried verbatim
by all sixteen modes and never rewritten (`_Block`,
`backend/tools/adversarial.py`). Only the label line is ever touched. All
sixteen modes do reach `_alt_split()` — 512 calls each, measured by
instrumenting it — and in every mode nine non-label lines match
`_ALT_SEPARATOR` and are turned away by `resolve()`; but they are invoice and
packing-table headers (`Description   Qty   Unit Price   Amount`), never an
address line. So the guard is exercised, and never on the shape that breaks
it. The baseline supplies no counter-example either: of
the 364 indented lines in the dev bundle's `.txt` attachments (336 held out),
**zero** carry a separator `_alt_split()` would act on. That is why
`punct_no_colon`, `punct_em_dash`, `punct_nbsp`, `punct_double_space`,
`punct_tab` and `label_indented` all read a clean 1281/0/0 while the guard
those rows appear to vindicate was quietly splitting addresses (§4.3). The
rows are not wrong; they are **silent**. Closing that hole in `labels.py` did
not move a single counter in §2 or §3 — re-run and diffed — which is the
proof, not the reassurance: a measurement that cannot move when the bug is
fixed could not have seen the bug. Generalised, and this outlives the fix: a
clean row is evidence about the perturbation that produced it and nothing
else.
