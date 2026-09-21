# Roadmap & task board

**Preliminary deadline: 22 Sep 2026, 12:00 PM.**
Everything below is sized to land with a buffer on the evening of the 21st.

Legend: `[ ]` open · `[~]` in progress · `[x]` done · **(C)** = Claude session ·
**(T)** = team (you + teammate)

---

## Phase 0 — Foundations · target: 19 Sep

- [x] **(C)** Read every artefact: problem statement, rules, infopack, both data bundles
- [x] **(C)** Repo scaffold, `.gitignore`, venv, dependencies
- [x] **(C)** Copy dataset to `data/bundle/`; grader to `data/_grader/` (git-ignored)
- [x] **(C)** `schema.py` — domain types + submission shape
- [x] **(C)** `normalize.py` — org / port / number canonicalisation, blank detection
- [x] **(C)** `labels.py` — 3-pass label resolution
- [x] **(C)** Readers: `rows.py`, `plain.py`, `office.py`, `pdf.py`
- [x] **(C)** Docs: `ARCHITECTURE.md`, `DATA_NOTES.md`, `SCORING.md`, this file
- [ ] **(T)** Read `DATA_NOTES.md` end to end — it is the shared mental model
- [x] **(T)** **Project name locked: Sentinel.** Tagline for the deck and the
      video: ***Sentinel — every answer comes with its evidence.*** Considered
      and rejected: *Flagship*, which names a status rather than a behaviour and
      would have cost a rename across 30 files, 96 references, 9 `SENTINEL_*`
      environment variables and — the part that actually mattered — both
      deployed URLs, the day before submission. *Sentinel* also happens to be
      the accurate word: this system's whole claim is that it stands watch and
      says what it cannot read, rather than answering everything.

## Phase 1 — Measurable baseline · **COMPLETE** (19 Sep)

- [x] **(C)** `doctype.py` — SI / BL / invoice / packing list / COO classifier
- [x] **(C)** `readers/__init__.py` — dispatch, readability checks, size guards
- [x] **(C)** `extract/fields.py` — chunks → 7 fields with evidence
- [x] **(C)** `compare.py` — verdicts per field
- [x] **(C)** `classify/rules.py` — scored 5-category classifier
- [x] **(C)** `classify/intent.py` — "send me a draft" vs "check what I attached"
- [x] **(C)** `pipeline.py` + `run.py` — full inbox → `submission.json` + `report.json`
- [x] **(C)** First official score; table filled in `SCORING.md`
- [x] **(C)** `pytest` suite over the known traps in `DATA_NOTES.md` (240 tests)
- [x] **(C)** `readers/fallback.py` — markitdown for unfamiliar formats
- [x] **(C)** `scripts/evaluate.py` — pipeline + official scorer in one command
- [x] **(C)** GitHub repository published (`TCF1209/duocode-sentinel`, private)

**Result:** 520 emails, ~2.3 ms each, 100% resolved without a model call.
Final score **1.0000** — and the same on three held-out seeds (`SCORING.md` §4.1).

## Phase 2 — Robustness beyond the generator · **COMPLETE** (19 Sep)

**Read this framing before picking up a task.** The score is at its ceiling on
everything this generator can produce, so "improve accuracy" is no longer a
meaningful goal — there is nothing left to improve *against this data*. What is
unproven is whether the pipeline survives a document the generator cannot make:
unfamiliar label wording, an unseen layout, a real scan. That is Phase 2.

- [x] **(C)** Adversarial perturbation harness — `backend/tools/adversarial.py`,
      16 perturbations in 8 families over 94 SI/BL pairs, no answer key. Results
      and findings in `docs/ADVERSARIAL.md`.
- [x] **(C)** `llm/client.py` — OpenAI wrapper, structured output, metering, budget
- [x] **(C)** `llm/cache.py` — content-hash cache so runs stay reproducible and cheap
- [x] **(C)** `classify/llm.py` — consumes `needs_llm`, wired at `pipeline.py:141`
- [x] **(C)** `extract/llm.py` — model-assisted extraction, every answer re-located
      in the source before it is adopted; the gate still vetoes what cannot be traced
