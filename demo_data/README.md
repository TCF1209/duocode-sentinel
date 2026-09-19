# demo_data — the curated inbox the live demo serves

**Generated. Do not edit by hand.** Re-create it with:

```bash
.venv/Scripts/python.exe scripts/make_demo_data.py
```

30 emails and 31 attachments — 186 KB of inbox JSON and attachments, drawn from the 520-email participant bundle.

## Why this exists

`data/` is git-ignored and Render builds from git, so a deployed
container has no inbox and `POST /runs` has nothing to run over. This
is the smallest subset that still tells the whole story: every
category, every escalation reason, a real defect in every attachment
format, and enough clean cases that the demo looks like an operations
inbox rather than a fault museum.

## What it is not

It carries **no labels** — inbox JSON and attachments only, exactly the
participant-bundle shape the organisers confirmed may be published.
Nothing from the organisers' package is here, and nothing from it ever
may be (`docs/SCORING.md` §3).

It is also **deliberately not representative**: defects and escalations
are over-sampled so a five-minute demo can show them. Counting statuses
here tells you nothing about the pipeline's accuracy — that claim lives
in `docs/SCORING.md`, measured over all 520 emails.

## How it was chosen

`scripts/make_demo_data.py` joins the bundle to a pipeline run's
`report.json` and fills one slot at a time, scanning candidates in
`email_id` order and taking the first that fits. No randomness: the
same inputs give a byte-identical subset, and every pick can be argued
with. The script asserts the coverage below before it writes, and never
opens `data/_grader/`.

## The slots, and what each one is here to show

| email | slot | why it is in the set |
|---|---|---|
| `email_003` | `pair.draft_requested` | Zero attachments, asking us to PRODUCE a draft BL — correctly OK, nothing to compare yet (DATA_NOTES §5a, case A). |
| `email_506` | `pair.attachments_dropped` | Zero attachments, asking us to CHECK documents the sender believes they attached — correctly NEEDS_REVIEW (DATA_NOTES §5a, case B). |
| `email_501` | `escalate.wrong_doc_type` | The attached 'BL' is really another document entirely — the doc-type classifier catches it before any field is compared. |
| `email_512` | `escalate.unreadable_scan` | An image-only scanned PDF pair: no text layer, so nothing can be read deterministically. This is the one case the vision path transcribes — and it still escalates, because a transcript is reviewer evidence, not an extracted value. |
| `email_511` | `escalate.unreadable_corrupt` | A different failure mode in the same reason: a PDF that will not open at all, next to a perfectly readable SI. Half a readable pair is still not a comparison. |
| `email_516` | `escalate.missing_value` | A required field left as ??? / TBA. CLAUDE.md rule 4: a blank is NEEDS_REVIEW, never a MISMATCH — reporting a discrepancy on an empty field is a false alarm that costs precision. |
| `email_507` | `escalate.half_a_pair` | A comparison request carrying exactly ONE document. Distinct from the zero-attachment case above and worth showing beside it: you cannot compare a pair with half a pair. |
| `email_313` | `defect.pdf` | A real discrepancy found inside a two-column PDF form — the coordinate-based reader, on the layout that defeats a line-oriented parser (DATA_NOTES §3). |
| `email_097` | `defect.docx_xlsx` | A discrepancy across a .docx SI and an .xlsx BL — different readers on each side, Chinese label text on one of them. |
| `email_243` | `defect.xlsx` | A discrepancy between two spreadsheets, where the weight is stored as a bare number rather than '131,058 KG' (DATA_NOTES §4). |
| `email_013` | `defect.txt_one_field` | The smallest real defect: one field out of seven differs. 20 of the bundle's 46 defects are this size. |
| `email_004` | `defect.txt_two_fields` | A two-field defect, the other 26. Picking a party-name defect here also shows the address-block trap: the generator swaps the name and leaves the old address behind, so only the entity name is compared. |
| `email_145` | `defect.field.shipper` | Puts `shipper` on the discrepancy screen — no compared field should be one the demo never shows failing. |
| `email_059` | `clean.pdf` | A PDF pair that matches on all seven fields — the coordinate reader producing a clean bill of health, not just catching faults. |
| `email_005` | `clean.xlsx` | A clean spreadsheet pair. |
| `email_055` | `clean.docx_xlsx` | A clean .docx/.xlsx pair — the office readers agreeing across two different label vocabularies. |
| `email_001` | `clean.txt.1` | The everyday case: a plain-text pair, all seven fields matched, no action needed. |
| `email_009` | `clean.txt.2` | A second one, because one clean case reads as an anecdote. |
| `email_007` | `category.si_request.1` | An SI request. Every one of these ends with 'revert with draft BL once available' — the phrase 'draft BL' alone must not route an email to BL_COMPARISON (DATA_NOTES §6). |
| `email_002` | `category.invoice_query.1` | A billing query: charges, freight, credit notes. Nothing to compare, and nothing to escalate. |
| `email_008` | `category.si_request.2` | A second/third SI_REQUEST, on a different subject template. |
| `email_010` | `category.invoice_query.2` | A second/third INVOICE_QUERY, on a different subject template. |
| `email_014` | `category.si_request.3` | A second/third SI_REQUEST, on a different subject template. |
| `email_017` | `category.invoice_query.3` | A second/third INVOICE_QUERY, on a different subject template. |
| `email_012` | `general.si_trap` | GENERAL, not SI_REQUEST — a bulk reminder whose subject says 'Submit SI'. The classifier keys off the real signal, not the keyword (DATA_NOTES §6). |
| `email_098` | `general.bl_trap` | GENERAL, not BL_COMPARISON — an operational notice about BLs with nothing attached and nothing to check. |
| `email_011` | `general.routine` | Ordinary operational traffic: a schedule update or planning note. |
| `email_015` | `category.spam.1` | Spam. The smallest class and the most separable one — and under macro-F1 one spam error costs as much as five BL_COMPARISON errors, so it is never the class to leave out. |
| `email_116` | `category.spam.2` | Another spam archetype — phishing, crypto, storage-full. Three templates, not three copies of one. |
| `email_134` | `category.spam.3` | Another spam archetype — phishing, crypto, storage-full. Three templates, not three copies of one. |

## What is in it

**Category**

- `BL_COMPARISON` — 18
- `GENERAL` — 3
- `INVOICE_QUERY` — 3
- `SI_REQUEST` — 3
- `SPAM` — 3

**Status**

- `MISMATCH` — 6
- `NEEDS_REVIEW` — 6
- `OK` — 18

**Escalation reason**

- `missing_attachment` — 2
- `missing_value` — 1
- `unreadable` — 2
- `wrong_doc_type` — 1

**Attachment shape**

- `docx+xlsx` — 2
- `pdf+txt` — 1
- `pdf-only` — 3
- `txt` — 1
- `txt-only` — 7
- `xlsx-only` — 2

## Running it

```bash
.venv/Scripts/python.exe backend/run.py --data demo_data --out runs/demo
```

The API serves it by pointing `SENTINEL_DATA_ROOT` at this folder;
`backend/api/main.py` falls back to `data/bundle` for local work.
