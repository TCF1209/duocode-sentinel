# Demo video — script and running order

**Hard limit 5:00. One mark is deducted per 30 seconds over, so the target is
4:30** and the thirty seconds left over are the margin for a sentence that runs
long, not spare time to fill.

The brief names five parts and this is their order — *Quick intro · The problem ·
Tech stack · Live demo · Impact*. Slides 1–4 of `/pitch` are those first three
parts and the last one, which is why the whole recording is one browser tab with
no cutting to a deck.

---

## Before you press record

| | |
|---|---|
| **Wake Render** | Open <https://sdoc-sentinel-api.onrender.com> and wait for `ready: true`. Cold start is **30–60 s** and it sleeps again after ~15 minutes idle. Do this last, right before recording. |
| **Window size** | 1280×720. Every `/pitch` screen is built to fit that without a scrollbar. |
| **Browser** | Hide bookmarks, close other tabs, no notifications. |
| **Start position** | `/pitch` on slide 1. Arrow keys advance; don't hunt for the dots on camera. |
| **Have ready** | The `unfamiliar-labels` sample pair on `/compare` — that is the AI beat. |

**The one thing that will catch you out.** The badge on every case in `/runs`
says `rule`, and it is supposed to: `decided_by` is `rule` for all 520 emails and
the deployed API has `llm_runs_allowed: false` as a cost guard. **Do not promise
"watch the AI work" over the inbox run.** The model is visible on `/compare`
with the toggle on, and nowhere else. Plan the sentence so it lands there.

---

## 0:00 – 0:20 · Quick intro *(slide 1)*

> "We're DuoCode — Tang Chye Fong and Lim Yee Teng, from Asia Pacific
> University. Our project is **Sentinel**, and its one promise is the line on
> the screen: *every answer comes with its evidence*."

Don't read the cards out. They are on screen; let them be read.

## 0:20 – 1:00 · The problem *(slide 2)*

> "A shipping desk gets five kinds of mail in one inbox. When someone asks them
> to check a document, a person opens the Shipping Instruction next to the
> draft Bill of Lading and compares seven fields — shipper, consignee, notify
> party, load port, discharge port, containers, gross weight — before the draft
> is finalised.
>
> Three things make that slow. Finding the right emails is manual. Comparing by
> hand is repetitive, and a missed discrepancy becomes a correction, a delay and
> rework. And the same field is printed differently on the two documents — one
> says *Port of Loading*, the other says *Load Port*, and nothing in the text
> says they are the same thing.
>
> There is a fourth case, and it is the one we built around: **sometimes the
> check cannot be done at all.** An unreadable scan, a blank field, the wrong
> document attached. That has to reach a person with the reason attached — not
> be guessed at, and not fail quietly."

## 1:00 – 1:40 · Tech stack *(slide 3)*

> "The core is deterministic and runs with no API key and no network.
> `pdfplumber` rebuilds a PDF's rows and columns from word coordinates rather
> than reading flattened text. Labels resolve in three passes — exact, then
> regex, then fuzzy with a minimum-length guard. Values are canonicalised and
> compared **exactly** — never by similarity score, because a threshold loose
> enough to forgive a scanning artefact also merges two genuinely different
> companies.
>
> A model tier sits behind that for three jobs the rules can't do: classifying
> an ambiguous email, reading a field label we've never seen, and transcribing
> an image-only PDF with no text layer.
>
> And after both of them, the **evidence gate** — a value nobody can trace back
> to a real line in the document is never reported as a discrepancy. It goes to
> a person instead.
>
> Python and FastAPI in Docker on Render; Next.js 16 on Vercel; 574 tests."

## 1:40 – 3:45 · Live demo

Click through to `/runs` from the slide's own button.

**1:40 – 2:05 · the run.** Press **Start a run**.

> "This is the real inbox — 520 emails, the organisers' full bundle, running on
> a free-tier container."

Let the progress panel fill. It now holds for a couple of seconds after the run
finishes, so point at the final tally while it's up:

> "Thirteen seconds. 220 document checks, 125 instruction requests, 75 invoice
> queries, 60 general, 40 spam. 45 mismatches, and 21 cases it refused to
> decide."