- [x] **(C)** Vision path for image-only PDFs — `readers/scan.py`, wired at
      `pipeline.py:202`. The transcript is reviewer evidence only; the case still
      escalates (pinned by `test_transcribed_scan_is_still_unreadable`).
- [x] **(C)** Cost instrumentation — pinned rate card (`llm/config.py`), provider
      token counts, per-purpose breakdown and a run budget, all in `metrics.json`
- [x] **(C)** Re-ran all four datasets after the LLM layer landed — all still 1.0000
- [ ] **(T)** Spot-check 10 escalated cases by hand — is the reason right, and
      is the evidence enough for an operator to act on? **Still open, and it is a
      human's job**: a score cannot tell us whether a reason reads sensibly.

**Result.** Three findings, all three now closed. Missing colons / dashes /
indented labels cost every field on the page (safe, but useless) — fixed in
`readers/rows.py`. Party names wrapped across two lines produced 74 *silent
wrong values* — fixed in `compare.py`, false discrepancies 64 → 0, and provably
inert on real data. OCR character confusion was the last and the worst: 982
silent wrong values and 151 invented defects, both now **zero** — fixed in
`normalize.py` (a damaged number is refused rather than parsed short) and
`compare.py` (a value differing only on confusable glyphs escalates rather than
being reported), written up in `ADVERSARIAL.md` §4.4.

What §5.1 still says, and should: the *reads* still change, because the
document genuinely says something else. The pass rate did not move and was
never going to. What moved is the consequence — fail-safe instead of
fail-silent.

The review also found a hole the harness structurally *cannot* see: short synonyms
("POL", "POD") fuzzy-matched inside long strings, so `NAPOLI CENTRALE` resolved to
a port. Fixed in `labels.py` via `_MIN_FUZZY_SYNONYM_CHARS`.

- [x] **(C)** Measure what the model layer recovers, not just what the rules
      lose — `adversarial.py --llm`, written up in `ADVERSARIAL.md` §8.

**Definition of done: met.** `docs/ADVERSARIAL.md` states, with measurements,
what breaks the deterministic path, what the model layer recovers, what was
fixed and what is still open; all four held-out scores are unchanged and every
`submission.json` is byte-identical.

The recovery number is the one worth carrying into the pitch: unfamiliar label
wording forces **168 of 188** cases to a human on the rules alone and **2** with
the model, while false discrepancies, silent wrong values and masked
discrepancies all stay at **zero**. Recall bought by guessing would have shown
up in that second clause; it did not. 178 calls, $0.2447.

Say it carefully, though — §8 spells out why. The model does **no** work on the
graded inbox (`decided_by` is `rule` for all 520), so this is "here is what
happens when wording we have never seen arrives", never "our pipeline is 89% AI".

## Phase 3 — Product surface · target: 21 Sep · **THE CRITICAL PATH**

**Read this before picking up a task.** Accuracy is finished. Nothing in the
judges' 100-point rubric is "score on the organisers' scorer" — the closest is
Technical Feasibility & Validation (15). **Working Core Prototype (25) requires a
live deployed demo, and Technology Integration (15) requires meaningful cloud
use**, which the rules make mandatory: *"solutions that do not meaningfully
integrate cloud infrastructure may receive significantly reduced scores."* So
roughly 40 points ride on this phase, and today it is zero lines.

The pipeline needs no changes to serve this. `Pipeline` has no web or database
imports, `report.json` already carries every field with its evidence, and
`metrics.json` already carries cost and latency. **Phase 3 is a presentation
layer over data that already exists** — resist the urge to touch `backend/sdoc/`.

### 3a · `backend/api/` — FastAPI

`fastapi`, `uvicorn` and `pydantic` are already in `requirements.txt`.

