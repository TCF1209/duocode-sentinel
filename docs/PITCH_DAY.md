# Pitch day — 26 September 2026, Monash University Malaysia

Registration 9:00, pitching from 10:30. Live, in person, with questions.
Everything below was written on 24 Sep against the repository as it stood
then; the numbers are the ones `docs/STATUS.md`'s session-9 entry measured.

**The pitch time limit and the Q&A format come from the Finalist Portal**
and were not known when this was written. `PITCH_DECK.md` is built for five
minutes plus questions and says which beats to drop for three and which to
add for eight. Read the portal first, then cut.

---

## The day before

- [ ] `main` is merged and pushed **by the repository owner** (Vercel's
      Hobby plan only builds the owner's pushes — `ROADMAP.md` 3c). Then, on
      the public URLs, in a private window:
  - [ ] <https://sdoc-sentinel-api.onrender.com/> reports `ready: true` and
        `llm_runs_allowed: true` (the `render.yaml` flag took effect).
  - [ ] `/runs` shows a finished run; open it: the stat strip, **Patterns
        worth a second look**, the filters.
  - [ ] Start a run **with the model tier on**: `metrics.json` shows 6 model
        calls; `email_512`, `513`, `514` show the transcript card on both
        documents.
  - [ ] `/compare`, the *Labels we have never seen* sample: toggle off →
        Escalated, with "Not extracted from the SI: Shipper, Consignee,
        Notify Party, Port of Loading" (the "No label for … could be
        recognised" sentence is inside the folded notes line); toggle on → Discrepancy:
        Consignee, Notify Party, badge **model answered**.
  - [ ] `/compare`, the *scanned* sample, toggle on: transcript card.
  - [ ] `/pitch` slide 3 chip reads **757 tests · 0 failing**; slide 4's
        card is about `email_145`.
  - [ ] GitHub: the CI badge on the README is green (first run after the
        push). If it is red, read the log before the pitch — a red badge on
        the README is worse than none.
- [ ] The laptop that will be on stage has a fresh `git pull`, `.venv`
      installed, `npm ci` done, and the two servers start cleanly
      (`uvicorn backend.api.main:app --port 8000` with
      `SENTINEL_DATA_ROOT=bundle_data`, then `cd web && npm run dev`).
      Local is the fallback if the venue network fails; it runs the whole
      520-email inbox in about 1.5 s with no network at all. **It cannot show
      the model tier unless `.env` holds a key and `SENTINEL_ALLOW_LLM_RUNS=1`
      is exported** — decide beforehand whether the fallback demo skips that
      beat or the key travels with the laptop.
- [ ] Phone hotspot charged and tested as the second network.
- [ ] Rehearse the whole thing twice with a timer: once on the deployed
      URLs, once on local. Write the two timings on the first page of the
      speaker notes.
- [ ] Try the dashboard in **light mode** (the theme toggle, top right) on a
      projector or a bright external screen. The dark theme reads well on a
      laptop and badly on a washed-out projector; decide which one the demo
      uses and do not decide it on stage.

## The morning

- [ ] **T–20 min: wake Render.** Open the API root, wait for `ready: true`.
      The free tier sleeps after ~15 minutes idle and takes 30–60 s to wake;
      the first run after waking took 41.6 s when it was measured, the second
      12.7 s. **Start one run and throw it away** so the one on stage is the
      warm one.
- [ ] **The re-check tile has three turns per run.** *Re-check on amendment*
      opens an email with nothing attached (`email_506`, then `508`, then
      `510`), and each *Load a sample pair → Re-check* turns one case to
      *No discrepancy* for everyone looking at that run. The home page follows the latest finished
      run, so a fresh run — the one thrown away above, or a Render restart —
      resets all three. Start another after any rehearsal that used them.
- [ ] Open, in this tab order, so nothing is typed on stage: `/pitch` (slide
      1) · `/runs` · `/compare` with the *Labels we have never seen* sample loaded ·
      the GitHub repository.
- [ ] Browser: 1280×720 or the projector's native size, bookmarks hidden,
      notifications off, other tabs closed.
- [ ] Keep the Render root URL in a fourth tab and refresh it every ten
      minutes while waiting to present, so the container never sleeps.

## The five-minute demo, in order

The deck's beats and timings are in `PITCH_DECK.md`. On the product:

1. `/runs` → **Start a run** with the model tier on. While the ring fills:
   "the organisers' full inbox, 520 emails, on a free-tier container."
   Point at the tally: **46 discrepancies, 20 escalated with the reason,
   thirteen seconds, 6 model calls — all six are scans transcribed for the
   reviewer.**
2. On the run, flip **Before Sentinel**: the inbox as it arrived — 520
   subject lines, 124 SI/BL pairs to find among them, "≈ 11.2 h of work at
   our own estimate". Classify the first five yourself (the *Your call* column;
   the clock starts at the first pick). Flip **With Sentinel**: your pace
   projected over all 520, Sentinel's 1.3 s beside it, and how many of the
   five it agreed with. *(Light theme on stage. The five calls survive
   opening a case; "Start over" clears them for the next rehearsal.)*
