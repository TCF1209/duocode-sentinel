# Narration — read this one while recording

> **Superseded on 24 Sep 2026 — final round.** No video is submitted this
> round; this script survives as the source of the pitch's running order and
> the reasoning behind each beat. Three things in it are stale and must not
> be said aloud: **"574 tests… one pinned to fail"** — the suite is **763
> tests, 0 failing** (25 Sep); the pinned §5.4 defect was fixed on 24 Sep and the open
> one is §5.2 (`email_145`). **"45 mismatches, 21 refused"** — the inbox is
> **46 MISMATCH / 20 NEEDS_REVIEW**; 45/21 was an artefact of a Windows
> checkout rewriting one PDF's line endings (`STATUS.md` 2026-09-24, fixed
> by `.gitattributes`). And the six scan transcriptions are now visible on
> the run page's **Run with the model tier** switch, not only on `/compare`.
> The final-round deck and script are `PITCH_DECK.md`; the day-of checklist
> is `PITCH_DAY.md`.

Words to say, where to be, and the clock. The reasoning, the source of every
number and the list of things **not** to say are in
[`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) — read that once before the first take,
not during.

**Target 4:46. Hard limit 5:00, one mark per 30 seconds over.**
The spoken text is **597 words — 4:11 at a normal 145 wpm** — and the section marks
below already include 35 seconds for clicking, page loads and the run itself,
which leaves **14 seconds of margin**. If you still run long, slide 3 is the one
to tighten: it is prose describing what is already on screen. Do not drop a beat
to save time — each is scoring a different rubric criterion.

> **Before you press record:** wake <https://sdoc-sentinel-api.onrender.com>,
> then start a run, let it finish, and throw it away. A cold first run is
> 41.6 s; the next is 12.7 s, and 12.7 s is what "thirteen seconds" below
> describes. Window 1280×720, on `/pitch` slide 1.

**Three rules this script is built on.** A judge is watching a dozen of these.
So: the first fifteen seconds have to earn the next four minutes; nothing is
said twice, because the rubric tells judges not to credit the same evidence
twice; and never read a number the screen is already showing — say what it
*means* instead.

---

### 0:00 – 0:16 · slide 1 · **the hook**

> A document checker that is confidently wrong is worse than no checker at
> all — because nobody goes back and looks.
>
> We're DuoCode. Sentinel is built on one rule: **it never reports anything it
> cannot prove.**

*Slow down on the last seven words. That sentence is the whole video, and
everything after it is evidence for it. Don't read the team cards — they're on
screen.*

**→ slide 2**

### 0:16 – 0:47 · slide 2 · the problem

> A shipping desk gets five kinds of mail in one inbox. For a document check,
> someone compares the Shipping Instruction against the draft Bill of Lading —
> seven fields, by hand. Miss one and it's a correction, a delay, rework.
>
> And sometimes the check **can't be done at all**: an unreadable scan, a blank
> field, the wrong document. That has to reach a person with the reason — not be
> guessed at.

**→ slide 3**

### 0:47 – 1:29 · slide 3 · three decisions

*Not a list of libraries — a list of choices, each with its reason.*

> Three decisions. **We read structure, not text** — word coordinates rebuild
> the form's rows and columns, because a flattened PDF loses which value belongs
> to which label. **Labels match by meaning, values exactly** — never by
> similarity, because a threshold that forgives a scan artefact also merges two
> real companies. And **the model goes only where the rules admit they can't
> read**, with nothing adopted until it's found again in the source.
>
> Then the **evidence gate** overrules all three: a value nobody can trace to a
> real line becomes a question for a person, never a discrepancy.

**→ slide 4**

### 1:29 – 2:24 · slide 4 · **the part nobody else has**

*The longest beat in the video, on purpose. It is the one claim a team that
didn't do the work cannot make.*

> A perfect score on the dataset you were handed proves you didn't memorise it.
> It doesn't prove the reader works.
>
> So we attacked it ourselves — three thousand perturbed documents, sixteen
> kinds of damage, **no answer key**. The reference is how that same document
> read before we damaged it.
>
> Thirteen of the sixteen don't move at all. On labels we've never seen, the
> model turns a hundred and sixty-eight forced escalations into two — with false
> discrepancies still at zero.
>
> And on the right is the one we didn't have to show you. One masked
> discrepancy — a real mismatch reported as a match. **A defect we hide is worse
> than one we miss**, so one of our 574 tests is pinned to fail until we fix it.

**→ slide 5, then the button through to `/runs`**

---

### 2:24 – 2:48 · press **Start a run**

> This is the real inbox — 520 emails, the organisers' full bundle, on a
> free-tier container.

*While it fills — don't read the tally off the screen:*

> Every one classified, every document pair compared, on rules alone. No model
> call, no network. Thirteen seconds.

### 2:48 – 3:10 · open a **MISMATCH** case

> Seven fields, and the two that disagree are flagged. But look underneath each
> value — **the line it was read from**. That's the promise from the first
> slide, on screen: a reviewer never has to open the source document to trust
> this.

### 3:10 – 3:27 · open a **NEEDS_REVIEW** case

> And here's the other half. No confident guess: the reason it stopped, and the
> evidence a person needs to settle it. The reviewer's correction goes into the
> report, beside the system's own answer.

### 3:27 – 4:18 · go to `/compare` — **the AI beat**

> You shouldn't have to take our word for it — anyone can drop in two documents
> of their own.

*Load the `unfamiliar-labels` pair. Run with the toggle **OFF** first:*

> This pair says *Sender of Goods* where our table says *Shipper*. On rules
> alone the honest answer is that we can't read it — so it escalates rather than
> guessing.

*Now turn the toggle **ON** and re-run:*

> With the model on it reads those labels, every value re-located in the source
> before it's adopted — and it surfaces a real discrepancy on the notify party,
> with the evidence. The badge says **model answered**: the model earning its
> place on exactly the case the rules couldn't do.

---

### 4:18 – 4:40 · back to `/pitch`, slide 5 · impact

*Everything here is new. The 1.0000 was slide 4's job — don't say it again.*

> 520 emails and 124 document pairs — at a conservative estimate, about eleven
> hours of desk work. Sentinel does it in thirteen seconds, and **every decision
> there was made by rules, so it costs nothing to run.**
>
> Cheap because the model is *aimed*, not because it's absent.

### 4:40 – 4:46 · close

> Sentinel, by DuoCode. Every answer comes with its evidence. Thank you.

---

## Four sentences to get right

- **"it never reports anything it cannot prove"** — the hook. Land it slowly;
  every later beat is evidence for that one line.
- **"at a conservative estimate"** before the eleven hours. It is an estimate,
  not a measurement, and the slide says so in print.
- **"thirteen seconds"** is true of a warm container only. See the note at the
  top.
- Never **"our pipeline is 89% AI."** It isn't — the model does no work on the
  graded inbox. `VIDEO_SCRIPT.md` has the other two traps.

## What changed from the previous cut, and why

Ordered against the judges' own rubric, which tells them to score each
criterion independently and **not to credit the same evidence twice**.

| | |
|---|---|
| A hook at 0:00 | The old opening spent its first minute on our names and on the problem statement the judges wrote themselves. Nothing in it separated us from the eleven videos before ours. |
| Slide 3 is decisions, not libraries | Technology Integration's *Weak* band is "integration is superficial… primarily cosmetic" and *Developing* is "relies heavily on boilerplate". A list of library names sounds like both, even when the work isn't. |
| Slide 4 grew from 15s to 37s | Attacking our own reader with no answer key, and publishing the defect it found, is the one claim here that a team which didn't do the work cannot make. It had five words. |
| 1.0000 is said once | It was in slide 4 *and* in Impact. In a five-minute budget that is a wasted beat, and the rubric will not pay for it twice. |
| The run beat stopped reading the screen | "220, 125, 75, 60, 40" is already visible. Saying what it means costs the same seconds and adds something. |
| It now actually fits | The previous cut was **866 spoken words**. Read at a normal pace that is 5:46 before a single click is counted — over the hard limit, and nobody had added it up. This one is 597 words and 4:46 including the waits, measured section by section. |
