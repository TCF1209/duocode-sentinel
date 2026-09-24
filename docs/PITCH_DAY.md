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
  - [ ] `/compare`, the *unfamiliar labels* sample: toggle off → Needs
        Review with "No label for … could be recognised"; toggle on → Mismatch
        on consignee and notify party, badge **model answered**.
  - [ ] `/compare`, the *scanned* sample, toggle on: transcript card.
  - [ ] `/pitch` slide 3 chip reads **590 tests · 0 failing**; slide 4's
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
- [ ] Open, in this tab order, so nothing is typed on stage: `/pitch` (slide
      1) · `/runs` · `/compare` with the unfamiliar-labels sample loaded ·
      the GitHub repository.
- [ ] Browser: 1280×720 or the projector's native size, bookmarks hidden,
      notifications off, other tabs closed.
- [ ] Keep the Render root URL in a fourth tab and refresh it every ten
      minutes while waiting to present, so the container never sleeps.

## The five-minute demo, in order

The deck's beats and timings are in `PITCH_DECK.md`. On the product:

1. `/runs` → **Start a run** with the model tier on. While the ring fills:
   "the organisers' full inbox, 520 emails, on a free-tier container."
   Point at the tally: **46 mismatches, 20 sent to a person with the reason,
   thirteen seconds, 6 model calls — all six are scans read out for the
   reviewer.**
2. **Patterns worth a second look** — open the top group, say what it is
   (six cases from one shipper wrong on the same field), click into one.
3. A **MISMATCH** case: the two documents side by side, the two fields that
   disagree, and under every value **the line it was read from**. This is the
   promise of the first slide, on screen.
4. A **NEEDS_REVIEW scan** (`email_512`): "no text layer, so it did not
   decide — but the model read the page for the reviewer" — the transcript
   card, then the review panel: confirm / correct per field.
5. `/compare`, unfamiliar labels, **toggle off**: "wording our table has
   never seen — the honest answer is *can't read it*, and it says which
   labels." **Toggle on**: "the model reads them, every value is re-located
   in the document before it is adopted, and it surfaces the real
   discrepancy — badge says *model answered*."
6. Back to the deck for impact and close.

If the venue network dies mid-demo: switch to the local tab (`localhost:3000`
already open behind), say so in one sentence, and continue from the same
step. The inbox run is identical; only the model beat changes.

## Questions to expect, and the short true answer

**"You said almost every decision is made by rules, not AI — why use AI so
little?"** *(the preliminary judge's own comment)*
Because on this inbox the rules are right every time and the scoring is
all-or-nothing per email: flag one of two fields and that email scores
zero. The model is aimed at the three things the rules admit they cannot do
— an ambiguous email, a label we have never seen, a scanned page — and we
measured it there: on documents with wording we invented, rules alone send
168 of 188 cases to a human; with the model, 2, and false discrepancies stay
at zero because nothing the model returns is adopted until we find it again
in the document. You just watched it read a scan and read four labels. On
this data the rules need no help, and that is a measured result, not an
absence.

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
document says. The repair has nothing to repair, and a real mismatch reads
as a match — once in 3,008 perturbed documents. The obvious guard would flag
92% of genuine party fields, so it stays open and documented.

**"Why exact matching — isn't fuzzy matching smarter?"**
The entity pools contain `APRIL FINE PAPER TRADING` and `APRIL FINE PAPER
TRADING (MIDDLE EAST) FZE` — different companies. Any threshold loose enough
to forgive a scanning artefact merges them and a real defect disappears.
Fuzzy matching is for labels; values are exact after canonicalisation. The
one amendment, for OCR-confusable characters, can only ever escalate — it
never produces a match.

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
- **"574 tests"**, **"one test pinned to fail"**, **"45 mismatches, 21
  refused"** — all stale. It is **590 tests, 0 failing** and **46 / 20**.
- **"Thirteen seconds"** is a warm container. A cold one takes 40. Wake it.
- **"Eleven hours of desk work"** only with *"at a conservative estimate"*
  in front of it. It is arithmetic on an assumed pace, not a measurement.
