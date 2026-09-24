# The final-round deck — slide by slide, against the rubric

Written 24 Sep 2026 for Pitch Day on the 26th. Every number below was
re-measured that day (`STATUS.md`, session 9) and its source is in the
table at the end.

**The deck file is [`Sentinel-final-pitch.pptx`](Sentinel-final-pitch.pptx)
(and a `.pdf` of it beside it)** — ten slides: the nine below plus a dark
divider for the demo beat, so the running order is on screen while the
browser is. It is generated from this document's content by
`scripts/build_pitch_deck.ps1`, which drives PowerPoint itself; the
screenshots it embeds are under `docs/img/pitch/` and come from a
model-tier run over the full inbox on 24 Sep (46 / 20 / 454, 6 model
calls). Speaker notes carry the *Say* paragraphs. When a number changes,
change it here first, then in the script, then rebuild.

**Built for five minutes plus questions.** The Finalist Portal's actual
limit was not known when this was written. Below each beat is its cost in
seconds; the *Cuts* section at the end says what goes for three minutes
and what comes back for eight.

## The three rules the deck is built on

The judges' own instructions, from the rubric PDF, and what each one does
to the deck:

1. **"Score each criterion independently."** One slide per criterion, in
   the rubric's own order, so a judge filling the score sheet finds the
   evidence for row 3 on slide 3.
2. **"Do not reward the same evidence twice."** Every fact appears on
   exactly one slide. The 1.0000 is on the evidence slide and nowhere else;
   the 168 → 2 is on the AI slide and nowhere else. Repeating the best
   number does not score it again — it costs the seconds another criterion
   needed.
3. **"Base scores on what is demonstrated, submitted or clearly
   explained."** Anything we cannot show or point at in the repository is
   not on a slide.

The rubric: Technical 70 — End-to-End Functionality 25, Architecture &
Scalability 15, Technology Integration 15 (marked *TBC* in the guide — check
the portal), Engineering Quality & Robustness 15. Product & Impact 30 —
Solution Effectiveness & User Value 10, User Experience & Differentiation
10, Impact & Future Potential 10.

---

## Slide 1 · Sentinel — every answer comes with its evidence *(0:00–0:15)*

**On the slide:** the name, the tagline, DuoCode, the two URLs. One line
under the tagline:

> A document checker that is confidently wrong is worse than no checker —
> because nobody goes back and looks.

**Say:** "We're DuoCode. Sentinel is built on one rule: it never reports
anything it cannot prove. Everything in the next five minutes is evidence
for that sentence."

**Scores:** nothing yet — this is the hook. It sets up criterion 6
(differentiation) without spending it.

## Slide 2 · The problem, and the fourth case *(0:15–0:40)* → criterion 5

**On the slide:** the organisers' own four capabilities — Classify ·
Extract · Compare · Ask for help — as four boxes; under them, the line the
mentor asked for: *why we built it* — a documentation clerk does this by
hand, about 4 minutes per SI/BL pair and 20 seconds to triage each email
(a conservative estimate, labelled as one), and a missed field becomes a
correction, a delay, rework. Then the desk's three pains from the problem
statement: finding the right emails takes time; manual comparison is
repetitive and easy to get wrong; the same field is printed differently on
the two documents.

**Say:** "Why we built it: a shipping desk gets five kinds of mail in one
inbox, and for every document check a person compares the Shipping
Instruction against the draft Bill of Lading — seven fields, by hand. At a
conservative estimate that's about four minutes a pair and twenty seconds
to triage each email; this inbox alone is a day and a half of desk work.
Miss one field and it's a correction, a delay, rework. And there's a fourth
case the statement names: sometimes the check *can't* be done — an
unreadable scan, a blank field, the wrong document. That has to reach a
person with the reason, not be guessed at. Sentinel does all four."

**Scores:** Solution Effectiveness & User Value — problem-solution fit,
in the organisers' own words.

## Slide 3 · What it does, end to end *(0:40–1:05)* → criterion 1

