# Status log

Newest entry at the top. Three lines: **Done / Next / Careful.**

---

## 2026-09-19 — Claude session 5 · Phase 3b (`web/` dashboard) built and verified

**Done**
- Scaffolded `web/` (Next.js 16.3.5 App Router, Turbopack, shadcn/ui, Recharts)
  and built all five items in this file's own 3b checklist: run list + create,
  inbox triage, the discrepancy report (`components/case-report-view.tsx` —
  "the screen the whole project exists to produce"), review confirm/correct,
  a client-side generated reply draft, and a metrics page with three charts.
  `POST /compare` (3d) has its own page too (`/compare`). `docs/ROADMAP.md`
  3b is ticked.
- Dropped `@tanstack/react-table` before writing a single row with it: the
  installed version is 9.2.4, a ground-up API rewrite from the `useReactTable`
  API this codebase's own training-era knowledge expected (confirmed by
  `node -e "require('@tanstack/react-table')"` listing its real exports — no
  `useReactTable`, no `getCoreRowModel`). A five-column table with manual
  filters does not need it; uninstalled rather than fighting an unfamiliar v9
  surface under a 3-day clock.
- Checked Next's own bundled docs before writing App Router code — `next dev`
  auto-generates a `web/AGENTS.md` warning that this Next version "has
  breaking changes" from training data and pointing at
  `node_modules/next/dist/docs/`. It was right to check: Next 16 ships a new
  Cache Components model (`cacheComponents` in `next.config.ts`, `'use cache'`,
  `<Suspense>`-gated runtime APIs). It is **off by default** and this
  dashboard never turns it on — every page is a plain Client Component
  fetching the FastAPI backend directly, which sidesteps that whole surface
  on purpose; if a future session enables `cacheComponents`, re-read that doc
  first, this dashboard was not written against it.
- Added two small, honest gaps found while building, not before:
  `GET /runs` (list all runs) — not in `backend/api/`'s original endpoint
  table, needed for the dashboard's own run list, `Store.list_runs` already
  existed for `latest_done_run` to build on; and `category_confidence` on
  `GET /runs/{id}/cases` — this file's own 3b line says the inbox triage needs
  a confidence column, and the API never exposed it until now. Both covered
  by `backend/tests/test_api.py` (still synthetic fixtures, still not
  `data/bundle`).
- **Found and fixed a real, non-obvious build bug, not a preference.**
  Utility classes written directly inside a Next.js dynamic-route folder
  (`app/runs/[runId]/...`) silently do not compile under this project's
  Tailwind v4 + Turbopack setup. Found by noticing a 4-column stat grid
  rendered as one column, then proven by fetching the actual served CSS and
  diffing it byte-for-byte (`md5sum`): `sm:grid-cols-2` (used in
  `components/case-report-view.tsx`, outside any bracket folder) compiled;
  `grid-cols-4` (used only in the metrics page, inside `[runId]/`) never did,
  with or without an explicit `@source` pointed at that exact path, before or
  after a full `rm -rf .next` restart. **Fix:** every `page.tsx` under a
  dynamic route segment is now a thin shell that only unwraps `params` (React
  `use()`, per Next's own file-conventions doc — a Client Component page
  cannot be `async`); all real markup moved to `components/*-page-view.tsx`,
  which compiles correctly. Keep this pattern for any new page added under a
  `[param]` segment, or the same silent failure comes back.
- **Correction, same day, from `a01dd91` (main): the diagnosis two bullets up
  was wrong.** The real cause was an unanchored `runs/` line in the
  repo-root `.gitignore` matching `web/app/runs/` at any depth — the same
  bug that had also swallowed three page files whole (`git status` never
  mentioned them, `git add -A` staged nothing under that path, no error).
  Tailwind was never broken; it correctly skips git-ignored files, and those
  files were git-ignored. `.gitignore` is now anchored (`/data/`, `/runs/`,
  `/.cache/`). The `components/*-page-view.tsx` split is kept as a plain
  layout choice, not as a fix for anything — the false claim is removed from
  `globals.css`'s comment. Left visible here rather than silently corrected,
  same reason this file keeps its other wrong-turn rows.
