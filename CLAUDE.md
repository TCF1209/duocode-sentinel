# Project context for AI sessions

Read `docs/STATUS.md` first, then `docs/ROADMAP.md`. `docs/DATA_NOTES.md`
explains why the code is shaped the way it is — read it before changing
anything in `readers/`, `labels.py` or `normalize.py`.

## What this is

Averis × Monash Hackathon 2026. A shipping operations inbox is classified
per email; document-comparison requests have their Shipping Instruction (SI)
compared against a draft Bill of Lading (BL) across 7 fields; anything the
system cannot decide confidently is escalated to a human with evidence.

Categories: `BL_COMPARISON` `SI_REQUEST` `INVOICE_QUERY` `GENERAL` `SPAM`
Statuses: `OK` `MISMATCH` `NEEDS_REVIEW`
Fields: `shipper` `consignee` `notify_party` `port_of_loading`
`port_of_discharge` `container_count` `gross_weight_kg`

## Hard rules

1. **Never read, import or reference `data/_grader/ground_truth.json` from any
   code under `backend/`.** It exists only so the organisers' own
   `score_cli.py` can grade a finished submission. `data/` is git-ignored.
2. **No per-email special cases.** No `if email_id == "email_313"`. A rule must
   be justified by the shipping domain, not by one labelled example. If you
   find yourself wanting one, the generalisable fix is in `labels.py`,
   `normalize.py` or `classify/rules.py`.
3. **Values are compared with exact equality after normalisation, never
   fuzzily.** The entity pools contain near-identical names that are genuinely
   different parties/ports; a similarity threshold swallows real defects.
   Fuzzy matching is for *labels* only. The single amendment is
   `compare.ocr_confusable`, and the test it must pass to stay is that it
   **never produces `MATCH`** — it escalates, so its worst case is a wasted
   review rather than a cleared BL (`docs/DECISIONS.md` §D2).
4. **A blank or unreadable value is not a discrepancy.** It is
   `NEEDS_REVIEW`. Reporting `MISMATCH` on a `???` field is a false alarm and
   costs precision.
5. **The pipeline must run with no API key and no network.** The LLM is a
   fallback for hard cases, never a hard dependency.
6. Every extracted value carries `Evidence(doc, locator, label, snippet)`.
   Do not add a code path that produces a bare value.

## Commands

```bash
# run the pipeline over the full inbox
.venv/Scripts/python.exe backend/run.py --data data/bundle --out runs/latest

# score it with the organisers' scorer
.venv/Scripts/python.exe data/_grader/score_cli.py runs/latest/submission.json \
    --ground-truth data/_grader/ground_truth.json

# tests
.venv/Scripts/python.exe -m pytest backend/tests -q
```

## After you change pipeline behaviour

Re-run the score, add a row to the table in `docs/SCORING.md`, and append an
entry to the top of `docs/STATUS.md`.
