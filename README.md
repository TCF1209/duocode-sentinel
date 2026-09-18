# Sentinel — shipping document verification

*From email inbox to discrepancy report.*
Averis × Monash Hackathon 2026.

A shipping operations team receives everything in one inbox: requests to check
documents, requests for new shipping instructions, invoice queries,
operational noise, and spam. For a document check they compare a **Shipping
Instruction (SI)** against a **draft Bill of Lading (BL)** across seven fields
and look for anything that does not match, before the draft is finalised.

Sentinel does that work, and — this is the part that matters in an operations
setting — it knows when it cannot. A missing attachment, an unreadable scan, a
blank field or the wrong document type produces a case for a human with the
reason and the source evidence attached, not a confident guess.

---

## What it does

| Capability | How |
|---|---|
| **Classify** | Scored rule classifier over 5 categories; an LLM decides only the ambiguous tail. Each email records whether a rule or the model answered. |
| **Extract** | Format-aware readers for `.txt`, `.pdf`, `.docx`, `.xlsx`. PDFs are reconstructed from word coordinates, not flat text. Every value keeps a pointer back to where it was read. |
| **Compare** | Labels are matched by meaning (`Load Port` = `Port of Loading`); values are canonicalised and compared exactly. Side-by-side SI/BL output with the differing fields flagged. |
| **Ask for help** | Missing attachment · wrong document type · unreadable file · blank required value → routed to a review queue with the evidence, for a person to confirm or correct. |

## Quick start

```bash
git clone <repo-url> && cd sdoc-sentinel

python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt   # Windows
# source .venv/bin/activate && pip install -r backend/requirements.txt  # macOS/Linux

# put the participant bundle in place (not committed — see docs/SCORING.md)
#   data/bundle/{inbox,attachments,sample_submission.json}

.venv/Scripts/python.exe backend/run.py --data data/bundle --out runs/latest
```

Outputs:

* `runs/latest/submission.json` — the shape the official self-evaluation expects
* `runs/latest/report.json` — the full audit trail: every field, every verdict,
  every piece of evidence, what the LLM was used for

An optional API key enables the model fallback and reading scanned documents.
**Without it the pipeline still runs end to end** — rules handle everything
they can and the rest is escalated rather than guessed.

```bash
cp .env.example .env     # then set OPENAI_API_KEY
```

## Repository map

```
backend/sdoc/     the pipeline — no web framework, no database, no network
backend/api/      FastAPI surface over the pipeline
backend/tests/    regression tests for the traps in docs/DATA_NOTES.md
web/              Next.js dashboard
docs/             architecture, data findings, scoring, roadmap, status
data/             dataset + local grader — git-ignored, never committed
```

## Documentation

| Document | Read it when |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | you want the design and the reasoning behind it |
| [`docs/DATA_NOTES.md`](docs/DATA_NOTES.md) | **before** changing anything in extraction |
| [`docs/SCORING.md`](docs/SCORING.md) | you want the metrics and how we validate |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | you are picking up the next task |
| [`docs/STATUS.md`](docs/STATUS.md) | you just sat down |
| [`docs/COLLABORATION.md`](docs/COLLABORATION.md) | you are joining the repo |

## On evaluation

The problem statement provides a self-evaluation that grades a submission
against a private reference set. We use it exactly as intended: to find our
own errors while building. The reference answers are never read by any code in
`backend/`, are not committed to this repository, and no per-email answers are
hard-coded anywhere. Generalisation is verified by regenerating the dataset
with an unseen seed and scoring against that. Details in
[`docs/SCORING.md`](docs/SCORING.md).
