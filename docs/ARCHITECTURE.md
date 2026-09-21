# Architecture

## 1. What the system does

One sentence: **it turns a shared operations inbox into a per-email decision,
and every decision it is not sure about goes to a human with the evidence
attached.**

```
                                  ┌──────────────────────────────────┐
  inbox/email_XXX.json  ─────────▶│  Stage 1 · Classify              │
                                  │  rules first, LLM only on doubt  │
                                  └───────────────┬──────────────────┘
                                                  │
                  SI_REQUEST · INVOICE_QUERY ·    │    BL_COMPARISON
                  GENERAL · SPAM                  │
                       │                          ▼
                       │          ┌──────────────────────────────────┐
                       │          │  Stage 2 · Intake                │
                       │          │  attachments present?            │
                       │          │  readable?  right document type? │
                       │          └───────────────┬──────────────────┘
                       │                          │
                       │            ┌─────────────┴─────────────┐
                       │            ▼                           ▼
                       │   ┌──────────────────┐     ┌──────────────────────┐
                       │   │ Stage 3 · Extract│     │  escalate            │
                       │   │ 7 fields + source│     │  NEEDS_REVIEW        │
                       │   │ evidence, per doc│     │  + reason + evidence │
                       │   └────────┬─────────┘     └──────────┬───────────┘
                       │            ▼                          │
                       │   ┌──────────────────┐                │
                       │   │ Stage 4 · Compare│                │
                       │   │ normalise, then  │                │
                       │   │ exact match      │                │
                       │   └────────┬─────────┘                │
                       │            ▼                          │
                       │   ╔══════════════════╗                │
                       │   ║ Stage 5 · GATE   ║  can veto ─────┤
                       │   ║ every value must ║                │
                       │   ║ trace to a real  ║                │
                       │   ║ span, or escalate║                │
                       │   ╚════════┬═════════╝                │
                       │            ▼                          │
                       ▼   ┌──────────────────────────────────────────────┐
                           │  Stage 6 · Decide + Report                   │
                           │  OK · MISMATCH(fields) · NEEDS_REVIEW(reason)│
                           └───────────────┬──────────────────────────────┘
                                           ▼
                        discrepancy report · review queue · submission.json
```

## 2. The three decisions that shape everything else

### 2.1 Deterministic first, LLM second

Every stage tries a deterministic path before it reaches for a model, and
records which path answered (`decided_by: "rule" | "llm"`).

Why:

* **Accuracy.** The headline metric requires the *exact set* of mismatched
  fields. A parser that reads `Total Containers: 5 x 40'HC` is right every
  time; a model asked the same question is right almost every time. On 46
  graded emails, "almost" is the difference between first and fourth place.
* **Cost and latency.** An ops inbox is thousands of emails a day. Spending a
  model call on an obvious spam message is indefensible in production, and the
  organisers' own scorer reports `resolved by rules (cost)` — they are
  watching for exactly this.
* **Demo safety.** With no API key and no network the pipeline still runs end
  to end. A live demo that depends on a third-party API being up is a demo
  that eventually fails in front of judges.

The LLM is not decoration — it earns its place on the cases rules genuinely
cannot settle: ambiguous intent, unfamiliar label wording, layouts we have not
seen, and reading scanned documents.

### 2.2 Every value carries its evidence

An extracted field is never a bare string. It is
`(value, normalised value, which document, where in it, the label as printed,
the raw snippet)`. That single decision buys three things at once: a reviewer
can confirm a flag in seconds, the UI can show the source side by side, and
we can tell "the document says something different" apart from "we read the
document wrong" — which is exactly the distinction the problem statement asks
for.

### 2.3 Uncertainty is a first-class outcome, not an error

`NEEDS_REVIEW` is not a failure path bolted on at the end. A blank field, an
unreadable scan, a missing attachment and a wrong document type are all
*normal* states of an ops inbox. Each produces a case with a reason and the
source evidence, routed to a review queue where a person confirms or corrects
it — and the corrected result flows back into the report
(`Store.effective_outcome`: the system's answer is immutable and the review
sits beside it, so the queue clears without the audit trail being overwritten).

**Its name in the literature is the reject option**, and the three-way outcome
is older than any of this: Chow formalised abstention in 1970, and
Fellegi–Sunter's match / non-match / **clerical review** (1969) is the same
decision rule for the same task — deciding whether two records describe the
same entity. Saying "we escalate instead of guessing" as though it were new
would be wrong. What we changed is the *criterion* for the middle band. The
classical rule puts a probability in a grey zone between two thresholds; ours
is not a probability at all but a hard locatability test — §2.2's gate — so
there is no threshold to mis-tune on a document type we have never seen. The
cost of that choice is stated in `ADVERSARIAL.md`: a binary gate cannot express
that a missing locator on `notify_party` matters more than one on
`gross_weight_kg`.

## 3. Module map

```
backend/sdoc/
├── schema.py          domain types; the submission shape lives here
├── normalize.py       "same fact, written differently" — the canonicalisers
├── labels.py          label synonyms -> our 7 canonical fields (3-pass)
├── doctype.py         is this an SI, a BL, an invoice, a packing list, a COO?
├── readers/
│   ├── __init__.py    dispatch by extension + readability checks
│   ├── rows.py        shared "Label: value" line parser
│   ├── plain.py       .txt
│   ├── office.py      .docx (tables) and .xlsx (A/B columns)
│   └── pdf.py         .pdf — coordinate-based column reconstruction
├── extract/
│   ├── fields.py      chunks -> the 7 FieldValues, with evidence
│   └── llm.py         model-assisted extraction for what rules could not read
├── classify/
│   ├── rules.py       scored keyword/pattern classifier over the 5 categories
│   ├── intent.py      "send me a draft" vs "check the docs I attached"
│   └── llm.py         model fallback when the rule margin is thin
├── compare.py         field-by-field verdicts -> MATCH/MISMATCH/UNCOMPARABLE
├── evidence_gate.py   no defect without traceable evidence; can veto a defect
├── pipeline.py        the orchestrator; produces CaseResult
├── llm/
│   ├── client.py      provider wrapper (OpenAI), structured output
│   └── cache.py       content-hash cache: same input -> same answer, no call
└── cli.py             run over a dataset -> submission.json + report.json
```

