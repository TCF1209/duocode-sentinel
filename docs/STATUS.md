# Status log

Newest entry at the top. Three lines: **Done / Next / Careful.**

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