| Endpoint | Returns |
|---|---|
| `POST /runs` | start a run over the bundled demo inbox → `{run_id}` |
| `GET /runs/{id}` | status + `metrics.json` |
| `GET /runs/{id}/cases` | case list, filterable by category / status / `decided_by` |
| `GET /cases/{id}` | one `report.json` record — all 7 fields, both sides, evidence |
| `POST /cases/{id}/review` | reviewer confirms or corrects; the report updates |
| `POST /compare` | **upload two documents, get a comparison** — see 3d |
| `GET /metrics` | counts, rule share, cost, latency |
| `GET /submission` | the graded artefact, for the "we scored 1.0000" claim |

- [x] **(C)** the endpoints above, Pydantic models at the boundary only — built
      in `backend/api/`, all 8 live and tested (`backend/tests/test_api.py`,
      7/7 passing). See `docs/STATUS.md` 2026-09-19 session 4.
- [x] **(C)** job handling: visible failures, retry a single case. A failed
      *run* carries `status`/`error`; `POST /cases/{id}/retry` re-processes one
      email in place, re-reading it from disk so a re-sent attachment is picked
      up. The case keeps its position and `processed` does not double-count.
- [x] **(C)** A reviewer's correction reaches the report — the problem
      statement's "then update the report". `Store.effective_outcome` combines
      the system's answer with the review; the case list, the submission and
      the case detail all read it, so a corrected case leaves the queue while
      the system's own answer stays visible beside it as `system_status`.
      Measured in `ADVERSARIAL.md` §6: removing the blank veto takes escalation
      recall from 1.000 to 0.750.

### 3b · `web/` — Next.js dashboard

- [x] **(C)** inbox triage — category, status, confidence, `rule`/`llm` badge
- [x] **(C)** discrepancy report — SI vs BL side by side, mismatched fields
      highlighted, **the evidence snippet under each value**. This is the
      screen the whole project exists to produce; build it first.
- [x] **(C)** review queue — reason, recovery text, source evidence, confirm /
      correct, then the report updates — built as part of the case-detail page
      rather than a separate queue screen (see `docs/STATUS.md` session 5)
- [x] **(C)** metrics page — cost + latency, rules % (**no confusion matrix or
      accuracy score** — those need the organisers' ground truth, which
      `backend/` must never read; this page shows operational metrics only)
- [x] **(C)** generated reply draft to the counterparty listing the discrepancies
      — built client-side from data already in the report, no extra API call

### 3c · Deploy — Render (backend Docker) + Vercel (frontend)

- [x] **(C)** Dockerfile + render config
- [x] **(T)** flip `TCF1209/duocode-sentinel` to public — done 21 Sep, and it
      turned out to be load-bearing for more than the rules: Vercel's Hobby
      plan refuses to build a commit pushed by anyone who is not the project
      owner, so a teammate's push produced a deployment that never shipped.
      A public repository is one of the three fixes Vercel itself offers.
      The other, and the one to keep using: the teammate pushes a branch and
      the owner merges it with `--no-ff`, so the tip of `main` is a commit the
      owner pushed.