**2:05 – 2:40 · a MISMATCH case.** Open one.

> "Here's the Shipping Instruction on the left, the draft Bill of Lading on the
> right, seven fields, and the ones that disagree are flagged. The part that
> matters is underneath each value — **the line it was read from**. A reviewer
> doesn't have to go back to the source document to trust this; the source is
> already here. That's what lets us tell 'the document genuinely says something
> different' apart from 'we read the document wrong'."

**2:40 – 3:00 · a NEEDS_REVIEW case.** Open one from the escalated four.

> "And this is the other half. No confident guess — the reason it stopped, and
> the evidence a person needs to settle it. When the reviewer corrects it, the
> correction goes into the report, and the system's own answer stays visible
> beside it rather than being overwritten."

**3:00 – 3:45 · `/compare` — this is the AI beat.**

> "Judges shouldn't have to take our word for it, so anyone can drop in two
> documents of their own."

Load the `unfamiliar-labels` pair. Run it **with the toggle off** first:

> "This pair uses wording our label table has never seen — *Sender of Goods*
> instead of *Shipper*, *Deliver To* instead of *Consignee*. On rules alone the
> honest answer is that we can't read it, so it escalates."

Now turn the toggle on and re-run:

> "With the model tier on, it reads the unfamiliar labels, every value gets
> re-located in the source document before it's adopted — and there's a real
> discrepancy in here on the notify party that it surfaces, with the evidence.
> The badge says **model answered**. That's the model earning its place on the
> case the rules admitted they couldn't do."

## 3:45 – 4:25 · Impact *(back to slide 4)*

> "Scored on the organisers' own scorer across four draws of their generator, at
> three different sizes: **1.0000**. 225 planted defects, every one caught with
> the exact set of fields wrong, no false alarms, and all 80 escalations
> correct.
>
> One inbox is 520 emails to triage and 124 document pairs to compare. At a
> conservative estimate that's around eleven hours of desk work. Sentinel does
> it in thirteen seconds, and **every decision on that inbox was made by rules —
> it costs nothing to run.** The model is thirteen hundredths of a cent per
> document, spent only on the tail the rules can't read.
>
> Cheap because the model is *aimed*, not because it's absent."

## 4:25 – 4:35 · Close

> "Sentinel, by DuoCode. Every answer comes with its evidence. Thank you."

---

## Every number spoken above, and where it is from

Re-measured on `bb07c1a` against the committed 520-email `bundle_data/`, not
copied from an older doc.

| Said in the video | Verified |
|---|---|
| 520 emails; 220 / 125 / 75 / 60 / 40 by category | fresh pipeline run — `metrics.json` |
| 45 MISMATCH, 21 NEEDS_REVIEW, 4 escalation reasons | same run |
| 124 document pairs compared | counted from `report.json` — cases carrying field comparisons |
| every decision made by rules, $0 | `decided_by_rule: 520`, `llm_calls: 0`, `rule_share: 1.0` |
| 574 tests | `pytest --junitxml`: 574 tests, 0 failures, 0 errors |
| 1.0000 · 225 defects · 80/80 escalations | `docs/SCORING.md` §4.1 — 46+57+31+91 across four seeds |
| $0.0013 per document, 178 calls / $0.2447 | `docs/ADVERSARIAL.md` §8 |
| 13 seconds | the deployed free-tier container. **A laptop does it in 1.2 s** (2.37 ms/email) — say 13, because 13 is what the screen will show. |
| ~11 hours of desk work | **an estimate, not a measurement** — 20 s an email, 4 min a pair. Say "at a conservative estimate" out loud, as slide 4 does in print. |

## Things not to say

- **"Our pipeline is 89% AI."** It is not. The model does no work on the graded
  inbox. The 89% is the recovery rate on documents *we* perturbed to create
  wording the generator never emits (`ADVERSARIAL.md` §8) — quote it as "here is
  what happens when a document arrives with wording we have never seen".
- **"We score 1.0000, so it's solved."** Four draws of one generator.
  `SCORING.md` §4.1 says why that is not four independent tests.
- **"It never gets anything wrong."** `ADVERSARIAL.md` §5.4 pins a defect we
  have found and not fixed, with a strict `xfail`. Don't claim past it.