**On the slide:** one screenshot of the run page over the real inbox, and
four numbers beside it — **520 emails · 46 mismatches · 20 sent to a person,
with the reason · 12.7 s on a free container.** Below, the four steps a
desk actually takes (the mentor: "the pitch shows the pipeline, not how a
person uses it"): *run the inbox · open a flagged case · confirm it, correct
a single field, or re-upload the corrected document · send the drafted
reply.*

**Say:** "This is the whole inbox, live on Render and Vercel — not a
sample, the organisers' 520 emails. Every email classified, every document
pair compared, every case Sentinel can't decide sent to a person with the
reason attached. Thirteen seconds. And this is how a desk uses it, four
steps: run the inbox, open a flagged case, confirm it or correct one field
or re-upload the corrected document, send the drafted reply."

**Scores:** End-to-End Functionality. Do not say the accuracy here — that
is slide 6's evidence.

## Slide 4 · How it decides *(1:05–1:30)* → criterion 2

*Trimmed after the mentor session to buy slide 7 its extra fifteen seconds:
keep the diagram on screen and say only the two choices and the gate
sentence; the rest of the "Say" below is the eight-minute version.*

**On the slide:** the six-stage diagram from `ARCHITECTURE.md` — Classify →
Intake → Extract → Compare → **Gate** → Decide — with the gate drawn as the
one stage that can veto the one before it. Three decisions as three short
lines, each with its cost: *labels match by meaning, values exactly — never
a similarity score* · *rules first, model second, and it records which
answered* · *one stateless pipeline library; the CLI, the API and the tests
run the same code*. A small footer: *store: one class, one file — Postgres
is a one-file change; one worker on purpose; cost does not scale with
volume.*

**Say:** "Six stages, one direction. Two choices carry the design. Values
are compared exactly after canonicalising, never by similarity — a
threshold loose enough to forgive a scan artefact also merges two real
companies, and the data has those. And the gate after the comparison can
overrule it: a value we cannot find again in the document it was read from
is never reported as a discrepancy — it becomes a question for a person.
The pipeline is a stateless library with no web or database in it, which is
also the scaling story: throughput is more copies of it; the state sits
behind one class in one file."

**Scores:** Architecture & Scalability — trade-offs stated with their
reasons, and a realistic scaling approach the code supports.

## Slide 5 · Where the AI is, and why it is aimed *(1:30–2:10)* → criterion 3

*The mentor's rule for this slide: never say "we use less AI". Say the AI
is reserved for the cases the rules can't handle — and the system performs
just as well.*

**On the slide:** three rows — **classify** *(an email the rules can't
separate)* · **read** *(a label the table has never seen)* · **see** *(a
scanned page with no text layer)* — each with the model (gpt-5-mini,
structured output) and the rule it obeys: *nothing it returns is adopted
until it is found again in the document.* One measured pair, large:
**168 → 2** *(cases forced to a human on wording we invented, rules alone vs
rules + model — false discrepancies 0 both ways)*. A footer: *$0.0013 per
document at the published rates · cached · $2 ceiling per run · on this
inbox: 0 classifier calls, 0 extractor calls, 6 scans read for the reviewer.*

**Say:** "A judge in the first round said we use AI less than most teams.
True, and measured. On this inbox the rules answer all 520 and the scoring
is all-or-nothing per email, so a model that is *almost* always right costs
places. The model goes only where the rules admit they can't read: an
ambiguous email, a label we've never seen, a scanned page. On documents
with wording we invented, rules alone send 168 of 188 cases to a human;
with the model, two — and false discrepancies stay at zero, because
nothing the model says is adopted until we find it again in the source.
You'll see both in the demo: a scan read out for the reviewer, and four
unknown labels read on request."

**Scores:** Technology Integration — deep, specific, craftsmanship shown
rather than claimed. This slide is the answer to the judges' feedback;
land it and move on.

## Slide 6 · How we know it holds *(2:10–2:45)* → criterion 4

**On the slide:** four short blocks. *Not memorised:* 1.0000 on four
datasets, three from seeds we never developed against — 225 defects, exact
field set, 80/80 escalations. *Attacked ourselves:* 16 kinds of damage,
3,008 perturbed documents, 20,496 field reads, no answer key — 13 modes at
zero movement; silent wrong values 982 → 0. *A real carrier's form:* CMA
CGM's SI template — one bug found and fixed. *Engineering:* 646 tests, 0
failing, CI on every push, a container that runs as a non-root user with no
secret baked in. And the honest box, in a different colour: **what we
haven't fixed** — `email_145`, one masked discrepancy in 3,008, the guard
would cost more than the gap.

**Say:** "A perfect score on the dataset you were handed proves you didn't
memorise it. It doesn't prove the reader works. So we attacked our own
reader — three thousand perturbed documents, sixteen kinds of damage, no
answer key. Thirteen of sixteen don't move. OCR noise used to produce 982
silently wrong values; it produces zero now, because a damaged number is
refused instead of parsed short. Then we fed it a real carrier's template
from outside the generator, and it found a bug we fixed the same day. And
the one we haven't fixed is on the slide, because a defect we hide is worse
than one we miss."

**Scores:** Engineering Quality & Robustness. The 1.0000 lives here and
only here.

## Demo *(2:45–4:10)* → criteria 1, 3, 6

Not a slide. The running order is in `PITCH_DAY.md`: the run with the model
tier on → the pattern group → a mismatch case with the source line under
every value → the scan case with its transcript and the review panel →
`/compare` with unknown labels, off then on.

**Say, at the mismatch case:** "Under every value — the line it was read
from. A reviewer never has to open the source document to trust this."

**Say, at the scan:** "No text layer, so Sentinel did not decide. But the
model read the page for the reviewer — seven fields, and it says which ones
it couldn't read rather than guessing. The case stays in review; the person
decides, per field."

**Scores:** End-to-End (it works, live, in front of them); Technology
Integration (the model doing its two jobs); User Experience &
Differentiation (the evidence line, the per-field review, the pattern
groups — the things a reviewer actually uses).

## Slide 7 · What makes it different *(4:10–4:40)* → criterion 6

*Rebuilt after the mentor session: "at the top-ten stage everyone meets
the brief — emphasise the special things."*

**On the slide:** five numbered features, left; the scan read-out capture,
right. **1 Correct by re-upload** — the sender re-sends a fixed SI or BL,
you attach it on the case, the same check runs again, the old answer stays
on record. **2 Scans read out for the reviewer** — an image-only PDF still
goes to a person, but with the seven fields already read by the model,
marked as evidence, not a verdict. **3 Shipper history on the field** —
correcting a field shows how often this shipper was wrong on that same
field before. **4 The original, one click away** — every value carries its
line and the source document opens beside it. **5 A reply drafted from the
corrected outcome** — not the stale one; a person still presses send. One
line under them: *Every flag carries the line it came from; every
escalation carries the reason and what to do about it.*

**Say:** "At this stage everyone meets the brief, so here is what the
others mostly don't have. The sender re-sends a fixed document — you
re-upload it on the case, the check runs again, and the old answer stays on
record. A scan still goes to a person, but already read out by the model.
Correcting a field shows this shipper's history on that field. The original
document is one click from every value. And the reply is drafted from what
the reviewer decided, not the stale answer."

**Scores:** User Experience & Differentiation. Thirty seconds now, not
fifteen — the demo showed two of the five; this names all of them.

## Slide 8 · Impact, and what comes next *(4:40–4:58)* → criterion 7

**On the slide:** the adoption path in one line — *one desk first (the
inbox already carries four desk codes), beside the existing check, until
the measures hold* — and a three-row measures table: escalation rate
(9.1% today, all correct) · false alarms (0 of 46; 0 across 16 modes) ·
reviewer minutes per escalation (*the pilot's first new measurement*). Next
three, in order: per-desk rules · reviewer corrections feed the label table
· the database, one file.

**Say:** "520 emails and 124 document pairs is, at a conservative estimate,
about eleven hours of desk work. Sentinel does it in thirteen seconds and
every decision on that inbox was a rule, so it costs nothing to run — cheap
because the model is aimed, not because it's absent. The first deployment
is one desk, with three numbers we'd watch; two of them we can already show
you and the third is what the pilot is for."

**Scores:** Impact & Future Potential — a credible path and named measures.
The "eleven hours" carries *at a conservative estimate* aloud, always.

## Slide 9 · Close *(4:58–5:00)*

**On the slide:** the tagline and the repository URL.

**Say:** "Sentinel, by DuoCode. Every answer comes with its evidence. Thank
you."

---

## What the mentor changed (24 Sep)

The full table is in `PITCH_DAY.md`. In this document it landed as: the
"why we built it" line and the manual-check estimate on slide 2; the four
usage steps on slide 3; the "never say 'we use less AI'" rule on slide 5;
slide 4 trimmed to twenty seconds; slide 7 rebuilt around the five
differentiating features and given thirty; and, in the product, the status
words "No mismatch / Mismatch / Needs review", the Compare page's
three-step strip and clickable sample cards, and the nav order Home ·
Compare · Runs · How it works.

## Cuts and extensions

**Three minutes:** drop slide 7 (the demo covers it) and slide 4's spoken
half (keep the diagram on screen for ten seconds, say only the gate
sentence); demo becomes run → mismatch case → `/compare` off/on, 75 seconds.

**Eight minutes:** demo gains the pattern group and the reply draft (30 s);
slide 6 gains the OCR before/after table and the CMA CGM finding in
detail (30 s); slide 4 gains the "why exact matching" example with the two
APRIL FINE PAPER companies (30 s); slide 8 gains the cost projection from
the metrics page (20 s). Nothing else is added — more numbers per slide
does not score more.

## Every number on the deck, and where it comes from

| Number | Source |
|---|---|
| 520 emails · 46 mismatches · 20 sent to a person · 454 matched | `run.py` over `bundle_data`, 24 Sep, after `.gitattributes` (`STATUS.md` session 9); identical to the deployed API |
| 12.7 s on a free container (13 seconds) | deployed API `metrics.json`, `total_ms: 12684`, warm container; a cold one took 41.6 s |
| 2.7 ms per email single-threaded | same run on a laptop |
| 6 model calls on a model-tier run; 0 classifier, 0 extractor | measured 24 Sep: 0/520 `needs_llm`, 5 candidate documents all `wrong_doc_type` pairs, 6 `no_text_layer` attachments |
| 168 → 2, false discrepancies 0 both ways | `ADVERSARIAL.md` §8, `unseen_labels`, 188 documents |
| $0.0013 per document; 178 calls, $0.2447 | `ADVERSARIAL.md` §8, pinned rate card `llm/config.py` |
| 1.0000 × 4; 225 defects; 80/80 escalations | `SCORING.md` §4.1 (dev 520/46, held-out 520/57, 320/31, 820/91) |
| 16 modes · 3,008 documents · 20,496 reads · 13 at zero · 982 → 0 · 151 → 0 | `ADVERSARIAL.md` §1–§4, re-run 24 Sep, all sixteen modes match |
| `email_145`, one masked discrepancy in 3,008; the guard would flag 114 of 124 SI/BL pairs (92%) | `ADVERSARIAL.md` §5.2; `python backend/tools/party_continuations.py bundle_data`, 25 Sep (per label line it is 328 of 530, 62% — the 24 Sep "485 of 530" was a miscount) |
| CMA CGM SI template: one bug found and fixed | `EXTERNAL_VALIDATION.md` |
| 646 tests, 0 failing (504 passed, 142 skipped without the dataset) | `pytest --junitxml`, 25 Sep, on the final-round working tree (no `data/bundle`) |
| 21 pattern groups, largest 7 cases | run page over the real inbox, `STATUS.md` 24 Sep |
| desk codes AFEMY 35 · AIE 30 · AFRT 29 · AFPTME 22 | counted from `bundle_data/inbox` subjects and recipients, 24 Sep |
| 9.1% escalation rate, all correct | 20 of 220 comparison requests, gold `NEEDS_REVIEW` 20 |
| ~11 hours of desk work | **an estimate** — 20 s per email, 4 min per pair; say "conservative estimate" |
| gpt-5-mini, structured outputs, $2 ceiling, cache | `llm/config.py`, `llm/client.py`, `llm/cache.py` |