- [x] **(C)/(T)** **DEPLOYED.** Dashboard
      [duocode-sentinel.vercel.app](https://duocode-sentinel.vercel.app),
      API [sdoc-sentinel-api.onrender.com](https://sdoc-sentinel-api.onrender.com).
      Verified on the public URLs, not locally: the run list, the side-by-side
      report with evidence, `POST /compare` on real uploads, and the guards
      (`use_llm=true` → 403, `limit=-5` → 422, partial `/submission` → 409).
- [ ] **(T)** confirm the public URL works from a phone on mobile data

**Do this on the 20th, not the 21st.** Deployment always costs two hours more
than planned, and a dead link on submission day is an incomplete entry.

### 3d · The upload path is the demo, not a feature

`POST /compare` lets a judge drop in their own SI and BL and watch the system
work. It is worth more than any pre-recorded flow, for three reasons:

1. It answers "are you just replaying a memorised dataset?" on the spot.
2. It is where the **model actually earns its place**. The rules win 520/520 on
   this generator, so a judge asking "show me the AI doing something" currently
   has only the six scan transcriptions to look at. An unfamiliar document is
   exactly the case `extract/llm.py` was built for — and that path has never
   run on real data (see `STATUS.md`).
3. If it fails on their document, the honest outcome is a `NEEDS_REVIEW` with
   a reason — which *is* the product's thesis. There is no bad outcome.

**Definition of done:** a judge can open one link and run the whole story
without us touching anything.

### What the data problem is, and the decision still open

`data/` is git-ignored (3.3 MB, 520 emails + 251 attachments), but Render builds
from git, so the deployed API needs something to serve. The organisers have
confirmed the **participant bundle** may be published; the mis-sent organiser
package (answer key + generator) may **never** be — see `SCORING.md` §3.

Options, in the author's order of preference: a curated demo subset (~30 emails
covering all 5 categories, all 4 escalation reasons and several real defects)
committed under `demo_data/`, **plus** the upload path in 3d; or committing the
whole participant bundle. **(T) to decide.**

## Phase 4 — Submission assets · target: 21 Sep evening

- [x] **(T)/(C)** Slide deck: architecture, implementation, challenges, roadmap
      — **answered with the README rather than a deck.** The rules list "GitHub
      README" beside Google Slides, PDF and Notion as an acceptable
      documentation link, and all four required sections are already in it
      (`docs/SUBMISSION.md` maps each one to its heading). Building a deck the
      evening before would have competed with the video, which is the component
      that carries a time penalty.
- [~] **(T)** Demo video ≤ 5:00 — intro, problem, tech stack, live demo, impact
      *(1 mark lost per 30s over — rehearse with a timer)*. Script, running
      order, per-section timings and the pre-record checklist are in
      [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md); **recording it is what is left.**
- [x] **(C)** `README.md` with setup instructions a judge can follow
- [x] **(C)** Project description for the Google Form — both a full and a short
      version, with every other form field, in [`SUBMISSION.md`](SUBMISSION.md)
- [x] **(C)** Dry run: fresh clone → follow the README → does it work? **Yes**,
      re-run 21 Sep against a clone with no `data/`, no API key and no network:
      `pip install -r` resolves clean, `run.py --data demo_data` gives 30
      emails / 5 categories / 4 escalation reasons, `pytest` gives **431
      passed, 142 skipped, 0 errors**, `uvicorn backend.api.main:app` serves
      from the repo root with `ready: true`, and `npm ci && npm run build &&
      npx tsc --noEmit` is clean (645 packages, 0 vulnerabilities, 7 routes).
      The README's three stale numbers were corrected from it.
      **Not covered, and each needs the bundle or a browser:** the 520-email
      path and `score_cli.py` (a judge supplies `data/`), the dashboard
      driving the API in a browser (verified earlier on the deployed URLs
      instead), and the macOS/Linux command variants — the Windows ones were
      the ones run.

## Phase 5 — Buffer · 22 Sep morning

- [ ] **(T)** Submit by 11:00, not 11:55
- [ ] **(T)** Re-check every link is public (GitHub, demo, slides, video)

---

## Backlog — final-round differentiators (only after Phase 4 is safe)

- Confidence calibration: show *why* a case was escalated, with a score
- Reviewer corrections feed back into the synonym table (a learning loop)
- Batch view: "12 emails from this carrier all mismatch on POD" — pattern alerts
- Throughput/cost projection at real inbox volume
- Multi-tenant: per-desk rules (AIE / AFPTME / AFRT / AFEMY)

---

## How to pick up work

1. `git pull`
2. Read `docs/STATUS.md` — what the last session finished and what is next
3. Pick the top unchecked box in the current phase
4. Branch: `feat/<short-name>`, commit small, push
5. Tick the box in this file **in the same commit** as the work
6. If you change behaviour, re-run the score and add a row to `SCORING.md`
