# Decisions

Each entry: what we chose, what we rejected, and the reason. Written as we go,
so the slide deck's *Challenges Faced* section has real material instead of
reconstructed memory — and so nobody re-opens a settled question at 2am.

---

## D1 · Deterministic first, LLM second

**Chosen.** Every stage attempts a rule-based answer before reaching for a
model, and records which one answered (`decided_by`).

**Rejected.** Sending every email and every document to an LLM.

**Why.** Three reasons, in order of weight.

1. *Accuracy.* The headline metric requires the **exact set** of mismatched
   fields — flagging one of two scores zero for that email. A parser that reads
   `Total Containers: 5 x 40'HC` is right every time; a model asked the same
   question is right almost every time, and "almost" across 46 graded emails is
   the whole gap between first and fourth.
2. *Cost.* A real operations inbox is thousands of emails a day. Spending a
   model call to recognise an obvious spam message is indefensible in
   production. The organisers' own scorer reports `resolved by rules (cost)`,
   so they are measuring this too.
3. *Demo safety.* With no API key and no network the pipeline still runs end to
   end. A demo that depends on a third-party API staying up is a demo that
   eventually fails in front of judges.

The model is not decoration — it earns its keep on ambiguous intent, unfamiliar
label wording, layouts we have not seen, and reading scans.

