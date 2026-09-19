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
- [ ] **(T)** Decide the project name (placeholder: *Sentinel*) and lock it before the slides

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

## Phase 2 — Robustness beyond the generator · target: 20 Sep

**Read this framing before picking up a task.** The score is at its ceiling on
everything this generator can produce, so "improve accuracy" is no longer a
meaningful goal — there is nothing left to improve *against this data*. What is
unproven is whether the pipeline survives a document the generator cannot make:
unfamiliar label wording, an unseen layout, a real scan. That is Phase 2.

- [ ] **(C)** Adversarial perturbation harness: mutate the documents ourselves —
      invented label synonyms, reflowed layouts, OCR-style noise, values split
      across lines — and measure where extraction actually breaks. **Do this
      first**: it tells us what the LLM layer needs to cover, instead of us
      guessing.
- [ ] **(C)** `llm/client.py` — OpenAI wrapper, structured output, retries
- [ ] **(C)** `llm/cache.py` — content-hash cache so runs stay reproducible and cheap
- [ ] **(C)** `classify/llm.py` — consume the `needs_llm` flag the rule
      classifier already sets and nothing currently reads
- [ ] **(C)** `extract/llm.py` — model-assisted extraction for fields the rules
      could not read, with the evidence gate still holding the line on anything
      the model produces that cannot be traced
- [ ] **(C)** Vision path for image-only PDFs: produce a transcript as reviewer
      evidence, while the case still escalates
- [ ] **(C)** Cost + latency instrumentation: pinned rate card, real tokeniser
      counts, projected cost at 10k emails/day
- [ ] **(T)** Spot-check 10 escalated cases by hand — is the reason right, and
      is the evidence enough for an operator to act on?
- [ ] **(C)** Re-run all four datasets after the LLM layer lands; the numbers
      must not move down

**Definition of done:** we can state, with measurements, what kind of document
breaks the deterministic path and what the LLM layer recovers — and the
held-out scores are unchanged.

## Phase 3 — Product surface · target: 21 Sep

- [ ] **(C)** `api/` — FastAPI: `POST /runs`, `GET /runs/{id}`, `GET /cases/{id}`,
      `POST /cases/{id}/review`, `GET /metrics`, `GET /submission`
- [ ] **(C)** Job handling: visible failures, retry a single case
- [ ] **(C)** Next.js dashboard
  - [ ] inbox triage view — category, status, confidence, `rule`/`llm` badge
  - [ ] discrepancy report — SI vs BL side by side, mismatched fields
        highlighted, **evidence snippet under each value**
  - [ ] review queue — reason, source evidence, confirm / correct, then the
        report updates
  - [ ] metrics page — scores, confusion matrix, cost + latency, rules %
- [ ] **(C)** Generated reply draft to the counterparty listing the discrepancies
- [ ] **(T)** Deploy: Render (backend Docker) + Vercel (frontend), confirm the
      public URL works from a phone on mobile data

**Definition of done:** a judge can open one link and run the whole story
without us touching anything.

## Phase 4 — Submission assets · target: 21 Sep evening

- [ ] **(T)** Slide deck: architecture, implementation, challenges, roadmap
- [ ] **(T)** Demo video ≤ 5:00 — intro, problem, tech stack, live demo, impact
      *(1 mark lost per 30s over — rehearse with a timer)*
- [ ] **(C)** `README.md` with setup instructions a judge can follow
- [ ] **(T)** Project description for the Google Form
- [ ] **(T)** Dry run: fresh clone → follow the README → does it work?

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
