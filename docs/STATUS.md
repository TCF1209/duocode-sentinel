# Status log

Newest entry at the top. Three lines: **Done / Next / Careful.**

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