- **A second, sharper bug found while fixing the first one.** Documenting the
  fix above inside a CSS comment in `globals.css` — the comment's prose
  literally contained the word `@source` and a `[` character — crashed the
  Turbopack/PostCSS build outright: `CssSyntaxError: ... Unknown word [`, from
  a line that was supposed to be inside `/* ... */`. Whatever preprocesses
  `@source` in this pipeline is not respecting comment boundaries reliably.
  Reworded the comment in plain prose with no `@`-directive-looking text and
  no literal brackets; confirmed clean by watching the same error disappear
  from the dev server log on restart.
- Verified, not asserted: `npx tsc --noEmit` clean, `npm run lint` clean,
  backend suite unchanged at **391 passed / 141 skipped / 1 xfailed** after
  all of this (nothing under `backend/sdoc/` or `backend/api/`'s existing
  routes changed behaviour). Then a full manual click-through in a real
  running browser (not just curl) against a synthetic 3-email demo inbox
  (`data/manual_check_bundle/` — scratch data for this session, **not** the
  organisers' bundle and not a `demo_data/` proposal, see Careful below):
  created a run, watched inbox triage show the right category/confidence
  (100%)/status/`rule` badge for all three emails, opened all three case
  outcomes (OK all-MATCH, MISMATCH on `consignee` with real evidence
  snippets, NEEDS_REVIEW/`missing_attachment` with a recovery suggestion),
  confirmed a review and watched it persist across reload, generated a reply
  draft and read its text, and watched all three metrics charts render the
  correct real numbers (3/3/3 category count, a 1/1/1 outcome pie, 1
  `missing_attachment` bar).

**Next**
- **3c, deploy, is still zero lines** and is explicitly not something this
  session did unattended — it needs Render/Vercel accounts and a decision
  the team owns (which service account, what the public URL becomes), and it
  touches shared/external state. `docs/ROADMAP.md` still says do this on the
  20th.
- The `/compare` page's actual file-picker interaction was not click-tested
  in a live browser — this session's browser tool has no scriptable way to
  drive a native OS file picker. The endpoint underneath it is proven
  (3 pytest cases plus an earlier real `curl -F` multipart upload against a
  running server), and the page typechecks and lints clean, but a human
  should click through the literal upload flow once before demo day.
- Retry-a-single-case (docs/ROADMAP.md 3a, still `[~]`) is still not built.
- The metrics page deliberately does not show a confusion matrix or accuracy
  score — `docs/SCORING.md` and `CLAUDE.md` rule 1 both say nothing under
  `backend/` may read `data/_grader/ground_truth.json`, and the dashboard
  only calls `backend/api/`, which only ever sees what `backend/sdoc/` sees.
  If the team wants that number on-screen for the demo, it has to come from
  a human pasting the `score_cli.py` output in, not from a new code path.

**Careful**
- `data/manual_check_bundle/` is scratch data this session wrote to disk to
  have something real to click through — three emails, one clean, one with a
  planted consignee mismatch, one missing its second attachment. It is
  git-ignored like everything under `data/`. Do not confuse it with the real
  participant bundle or with the curated `demo_data/` the team still needs to
  decide on (`docs/ROADMAP.md`, "What the data problem is").
- `backend/api/store.py` is in-memory and empty on every restart — this
  session restarted the API once (to pick up `category_confidence`) and lost
  the first demo run; had to click "Start a run" again. Anyone deploying to
  Render should expect the same on every redeploy.
- Both dev servers were left running for hands-on inspection: backend on
  `:8000` (`SENTINEL_DATA_ROOT` pointed at `data/manual_check_bundle`),
  frontend on `:3000` (`web/.env.local` points at `:8000`). Stop them with
  whatever owns those ports before starting your own.
- If you add a new page under any `app/**/[param]/...` folder, put its markup
  in a `components/*-page-view.tsx` and keep the `page.tsx` to a two-line
  `params` unwrap. This is not a style preference — skipping it reproduces
  the silent Tailwind compile failure two sections up.

---

## 2026-09-19 — Claude session 4 · Phase 3a (`backend/api/`) built and verified

**Done**
- Built `backend/api/` end to end: `main.py` (FastAPI app + CORS), `store.py`
  (in-memory run/case store — no Postgres yet, see `ARCHITECTURE.md` §5),
  `pipeline_runner.py` (background-thread run over a bundled inbox),
  `direct_compare.py` (`POST /compare` logic), `models.py` (Pydantic at the
  boundary only, per `ARCHITECTURE.md`). All 8 endpoints from this file's own
  table are live: `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/cases`,
  `GET /cases/{id}`, `POST /cases/{id}/review`, `POST /compare`, `GET /metrics`,
  `GET /submission`. Nothing under `backend/sdoc/` was touched — the API calls
  the same `Pipeline`, `evidence_gate.evaluate` and `Pipeline._apply` the CLI
  uses, so the decision rule is not duplicated.
- `/compare` reuses the exact reader/doctype/extract/compare/gate stages
  `Pipeline._process` runs for a `BL_COMPARISON` email, so a judge's own
  upload gets the same evidence-gated decision the graded inbox does — no
  separate, weaker code path for the demo case.
- Found and fixed a real gap while building this, not before: `requirements.txt`
  listed `fastapi`/`uvicorn`/`pydantic` but nothing had ever exercised
  `UploadFile`, so the missing `python-multipart` dependency had never
  surfaced. Added it, plus `httpx` under `# --- dev ---` for
  `fastapi.testclient.TestClient`. Both installed clean in a fresh venv.
- Wrote `backend/tests/test_api.py` — 7 tests against synthetic fixtures built
  in the file itself, never `data/bundle` (`COLLABORATION.md` non-negotiable
  #1). Covers: matching documents → `OK`; a planted consignee mismatch →
  `MISMATCH` with a traceable evidence snippet on both sides; an empty upload
  → `NEEDS_REVIEW`, not a crash; and the full run lifecycle — create, poll
  status, list cases, fetch one, submit a review, confirm it persists, read
  `/metrics` and `/submission` — against a 3-email synthetic inbox (clean
  match / planted mismatch / missing second attachment), asserting the exact
  `OK` / `MISMATCH` / `NEEDS_REVIEW` split. All 7 passed on the first real run.
- Verified independently, not just asserted: fresh `.venv`, clean
  `pip install -r backend/requirements.txt` (confirms the `pdfplumber==0.11.10`
  pin from session 3 really does resolve), full suite **391 passed / 141
  skipped / 1 xfailed** (up from 384 before this session's 7 new tests — exact
  match, nothing else moved). Then booted a **real** `uvicorn` process (not
  TestClient) and hit it with `curl`: `GET /` → 200, `GET /openapi.json` → 200,
  a real multipart `POST /compare` → 200 with a traced, evidence-linked
  response. Stopped the process afterward.
- Note for whoever reads session 3's own numbers next to this one: this
  session's from-scratch venv measured **384 passed**, not the 330 that
  session 3's entry states for the same "no bundle" condition. Both agree on
  141 skipped. Recorded rather than quietly using whichever number was
  convenient — if it matters, `git log`/`git blame` on `docs/STATUS.md` and
  the test files will show which count is stale.

**Next**
- **3b, `web/` — does not exist yet.** The dashboard is the actual point of
  the project ("the discrepancy report... is the screen the whole project
  exists to produce; build it first" — this file's own words below). The API
  underneath it is now real, not a placeholder to build against.
- **3c, deploy — does not exist yet.** Render + Vercel accounts, Dockerfile,
  the public-vs-private repo flip: none of this is something a coding session
  can do unattended — it needs the humans' accounts and a decision on what
  goes in `demo_data/` (the open question two sections below, still open).
- Job handling from this file's own checklist is **half done**: a failed run
  is visible (`status: "failed"` + `error` on `GET /runs/{id}`, and a crashed
  *email* already always became a `NEEDS_REVIEW` case rather than losing the
  run — that part is `Pipeline.process`'s own existing behavior, not new).
  Retrying **one case** without re-running the whole inbox is not built; there
  is no endpoint for it. Small to add (`pipeline.process()` on one
  `EmailRecord`, overwrite that case in the store) but it is untested and
  unbuilt, not merely undocumented — do not assume it exists.
- `POST /runs` cannot be exercised against the real inbox from this session:
  `data/bundle` is git-ignored and was not present in the working copy this
  session ran in. Every `/runs` assertion above is against a synthetic 3-email
  inbox built in the test file. Point `SENTINEL_DATA_ROOT` at a real bundle
  and re-run `docs/SCORING.md`'s commands through the API instead of the CLI
  as the first thing the next session does, before trusting this further.

**Careful**
- `store.py` is one process's memory. It is fine for a single Render instance
  and it is gone on every restart — no run history survives a redeploy. That
  is an explicit, documented trade, not an oversight; swapping in the planned
  Postgres touches that one file's internals, not the routes, because nothing
  outside `store.py` reaches into its dict.
- `direct_compare.py` calls `Pipeline._apply`, a name-mangled-looking internal
  of `sdoc.pipeline`. Deliberate — the alternative was re-deriving the
  grounded/`NEEDS_REVIEW` decision rule a second time, which is exactly the
  kind of duplication `DECISIONS.md` warns against elsewhere. If `_apply`'s
  signature ever changes, this file breaks loudly at import or at the first
  test run, not silently.
- Do not read the "391 passed" figure above as license to stop checking
  numbers against `docs/SCORING.md`'s official scorer — this count is pytest
  health, not accuracy. Nothing in `backend/sdoc/` changed this session, so
  the score is still exactly what session 2/3 measured it at.

---

## 2026-09-19 — Claude session 3 · Phase 2 closed

**Done**
- **Phase 2 is complete.** Both fixes the previous session left unverified are
  now measured, tested and green; the adversarial evidence is regenerated; and
  three real defects found along the way are fixed. `ROADMAP.md` Phase 2 is
  ticked and `docs/ADVERSARIAL.md` is the write-up.
- Finished the work session 2 died mid-edit on. It had written the truncation
  repair in `compare.py` and hit its usage limit before running anything. The
  repair is sound: wrapped-value false discrepancies **64 → 0**, and it is
  provably inert on real data — over 520 emails the prefix relationship is hit
  exactly once (`email_145` shipper) and the repair declines, so the genuine
  defect survives. The separator fix in `readers/rows.py` recovers 3 × 1281
  field reads that were being lost.
- Wrote the tests neither fix had: `test_compare_wrap.py` (24) and
  `test_rows_separators.py` (53). A mutation review then found two loosenings
  of the repair's central promise — *it may recognise that we cut a value
  short; it may never invent agreement* — that the whole suite missed. Both
  now have killers: dropping the whitespace boundary guard fabricates
  `NANTONG , CHINA`, text that appears in no document; relaxing `==` to
  `startswith` silently rewrites a value and its evidence snippet.
- **Closed a hole the harness structurally cannot see.** `WRatio` folds in a
  partial-ratio component, so the three-character synonyms `POL`, `POD` and
  `G.W.` scored 90 inside any longer string containing those letters:
  `resolve("NAPOLI CENTRALE")` answered `port_of_loading`, `PODIUM TOWER`
  answered `port_of_discharge`, and so did `43-45 METROPOLITAN ROAD`. The old
  guard rejected a short *query*; nothing rejected a short *candidate*. Fixed
  with `_MIN_FUZZY_SYNONYM_CHARS = 6` and pinned by `test_labels_fuzzy.py`.
- **That fix then had a cost of its own, and the review caught it — worth
  reading as a pattern, not an anecdote.** Pruning the pool dropped three
  keys: `POL`, `POD` and `G.W.`. The code comment justified it by saying an
  abbreviation is caught by pass 1 or pass 2 anyway. True for the two port
  ones, which have their own alternatives in the pass-2 rules — and **false
  for `G.W.`**, which had no rule at all, so the fuzzy pass was its only
  resolver. Every decorated spelling (`G.W. (KGS)`, `TOTAL G.W.`,
  `G.W. 毛重(KGS)`) silently began resolving to nothing while the bare form
  kept working, and the test written to guard the invariant checked only that
  bare form. `DATA_NOTES.md` §2b says every weight label in this set carries
  exactly such a parenthetical, so the regressed spellings are the realistic
  ones. Fixed by giving the abbreviation the rule the comment assumed it had
  (`\bG\s*W\b`, matching nothing in any of the four datasets), and the tests
  now pin the family a spelling at a time. **The score never moved through any
  of this** — which is the point: it could not have told us.
- Three real defects fixed: `llm_calls` was declared, aggregated and printed
  but never incremented, so every run reported "0 model calls" while the usage
  block said six — `Pipeline.process` now differences `client.usage.calls`
  around each email, outside the `except`, because a crashed email may already
  have paid for a call. `pypdfium2` and `pillow` are pinned: `readers/scan.py`
  imports both directly and they were only ever present as pdfplumber's
  dependencies, so a resolver change would have switched the vision path off
  in silence. And `pip install -r backend/requirements.txt` **failed outright**
  with `ResolutionImpossible` — `pdfplumber==0.11.4` under the `>=0.11.9` that
  `markitdown[pdf]` demands — meaning no judge following the README could
  install the project at all. The pin is now 0.11.10, the version every
  measured score was actually produced with.
- The suite no longer breaks on a fresh clone. 304 tests read git-ignored
  `data/bundle/` with no guard and *errored* rather than skipped; with the
  guard in `conftest.py` a clone with no data is 330 passed / 141 skipped /
  **0 errors**.

- **Phase 2's definition of done is now actually met, not rounded up.** The
  bar was "what breaks the deterministic path *and what the LLM layer
  recovers*", and the second half had never been measured — both harness runs
  were `pipeline_mode: deterministic`. Ran it with the model on
  (`adversarial.py --only unseen_labels --llm`): unfamiliar label wording
  forces **168 of 188** cases to a human on the rules alone and **2** with the
  model, while false discrepancies, silent wrong values and masked
  discrepancies all stay at **zero**. 178 calls, $0.2447. Written up as
  `ADVERSARIAL.md` §8, which also spells out how to quote it honestly — the
  model does no work on the graded inbox.
- Added `--llm` to the harness CLI. It refuses to write a report labelled
  `assisted` if no usable client is configured, because a file that misstates
  which pipeline it measured is worse than no file.

**Next**
- **Phase 3, and it is the whole remaining risk.** See `ROADMAP.md` — it now
  carries the endpoint list, the screen list and the deploy plan, so the next
  session can start writing instead of re-deriving. Roughly 40 of the judges'
  100 points ride on a live deployed demo and meaningful cloud use, and that
  is currently zero lines of code. Do the deploy on the 20th, not the 21st.
- The one Phase 2 box still open is **(T)**, not (C): hand-check ten escalated
  cases. A score cannot tell us whether a reason reads sensibly to an operator.

**Careful**
- **No decision moved.** All four datasets still score **1.0000** and every
  `submission.json` is byte-identical to the previous run. The no-key run is
  byte-identical to the LLM-enabled run, which is the honest way to say that
  the model changes nothing here — the 1.0000 is entirely the rules'.
- **The fuzzy pass fires on zero labels in all four datasets.** Every real
  label is answered by pass 1 or pass 2 — 13,620 chunk labels were classified
  by pass to confirm it. So the score *cannot* detect a regression in
  `labels.py`; measure that one on the unit tests and the harness instead.
- One `xfail` remains and it is legitimate: `_extend` uses
  `text.find(value.raw)`, taking the *first* occurrence rather than the one
  the evidence locator points at. Consignee and notify party are frequently
  the same company here, so a continuation can be read from the wrong block.
  It has fired 0 times on real data. Anchoring `_extend` on the locator is the
  fix, and `test_compare_wrap.py:601` goes green the day it lands.
- **`runs/` is git-ignored and agents write into it.** The full 94-pair
  adversarial report was silently overwritten by a 40-pair partial run during
  verification, so the file on disk stopped reproducing the numbers
  `ADVERSARIAL.md` cites. Regenerated and checked cell by cell. If you script
  anything against the harness, write it to the scratchpad, not to `runs/`.
- `runs/adversarial.json` was previously a snapshot taken *between* two fixes
  and understated the system. It is regenerated. If you change extraction,
  regenerate it again — a table a judge cannot reproduce is worse than none.
- OCR character confusion is **open** and stated plainly in `ADVERSARIAL.md`.
  Do not let a judge discover it unprompted; the mitigation is real
  (`readers/scan.py` keeps image-only scans unreadable, so our own OCR never
  feeds a decision) and the caveat is honest (the perturbation really does
  alter the document).

---

## 2026-09-19 — Claude session 2

**Done**
- Phase 1 is complete. The deterministic pipeline runs end to end over all 520
  emails in ~2.3 ms each, with no model calls and no network.
- Repository published: `TCF1209/duocode-sentinel` (private — **make it public
  before the submission deadline**, the rules require a public link).
- Scores 1.0000 on the dev set **and on three held-out seeds** at three
  different scales — 225 defect emails in total, every one caught with the
  exact field set, no false alarms, 80/80 escalations correct. Table in
  `SCORING.md` §4.1.
- Found and fixed the only two false alarms the system produced, which shared
  one cause: a long PDF label drawn through its own value, interleaving the
  characters (`"...Intermediate ConsCigEnReIEeX"`). Labels and values are now
  separated by font where the geometry is ambiguous.
- Fixed a second, subtler fault the first fix exposed: the value column was
  detected from the most common word left-edge, so a fifteen-row container
  table outvoted the form's own value column.
- Added the markitdown fallback reader for formats we have no precise reader
  for, `scripts/evaluate.py` (pipeline + official scorer in one command), and
  `docs/DECISIONS.md`.

**Next**
- Phase 2, but **not** as "raise the score" — it is already at the ceiling on
  everything this generator can produce. The real work is robustness *beyond*
  the generator: the LLM fallback for unseen label wording (the classifier
  already reports `needs_llm` and nothing consumes it), the vision path for
  scans, and adversarial perturbation of the documents to find where we break.
- Then Phase 3: API, dashboard, deployment.

**Careful**
- **A perfect score is a reason for suspicion, not celebration.** All four
  datasets come from one generator, with one label vocabulary and one set of
  renderers. It proves we do not memorise a draw; it does not prove we survive
  a real document. Say it that way in the pitch too — judges respect a team
  that states the limits of its own evidence.
- Do not "simplify" `_value_column_from_labelled_rows()` in `readers/pdf.py`
  back to counting word edges. That is exactly the bug that cost an end-to-end
  point, and the score log records it.
- The score log in `SCORING.md` deliberately keeps the row where the score went
  *down*. Do not tidy it away.

---

## 2026-09-19 — Claude session 1

**Done**
- Read every artefact (problem statement, rules, infopack, participant bundle,
  organiser Docker bundle) and wrote up the findings in `docs/DATA_NOTES.md`.
- Repo scaffold, venv, dependencies, git-ignored `data/`.
- Architecture settled and documented: deterministic-first pipeline with an
  LLM fallback, evidence attached to every extracted value, `NEEDS_REVIEW` as
  a first-class outcome.
- Core modules written: `schema.py`, `normalize.py`, `labels.py`, and the
  readers for `.txt`, `.docx`, `.xlsx` and `.pdf`.

**Next**
- Phase 1 in `docs/ROADMAP.md`: `doctype.py`, `readers/__init__.py`,
  `extract/fields.py`, `compare.py`, `classify/`, `pipeline.py`, `run.py` —
  then the first measured score.

**Careful**
- The PDF reader reconstructs columns from word coordinates on purpose. Do not
  replace it with a line-based parser, however much simpler that looks:
  `pdftotext -layout` pairs labels with the wrong values on these documents and
  produces *confident* false discrepancies. See `DATA_NOTES.md` §3.
- In `labels.py`, the `NOTIFY` rule must stay above the `CONSIGNEE` rule —
  "Notify Party/Intermediate Consignee" contains the word *Consignee*.
- Two different emails in the set have zero attachments and *opposite* correct
  outcomes, separated only by intent. See `DATA_NOTES.md` §5a.