Dependency direction is one-way: `readers` and `classify` know nothing about
`pipeline`; `pipeline` knows about everything. Nothing under `backend/sdoc/`
ever reads a label file.

## 4. Stage detail

### Stage 1 — Classify

A scored pattern classifier over five categories. Each rule contributes weight
to a category; the winner needs both a minimum score and a minimum margin over
the runner-up. Below either threshold the email goes to the LLM, which returns
a category and a one-line justification. Roughly: cheap rules handle the
overwhelming majority, the model handles the tail.

Small classes matter most: Stage 1 is graded with macro-F1, so `SPAM` (40
emails) and `GENERAL` (60) carry the same weight as `BL_COMPARISON` (220).

### Stage 2 — Intake

For comparison requests only. Answers three questions in order, and the first
failure escalates:

1. **Do we have a pair?** 0 or 1 attachment → `missing_attachment`
   (subject to the intent check, see `DATA_NOTES.md` §5a).
2. **Can we read them?** empty file, corrupt PDF, or a PDF with no text layer
   → `unreadable`. A scanned document is still passed to the vision model so
   the reviewer gets a readable transcript, but the case is *not* auto-decided.
3. **Are they the right documents?** the pair must be
   {Shipping Instruction, Bill of Lading}. A Commercial Invoice, Packing List
   or Certificate of Origin → `wrong_doc_type`.

### Stage 3 — Extract

Each reader flattens its format into `Chunk(label, value, locator)`. The field
extractor resolves each chunk's label to one of the seven fields and keeps the
best candidate per field, with evidence. Fields the rules could not find, or
found blank, are handed to the LLM extractor together with the raw document
text; anything still missing becomes `missing_value`.

### Stage 4 — Compare

Both sides are canonicalised (`normalize.py`) and compared with **exact
equality**. Three verdicts per field: `MATCH`, `MISMATCH`, `UNCOMPARABLE`.
`UNCOMPARABLE` never becomes a defect — it escalates.

### Stage 5 — The evidence gate

> **No discrepancy may be reported unless both sides of it trace back to a real
> span in a real document.**

The gate runs after the comparison and before the decision, and it can **veto**
a defect the comparison believed in. It returns one of:

| Status | Meaning | Becomes |
|---|---|---|
| `grounded` | everything the decision rests on is traceable | OK or MISMATCH |
| `no_comparison_needed` | the sender asked us to *produce* a draft; nothing to compare | OK |
| `missing_attachment` | fewer than two documents, and the sender expected a comparison | NEEDS_REVIEW |
| `unreadable` | empty, corrupt, or an image-only scan | NEEDS_REVIEW |
| `wrong_document` | the pair is not {SI, BL} | NEEDS_REVIEW |
| `blank_value` | a required value is `???` / `____` / `TBA` | NEEDS_REVIEW |
| `untraceable_value` | we produced a value we cannot find in the source | NEEDS_REVIEW |

The last row is the one that earns the stage its place. A value that cannot be
located in the document is a value the system **misread or invented**. Without
the gate, that value flows into the comparison and is reported as a
discrepancy — a confident false alarm. With the gate, it becomes a review case
naming the field we could not read.

The difference is not just a score. An operations team that receives one
fabricated discrepancy stops trusting every flag after it, and a verification
system nobody trusts is worth less than no system at all. This is also the
distinction the problem statement asks for in as many words: *"the system must
distinguish a real discrepancy from a reading or formatting issue."*

Every gate decision also carries a **recovery** — what a human should actually
do (`Ask the sender to re-send the draft BL`, `Open the scan and confirm the
container count`) — so the review queue is a work list, not an error log.

### Stage 6 — Decide

```
gate grounded / no_comparison_needed
    -> MISMATCH when the comparison found differing fields, otherwise OK
gate anything else
    -> NEEDS_REVIEW with the gate's reason; never a defect
```

## 5. Deployment

```
   Vercel                        Render                     OpenAI
┌──────────────┐  HTTPS   ┌────────────────────┐  HTTPS  ┌──────────┐
│ Next.js      │ ───────▶ │ FastAPI + pipeline │ ──────▶ │ model    │
│ dashboard    │ ◀─────── │ (Docker)           │ ◀────── │ API      │
└──────────────┘          └─────────┬──────────┘         └──────────┘
                                    │
                            ┌───────▼────────┐
                            │ managed Postgres│  runs, cases, review actions
                            └────────────────┘
```

The pipeline package has no web or database imports, so the same code runs
in the API container, in the CLI, and in tests.

## 6. What is deliberately NOT in this system

* **No ground-truth file anywhere in `backend/`.** Scoring happens outside the
  solution, through the organisers' own scorer. See `SCORING.md`.
* **No per-email special cases.** No `if email_id == ...`. If a case needs
  bespoke handling, the rule it needs belongs in `labels.py` or `classify/`
  and must be justified by the domain, not by one sample.
* **No address comparison.** See `DATA_NOTES.md` §4.
* **No fuzzy matching on values.** Labels only. See `DATA_NOTES.md` §4.