3. The filter card: **Sorted into** is step 1 (classify) with the counts;
   **Outcome** is the check. Click *Discrepancy 46*: the list narrows, the
   discrepant fields are on every row.
4. **Patterns worth a second look** — it starts collapsed; open it, say what
   the top group is (seven cases from one shipper with a discrepancy on the
   same field), click into one.
5. A **Discrepancy** case: the two documents on top (*View original*), all
   seven fields in order — the two discrepant fields as full cards, the five
   consistent ones as one line each (click one to open it) — and under every
   value **the line it was read from**. The review box asks one thing — is
   there a discrepancy between the SI and the BL? — in one row: *Confirm
   discrepancy · Flag fields · Mark no discrepancy · Escalate · Attach
   amended SI/BL · Draft reply to counterparty*; confirming the Sentinel result is the one
   click. Then fix it where it is: *Edit* on the BL value, type what the
   shipper confirmed,
   Enter — the pair is compared again with the run's own rules, the card
   turns to *Consistent* with the extracted value kept underneath, struck
   through, the outcome above follows; *Revert* puts the extracted value
   back. *Mark no discrepancy* in the box is the one-click version when the
   two are the same party, and *Flag fields* adjusts which fields differ.
   The *Review record* then reads as three rows: Sentinel result · Reviewer
   decision · Changes. Nothing to scroll to, nothing to submit.
6. An **Escalated** case: `email_512` (a scan, needs the model run): "no
   text layer, so it did not decide — but the model transcribed the page for
   the reviewer" — the transcript card, and the seven fields as amber rows.
   Then *Use scan transcription* → tick the fields you verified against the
   image → *Accept N values — verified against the scan* → the rules compare
   the fourteen values and the case moves on, with "Values accepted from the
   scan transcription (…) after the reviewer verified them against the
   scan." on the record. Or `email_506` (the BL never arrived):
   the review box already shows *Amended documents* (nothing on file) →
   *Load a sample pair* → *Re-check* → it comes back No discrepancy, and
   the previous result stays on the case as v1.
7. `/compare`, *Labels we have never seen*, **toggle off**: "wording our table has
   never seen — the honest answer is that it cannot read them, so it
   is *Escalated*, and it says which labels." **Toggle on**: "the model reads them, every value is re-located
   in the document before it is accepted, and it surfaces the real
   discrepancy — badge says *Model answered*."
8. Back to the deck for impact and close.

Cut for time: step 2's own five calls (say the numbers instead), step 6's
second case, step 7's toggle-off half.

If the venue network dies mid-demo: switch to the local tab (`localhost:3000`
already open behind), say so in one sentence, and continue from the same
step. The inbox run is identical; only the model beat changes.

## Mentor feedback (24 Sep, 20:30) — and what changed because of it

Thirty minutes with a mentor the evening before the final. Their points, in
their order of emphasis, and what was done with each:

