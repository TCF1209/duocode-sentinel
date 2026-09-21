# `bundle_data/` — the organisers' participant bundle, committed on purpose

520 emails and 251 attachments, exactly as the Averis × Monash organisers
distributed them to participants. It is here so the deployed API can process
**the whole graded inbox live** rather than a curated sample: the number the
README quotes and the number a judge watches being produced are the same 520
emails.

| | |
|---|---:|
| emails | 520 |
| attachments | 251 |
| `.txt` / `.pdf` / `.xlsx` / `.docx` | 192 / 28 / 23 / 8 |
| size | 3.2 MB |

## Why this directory exists instead of `data/bundle/`

The same files already sit in `data/bundle/`, which is git-ignored — and that
is deliberate, because `data/_grader/` sits beside it holding the answer key
and the dataset generator. `docs/SCORING.md` §3 explains how we came to have
those and what we may and may not do with them; the short version is that the
organisers' own package says it must not be handed to participants, it was sent
anyway, and it has never entered this repository.

`.dockerignore` is an allow-list precisely to keep it that way, and its last
lines re-exclude `data/` so that a future `!data/something` line cannot
accidentally reverse the decision. Publishing the participant bundle by adding
an exception inside `data/` would have meant editing that guard.

So this is a separate top-level directory. The guard around `data/` is
untouched, and what is published here is only ever material the organisers gave
to every team.

## What is **not** here, and will not be

* `ground_truth.json` — the answer key. Not in this directory, not in
  `bundle_data/`'s history, not anywhere in this repository. The participant
  bundle never contained one: its `sample_submission.json` is a blank template
  labelling all 520 emails `GENERAL`/`OK`.
* The dataset generator. Used only to produce held-out draws at seeds we never
  developed against (`docs/SCORING.md` §4.1); no file from that package is
  committed.

Nothing under `backend/sdoc/` can read an answer key even if one appeared:
`grep -rn ground_truth backend/ --include=*.py` returns nothing, and
`CLAUDE.md` rule 1 forbids adding it.

## What the deployed API does with it

`SENTINEL_DATA_ROOT=/app/bundle_data`, so `POST /runs` processes all 520 emails
with no model calls, no network and no key — about 3 seconds of pipeline work on
a laptop, longer on Render's free CPU. `demo_data/` (30 emails, curated) stays
in the image as a faster alternative; the dashboard's **limit** box selects a
subset of this inbox when a shorter run is wanted.

The accuracy score is **not** computed here and cannot be: scoring needs the
answer key. `final_score = 1.0000` is measured by running the organisers' own
`score_cli.py` locally, and the command is in the root `README.md` under
*Verify it yourself*. What this inbox demonstrates live is coverage, latency and
the rule/model split — not a grade.
