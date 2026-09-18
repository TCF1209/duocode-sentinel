# Working together (2 people + AI sessions, 3 days)

The bottleneck in a short hackathon is not typing speed — it is **context**.
Every time one of us sits down we have to reload: what is done, what is next,
why something was built the way it was. This repo is set up so that reload
takes two minutes.

## The three files that carry the context

| File | Answers | Updated |
|---|---|---|
| `docs/STATUS.md` | *Where are we right now?* | end of every session |
| `docs/ROADMAP.md` | *What is next, and who has it?* | when a box is ticked |
| `docs/DATA_NOTES.md` | *Why is the code shaped like this?* | when we learn something new about the data |

Plus `CLAUDE.md` at the repo root: any Claude Code session opened in this
folder reads it automatically and starts with the project's rules already
loaded. That is the point — **a fresh AI session in this repo is productive
immediately, without re-explaining the problem.**

## Git flow

Small and boring on purpose.

```bash
git pull                              # always first
git checkout -b feat/pdf-extractor    # one branch per unit of work
# ... work ...
git add -A
git commit -m "feat(readers): reconstruct PDF columns from word coordinates"
git push -u origin feat/pdf-extractor
```

Merge into `main` as soon as it is green. We are not running a release
process; long-lived branches in a 3-day project only create conflicts.

* `main` must always run. If `run.py` crashes on `main`, that is the highest
  priority bug in the project.
* Commit messages: `type(scope): what changed` —
  `feat`, `fix`, `docs`, `test`, `chore`.
* Tick the `ROADMAP.md` box **in the same commit** as the work it describes.

## Handing off mid-task

Before you stop, write three lines in `docs/STATUS.md`:

```markdown
## 2026-09-20 14:30 — <name>
Done: PDF reader handles the two-column layout; 24/28 PDF pairs now extract cleanly.
Next: the 4 failures are all image-only scans — needs the vision path.
Careful: do not "simplify" _value_column_x(); the 4% threshold is what stops
         the container table columns from being picked as the value column.
```

Newest entry at the top. That third line is the one that saves the most time —
it stops the next person from redoing a decision you already made.

## Division of labour (suggestion)

Neither of us should own a whole vertical slice — if one person is stuck, the
other should be able to keep moving.

| Area | Primary | Why |
|---|---|---|
| Pipeline accuracy (extract / compare / classify) | Claude session | tight loop with the scorer |
| Dashboard + deployment | whoever prefers frontend | independent of pipeline internals |
| Slides, video, form | both, on the 21st | needs the real demo to exist first |
| Manual QA of escalated cases | **a human, always** | a score cannot tell us whether a review reason reads sensibly to an operator |

## Running an AI session on this repo

```bash
cd sdoc-sentinel
claude          # or open the folder in the Claude desktop app
```

Good opening prompts:

* "Read docs/STATUS.md and docs/ROADMAP.md, then take the next open task."
* "Run the pipeline, score it, and show me every email where the category was
  decided by the LLM instead of rules."
* "Here is the scorer output — find the general cause of the Stage 3 misses.
  Do not special-case individual emails."

Bad prompt: *"make the score higher"*. That invites exactly the overfitting
`SCORING.md` forbids.

## Non-negotiables

1. `data/` is never committed. Especially `data/_grader/`.
2. No `if email_id == ...` anywhere. Ever.
3. Secrets live in `.env`, which is git-ignored. If a key is ever pushed,
   rotate it immediately — do not just delete the commit.
4. Re-score before merging anything that touches the pipeline, and add the row
   to the table in `SCORING.md`.