| They said | What changed |
|---|---|
| Don't say "we use less AI". Say the AI is *reserved* for the cases rules can't handle — and the system performs just as well. | Slide 5's notes open with that sentence; the answer below is rewritten around it. |
| At the top-ten stage everyone meets the brief; **differentiate on the special things** — re-check on amendment, the scan transcription, shipper history on a field, the original document beside the value, the drafted reply. | Slide 8 is now "What makes it different", five features, thirty seconds instead of fifteen. |
| The intro should say **why the system was built** and how long a manual check takes. | Slide 2 carries both; the time is our estimate (≈4 min a pair, 20 s an email) and is labelled as one. |
| The pitch shows the pipeline steps but not **how a person uses it**. | Slide 3's footer is the four steps: run, open a case, confirm or override it / correct a single value / attach the amended SI/BL, send the reply. |
| Design is better and more distinctive than most of the ten. **But**: font sizes too uniform; capitalisation inconsistent (`all` vs `All`); the Compare page's samples don't look clickable; discrepancies should be visible from the list without opening a row. | Status labels are now "No discrepancy / Discrepancy / Escalated" (judges dislike "Matched/Mismatched"; the API still returns the problem statement's "No mismatch detected."). Compare samples are obvious buttons (icon, title, tagline, "Loaded" once picked) with a three-step strip above them. Run-table emphasis, chip capitalisation and the case page's type hierarchy: session 8's list. |
| Nav: "Pitch" says nothing; Runs could come after Compare. | Home · Compare · Runs · How it works. |
| A judge asked another team whether **20,000 KG against 20 MT** is caught as a unit mismatch. | It is handled, and re-checked on 24 Sep: `20 MT` → 20,000 kg, `21 MT` → 21,000 kg, so 20,000 KG vs 20 MT compares equal and 20,000 KG vs 21 MT is a discrepancy. Answer below. |

## Questions to expect, and the short true answer

**"You said almost every decision is made by rules, not AI — why use AI so
little?"** — *the mentor's rule: never say "we use less AI".*
The AI is reserved for the cases the rules can't handle — an ambiguous
email, a label we have never seen, a scanned page — and the system performs
just as well, because we measured it there: on wording we invented, rules
alone escalate 168 of 188 cases; with the model, 2, with false
discrepancies still at zero. Using AI on every email would cost money on
every email for no gain; on this inbox the rules are right every time, and
that is a measured result, not an absence.

**"What about units — 20,000 KG on one document and 20 MT on the other?"**
Both are normalised to kilograms before the comparison — 20 MT reads as
20,000 kg, so that pair compares equal; 20,000 KG against 21 MT is reported
as a discrepancy. Same for thousands separators and bare numbers in a
spreadsheet cell.

**"And pounds?"**
Our own test on real US bills of lading found it: 8,010 KG against 8,010
LBS read as the same weight. Now Sentinel sees that one side is in pounds
and the other in kilograms, and escalates the field to a person instead
of passing it. It does not convert pounds, on purpose. We tried four
conversions and our old-versus-new review rejected all four, because on a
real form the unit printed next to a number can belong to the next box. So
the pounds check works like our scan check: it can turn a pass into a
review, and it can never clear or condemn a Bill of Lading by itself.
Still open, and written down: the same weight printed in each unit shows as
a discrepancy, and European notation ("12.500,00 KG") is not read.

**"Have you tried it on real documents, not the organisers' data?"**
Yes, on 25 Sep: blank forms from six carriers and industry bodies, 30 real
scanned and archived shipping documents, 2,000 real bill-of-lading records
and 14,000 real emails. Two honest results. It cannot read most real form
layouts yet: boxed forms with the label above the value never appear in the
organisers' data, and on the filled carrier forms it read 0 of 42 fields.
And it never cleared or condemned a real document it could not read: every
one was escalated to a person with the reason. The test also found ways a real
document could fool the rules; we fixed only what survived three rounds of
old-versus-new review and wrote the rest down (`EXTERNAL_VALIDATION.md`).

**"How is the organisers' data different from the real thing?"**
It tests *checking*: clean digital files, one label per line, kilograms and
tonnes only, a container count always written "3 x 40'HC". Real documents
add *reading*: boxed layouts, scans, OCR noise, pounds, "40HC x 3". Our
checking is proven, 1.0000 on their data and zero wrong calls on real
documents. Reading real layouts is the next step, and the plan is the model
does the reading while the rules do the checking and a person signs.

**"A perfect score — is it overfitting?"**
Four datasets, three from seeds we never developed against: 1.0000 on all
four. That proves we did not memorise the draw. It does not prove real
documents, and we say so on the slide — so we attacked our own reader with
3,008 perturbed documents and sixteen kinds of damage with no answer key,
and tested a real carrier's SI template from outside the generator, which
found a bug we fixed. The one defect we have not fixed is on the slide too.

**"You had the answer key."**
The organisers' package reached us with the key and the generator inside;
their own README says it should not have. It is git-ignored, never
committed, and no file under `backend/` reads it — `grep -rn ground_truth
backend/` returns nothing. The generator was used for one thing: seeds we
never developed against, which is a stricter test than we were asked for.
It is the first thing the README volunteers.

**"Where is your database?"**
There isn't one yet, on purpose. Every route reaches state through one
class in `store.py`, so Postgres is a one-file change and the architecture
document says so. Adding an external dependency and a credential in the
last days before a live demo that does not need persistence was the wrong
trade; we wrote the decision down instead of drawing a box.

**"How does it scale?"**
The pipeline is a stateless library, 2.7 ms an email single-threaded. Once
the store is external, throughput is more containers behind the same URL.
Cost does not scale with volume on this inbox at all — every decision is a
rule — and the metrics page projects both to 50,000 emails a day from the
run's own numbers, with the worst case shown as a ceiling.

**"What about the per-desk rules and the pattern alerts you listed as
future plans?"** *(the judge's second point)*
Pattern alerts are built — you saw twenty-one real groups on the run page.
Per-desk rules are next: the desk code is already in the inbox, the label
table and the escalation policy are already the two things a desk would
own, and the plumbing to select one per desk is the roadmap's item 5.

**"What is the one thing it gets wrong?"**
`email_145`: a wrapped party name cut short to exactly what the other
document says. The repair has nothing to repair, and a real discrepancy
reads as consistent — once in 3,008 perturbed documents. The obvious guard would flag
114 of 124 SI/BL pairs (92%), so it stays open and documented.
*If asked how the 92% is counted:* the only sign that a name wrapped is a
line with no label of its own right after it — which is also exactly what an
address block looks like. 114 of the 124 pairs have a shipper, consignee or
notify value followed by such a line, so a guard on that sign escalates them
all. Per label line it is 328 of 530 (a notify party never has an address
under it); `backend/tools/party_continuations.py` reproduces both.

**"Why exact matching — isn't fuzzy matching smarter?"**
The entity pools contain `APRIL FINE PAPER TRADING` and `APRIL FINE PAPER
TRADING (MIDDLE EAST) FZE` — different companies. Any threshold loose enough
to forgive a scanning artefact merges them and a real discrepancy
disappears. Fuzzy matching is for labels; values are exact after
canonicalisation. The one exception, for OCR-confusable characters, can
only ever escalate — it never marks a field consistent.

**"What does it cost to run?"**
Nothing on this inbox. The model, where it is needed, is thirteen hundredths
of a cent per document at the published rates, with a two-dollar ceiling per
run and a cache so a re-run is free.

**"What would you do next with a week?"**
Per-desk configuration, then confirmed reviewer corrections feeding the
label table — the one place this system should learn — then the database.
In that order, because the first two change what a desk gets and the third
changes only what survives a restart.

## Things not to say

- **"Our pipeline is 89% AI."** It is not; the model does no work on the
  graded inbox. The 168 → 2 is what happens on wording we invented.
- **"574 tests"**, **"596 tests"**, **"732 tests"**, **"733 tests"**, **"756 tests"**, **"one test pinned to fail"**, **"45
  mismatches, 21 refused"** — all stale. It is **757 tests, 0 failing** and
  **46 / 20**.
- **"Thirteen seconds"** is a warm container. A cold one takes 40. Wake it.
- **"It reads any bill of lading."** It does not yet: on real boxed carrier
  forms it reads almost nothing and escalates. Say it never guesses on them.
- **Do not upload a real carrier form in the live demo.** It will escalate
  every field, which is correct but looks like it does not work. Use the
  samples on the Compare page.
- **"Eleven hours of desk work"** only with *"at a conservative estimate"*
  in front of it. It is arithmetic on an assumed pace, not a measurement.
