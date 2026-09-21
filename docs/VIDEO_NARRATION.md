# Narration — read this one while recording

Words to say, where to be, and the clock. The reasoning, the source of every
number and the list of things **not** to say are in
[`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) — read that once before the first take,
not during.

**Target 4:50. Hard limit 5:00, one mark per 30 seconds over.**

> **Before you press record:** wake <https://sdoc-sentinel-api.onrender.com>,
> then start a run and let it finish and throw it away. A cold first run is
> 41.6 s; the next is 12.7 s, and 12.7 s is what "thirteen seconds" below is
> describing. Window 1280×720, on `/pitch` slide 1.

---

### 0:00 – 0:20 · slide 1

> We're DuoCode — Tang Chye Fong and Lim Yee Teng, from Asia Pacific
> University. Our project is **Sentinel**, and its one promise is the line on
> the screen: every answer comes with its evidence.

*Don't read the team cards out. They're on screen.*

**→ next slide**

### 0:20 – 1:00 · slide 2

> A shipping desk gets five kinds of mail in one inbox. When someone asks them
> to check a document, a person opens the Shipping Instruction next to the
> draft Bill of Lading and compares seven fields — shipper, consignee, notify
> party, load port, discharge port, containers, gross weight — before the draft
> is finalised.
>
> Three things make that slow. Finding the right emails is manual. Comparing by
> hand is repetitive, and a missed discrepancy becomes a correction, a delay and
> rework. And the same field is printed differently on the two documents — one
> says *Port of Loading*, the other says *Load Port*, and nothing in the text
> says they're the same thing.
>
> There's a fourth case, and it's the one we built around: **sometimes the check
> can't be done at all.** An unreadable scan, a blank field, the wrong document
> attached. That has to reach a person with the reason attached — not be guessed
> at, and not fail quietly.

**→ next slide**

### 1:00 – 1:40 · slide 3

> The core is deterministic and runs with no API key and no network. pdfplumber
> rebuilds a PDF's rows and columns from word coordinates rather than reading
> flattened text. Labels resolve in three passes — exact, then regex, then fuzzy
> with a minimum-length guard. Values are canonicalised and compared **exactly**
> — never by similarity score, because a threshold loose enough to forgive a
> scanning artefact also merges two genuinely different companies.
>
> A model tier sits behind that for three jobs the rules can't do: classifying
> an ambiguous email, reading a field label we've never seen, and transcribing
> an image-only PDF with no text layer.
>
> And after both of them, the **evidence gate** — a value nobody can trace back
> to a real line in the document is never reported as a discrepancy. It goes to
> a person instead.
>
> Python and FastAPI in Docker on Render; Next.js 16 on Vercel; 574 tests — one
> of them deliberately failing, and that's worth coming back to.

**→ next slide**

### 1:40 – 1:55 · slide 4

> This isn't just the dev set — the same rules score 1.0000 on three more
> datasets we never trained against. And on labels we've never seen, the model
> turns a hundred and sixty-eight forced escalations into two, without a single
> wrong answer. The one thing we haven't fixed yet is up there too.

*Don't read the two callout cards word for word — they're dense enough to be
read off the screen.*

**→ next slide, then click the button through to `/runs`**

---

### 1:55 – 2:20 · press **Start a run**

> This is the real inbox — 520 emails, the organisers' full bundle, running on a
> free-tier container.

*Let the progress panel fill. It holds for a couple of seconds after the run
finishes — point at the final tally while it's up:*

> Thirteen seconds. 220 document checks, 125 instruction requests, 75 invoice
> queries, 60 general, 40 spam. 45 mismatches, and 21 cases it refused to
> decide.

### 2:20 – 2:55 · open a **MISMATCH** case

> Here's the Shipping Instruction on the left, the draft Bill of Lading on the
> right, seven fields, and the ones that disagree are flagged. The part that
> matters is underneath each value — **the line it was read from**. A reviewer
> doesn't have to go back to the source document to trust this; the source is
> already here. That's what lets us tell "the document genuinely says something
> different" apart from "we read the document wrong".

### 2:55 – 3:15 · open a **NEEDS_REVIEW** case

> And this is the other half. No confident guess — the reason it stopped, and
> the evidence a person needs to settle it. When the reviewer corrects it, the
> correction goes into the report, and the system's own answer stays visible
> beside it rather than being overwritten.

### 3:15 – 4:00 · go to `/compare` — **this is the AI beat**

> Judges shouldn't have to take our word for it, so anyone can drop in two
> documents of their own.

*Load the `unfamiliar-labels` pair. Run it with the toggle **OFF** first:*

> This pair uses wording our label table has never seen — *Sender of Goods*
> instead of *Shipper*, *Deliver To* instead of *Consignee*. On rules alone the
> honest answer is that we can't read it, so it escalates.

*Now turn the toggle **ON** and re-run:*

> With the model tier on, it reads the unfamiliar labels, every value gets
> re-located in the source document before it's adopted — and there's a real
> discrepancy in here on the notify party that it surfaces, with the evidence.
> The badge says **model answered**. That's the model earning its place on the
> case the rules admitted they couldn't do.

---

### 4:00 – 4:40 · back to `/pitch`, slide 5

> Scored on the organisers' own scorer across four draws of their generator, at
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
> Cheap because the model is *aimed*, not because it's absent.

### 4:40 – 4:50 · close

> Sentinel, by DuoCode. Every answer comes with its evidence. Thank you.

---

## Three sentences to get right

- **"at a conservative estimate"** before the eleven hours. It is an estimate,
  not a measurement, and slide 5 says so in print.
- **"thirteen seconds"** only works on a warm container. See the note at the
  top.
- Never **"our pipeline is 89% AI"**. It isn't — the model does no work on the
  graded inbox. `VIDEO_SCRIPT.md` has the other two traps.