**What this pattern is called, so we use the field's words and not our own.**
This is an **LLM cascade** with **confidence-based deferral**: a cheap tier
answers, a margin decides whether to escalate, and the expensive tier sees only
the tail. FrugalGPT ([arXiv:2305.05176](https://arxiv.org/abs/2305.05176), 2023)
is the reference for the cost argument; the deferral rule has its own
literature. We did not invent the architecture and should not imply we did.

What is ours is the **operating point**, and it is the falsifiable part: on
this inbox the cheap tier answers 520 of 520, so the cascade never escalates
and the expensive tier costs nothing. That is the optimum for a cascade whose
cheap tier is accurate on the distribution, not a sign the tier is dead — but
the honest corollary is that insurance never claimed on is insurance never
tested, which is why `ADVERSARIAL.md` §8 measures the tier on inputs the
generator cannot produce and `/compare` lets a judge fire it by hand.

---

## D2 · Values compared with exact equality, never fuzzily

**Chosen.** Canonicalise (drop legal suffixes, strip punctuation and UN/LOCODEs,
parse numbers), then compare exactly. Fuzzy matching is used for **labels only**.

**Rejected.** A similarity threshold on values, which is the obvious first
instinct and would look more "intelligent".

**Why.** The entity pools contain genuinely near-identical names:

```
APRIL FINE PAPER TRADING      vs  APRIL FINE PAPER TRADING (MIDDLE EAST) FZE
NANTONG, CHINA                vs  RUGAO/NANTONG/SHANGHAI, CHINA
```

Those are different shippers and different load ports. Any threshold loose
enough to merge `KPP-ANTALIS (SINGAPORE) PTE. LTD.` with `KPP-ANTALIS SINGAPORE`
also merges the two pairs above — and a planted discrepancy silently disappears.
Fuzzy matching would make the system *look* more tolerant while making it
*quietly* worse.

---

## D3 · PDFs are read from word coordinates, not from extracted text

**Chosen.** Group words into rows by vertical position, find the label column
and the value column by their left edges, treat a row with no label-column word
as a continuation of the previous value.

**Rejected.** `pdftotext`, or any line-oriented parse of a PDF text layer.

**Why.** Measured, not assumed. The dataset's PDFs are two-column forms with
multi-line address blocks. `pdftotext -layout` produces:

```
To the Order of    77 ROBINSON ROAD, #21-01     <- not the consignee
Load Port          8 TEMASEK BOULEVARD          <- not the load port
```

which yields a *confident* false discrepancy on two fields at once. The
coordinate reconstruction produces the document as a human reads it and needs no
model to do it. Full detail in `DATA_NOTES.md` §3.

**Cost of the decision.** Two bugs we had to find: single-linkage clustering
chained every word into one cluster and put the column split in open space; and
fuzzy label matching fired on the fragment `TOTAL` and mapped it to
`Total Containers`. Both are fixed and both now have tests.

---

## D4 · The evidence gate is a stage, not a helper

**Chosen.** A dedicated stage between comparison and decision that can **veto**
a defect: no discrepancy is reported unless both sides trace to a real span in a
real document.

**Rejected.** Folding "we could not read this" into the comparison as an
`UNCOMPARABLE` verdict and moving on.

**Why.** A value that cannot be located in its source is a value the system
misread or invented. Reported as a discrepancy it is a false alarm; routed to a
human it costs nothing and points at the exact field we could not read. Beyond
the metric, one fabricated flag teaches an operations team to distrust every
flag after it — and a verification system nobody trusts is worth less than no
system at all.

This also answers the problem statement directly: *"the system must distinguish
a real discrepancy from a reading or formatting issue."*

---

## D5 · Intent, not attachment count, decides a missing attachment

**Chosen.** An intent check distinguishes "please send me a draft BL" from
"please compare the documents I attached".

**Rejected.** `len(attachments) == 0 -> escalate`.

**Why.** Two emails in the set both have zero attachments and **opposite**
correct outcomes; only the sender's intent separates them (`DATA_NOTES.md` §5a).
Escalating every attachment-free comparison email would bury a real review queue
under routine requests — the failure mode that makes operations teams turn
alerting off.

Ambiguity resolves to *not* escalating, because wasting an operator's attention
is the more expensive error.

---

## D6 · markitdown as a fallback reader, not the primary one

**Chosen.** Precise readers for `.txt`, `.pdf`, `.docx`, `.xlsx`; markitdown for
anything else that arrives.

**Rejected.** Using markitdown as the single universal reader.

**Why.** Tested on our own data. It handles `.docx` and `.xlsx` well and
survives the corrupt and scanned edge cases sensibly, but on the two-column PDFs
it returns the label and the value **glued together with no separator**
(`Load Port RUGAO/NANTONG/SHANGHAI, CHINA`), and it returns a flat document with
**no provenance**. Recovering the boundary would need either a fixed label list —
which fails on exactly the "same field, different wording" challenge this problem
is built around — or a model call on 100% of PDFs. And losing provenance would
cost us the evidence locators that the gate and the reviewer UI depend on.

As a fallback it is genuinely valuable: real inboxes contain `.pptx`, `.html`,
`.msg` and images, and thirty lines buys honest coverage of all of them.

---

## D7 · Dependencies we turned down

| Rejected | Reason |
|---|---|
| **Docling** | Measured: 84 packages including `torch`, `torchvision`, `transformers`, `accelerate`, `opencv`. ~3 GB plus runtime model downloads. Cannot be built on our deployment tier. Excellent library; wrong constraint. |
| **unstructured** | Same weight class, and its strongest parsing sits behind a paid API. |
| **PyMuPDF / pymupdf4llm** | AGPL-3.0. The rules state participants retain their IP, and copyleft contaminates that. |
| **instructor / outlines / BAML** | The OpenAI SDK has native structured outputs. One schema of seven fields does not justify another abstraction layer. |
| **LangChain / LlamaIndex** | This is deterministic field extraction, not retrieval. Adding an agent framework would cost architecture marks, not earn them. |
| **Label Studio / Argilla** | Annotation platforms, not review queues. Ours is one screen. |

---

## D8 · How we evaluate ourselves

**Chosen.** Score with the organisers' own scorer, keep the answer key out of
the repository and out of the pipeline's reach, and prove generalisation by
regenerating the dataset with an unseen seed.

**Rejected.** Tuning against the labels; and also the opposite extreme, not
measuring at all.

**Why.** The problem statement tells participants to self-evaluate, and the
provided `/submit` endpoint runs the same `scoring.py` we run locally. Using it
is the sanctioned workflow. Reading the labels to shape rules is not — and a
held-out seed is the only honest way to tell the two apart. Details and the
exact rules we hold ourselves to are in `SCORING.md` §3.
