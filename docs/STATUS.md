# Status log

Newest entry at the top. Three lines: **Done / Next / Careful.**

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
