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

## Phase 1 — Measurable baseline · target: 19 Sep, end of day

The goal is a number, not a pretty one. Everything after this is improvement
against a measured starting point.

- [ ] **(C)** `doctype.py` — SI / BL / invoice / packing list / COO classifier
- [ ] **(C)** `readers/__init__.py` — dispatch, readability checks, size guards
- [ ] **(C)** `extract/fields.py` — chunks → 7 fields with evidence
- [ ] **(C)** `compare.py` — verdicts per field
- [ ] **(C)** `classify/rules.py` — scored 5-category classifier
- [ ] **(C)** `classify/intent.py` — "send me a draft" vs "check what I attached"
- [ ] **(C)** `pipeline.py` + `run.py` — full inbox → `submission.json` + `report.json`
- [ ] **(C)** First official score; fill the table in `SCORING.md`
- [ ] **(C)** `pytest` suite over the known traps in `DATA_NOTES.md`

**Definition of done:** `run.py` processes all 520 emails with no crash, and
`score_cli.py` prints a final score.

## Phase 2 — Accuracy & the LLM layer · target: 20 Sep

- [ ] **(C)** `llm/client.py` — OpenAI wrapper, structured output, retries
- [ ] **(C)** `llm/cache.py` — content-hash cache so runs are reproducible and cheap
- [ ] **(C)** `classify/llm.py` — fallback for low-margin classifications
- [ ] **(C)** `extract/llm.py` — model-assisted extraction for unread fields
- [ ] **(C)** Vision path for image-only PDFs (transcript as reviewer evidence,
      case still escalated)
- [ ] **(C)** Error analysis: dump every disagreement, fix the *general* cause
- [ ] **(T)** Spot-check 10 escalated cases by hand — is the reason right and
      is the evidence enough to act on?
- [ ] **(C)** Held-out seed run; record both numbers in `SCORING.md`

**Definition of done:** end-to-end rate and macro-F1 both measured, on two
different seeds, with the gap written down.

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
