# Submission — everything the Google Form asks for

**Form:** <https://forms.gle/XdfpiUEQDXZ6bdzi9>
**Deadline: 22 September 2026, 12:00 PM.** Submit by 11:00, not 11:55.

Open this file on submission morning and copy from it. Nothing here needs to be
composed on the day.

## How the form is actually laid out

Read from the live form, not from the rules PDF — the two differ in one way
that matters. **The description field caps at 150 words, which the PDF never
says.**

It is four pages, Google sign-in required, and the signed-in account's address
is recorded with the response.

| Page | Asks for |
|---|---|
| 1 | Intro, and confirmation of the account's email |
| 2 | Team Name\* · Team Representative Full Name\* · WhatsApp/Phone\* (with country code) · Representative Email\* |
| 3 | Project Name\* · Project Description\* (**≤150 words**) · GitHub URL\* · Live Prototype URL\* · Slide Deck/Documentation URL\* · Video Demo URL\* |
| 4 | not reachable without filling page 3 — expect consent and the resume the rules mention |

\* = required. Page 3 will not advance until every field on it is filled, so
**the video link must exist before the first submit** — there is no submitting
early and adding it later.

Two things the form says that the rules PDF does not:

- **Only one team member should submit, on behalf of the whole team.** Agree who
  before the morning, so two of you do not file two entries.
- **You may edit your submission before the deadline.** That is the safety net
  for a mistyped link, not a licence to file a placeholder video URL.

---

## First part — team details

| Field | Answer |
|---|---|
| **Team Name** | `DuoCode` |
| **Team Representative Full Name** | *fill in on the day* |
| **WhatsApp / Phone Number** | *with country code, e.g. `+60…`* |
| **Team Representative Email Address** | *fill in on the day* |

## Second part — project details

### 1. Project Name

```
Sentinel
```

### 2. Project Description / Summary

**The form caps this at 150 words** — a limit that is nowhere in the rules PDF,
only in the field's own help text. The version below is **148 real words**, and **149** even by a counter naive
enough to treat a spaced em dash as a word — under the cap either way. That
second number is why the asides are in brackets rather than between dashes:
the earlier draft was 148 words and 152 whitespace tokens, so whether it
passed depended on whose counter was used. Count both if you edit it.

That cap forces a decision about what 150 words are *for*, and the answer is
in the judges' own rubric rather than in taste. The detailed criteria are a
public Google Doc linked from page 4 of the rules PDF
([preliminary](https://docs.google.com/document/d/1EiI_mqJYeMN0D-dtZ_npCavVGXVcePFmcZ7O4d4ygQI/edit)),
and its instructions to judges are three lines long:

> • Score each criterion **independently**.
> • **Do not reward the same evidence twice.**
> • Base scores on what is **demonstrated, submitted or clearly explained**.

"Do not reward the same evidence twice" is the one that decides the shape.
Hammering the single most impressive fact earns points in one criterion and
nothing anywhere else, so the description is not an argument — it is a
**distribution problem**. Seven criteria, 148 words, and the strongest thing
we can hand each of them.

An earlier draft that led on the adversarial harness scored well on criterion 4
and left criteria 5 and 7 — 20 points — with no evidence at all, while its one
line of stack for criterion 3 matched that criterion's *Weak* band almost
word for word: *"integration is superficial... or primarily cosmetic."*

Two phrasings are deliberate echoes of the Excellent bands, and both are true:
**"end-to-end"** is criterion 2's own wording, and naming the organisers' own
scorer and their generator is what turns criterion 4's *"critical assumptions
are validated with clear evidence"* into something a judge can check rather
than take on faith.

```
Sentinel — every answer comes with its evidence.

Shipping desks check each draft Bill of Lading against its Shipping Instruction, seven fields, before it is finalised; a missed error means corrections, delays and rework. Sentinel runs that inbox end-to-end, live on Render and Vercel: 520 emails triaged, 124 pairs compared, 13 seconds.

Its rule: never report what it cannot prove. Every value carries the source line it came from; a gate after the comparison sends anything untraceable, blank or damaged to a person. The model tier (ambiguous emails, unseen labels, scanned PDFs) obeys it too, so nothing it returns is adopted until found again in the document.

We attacked it: 16 kinds of damage, no answer key, 982 silently wrong values now zero. 574 tests. A maximum 1.0000 on the organisers' own scorer, on their data and three unseen draws.

Next: per-desk rules, pattern alerts across a carrier's inbox.
```

### What each sentence is there to score

Check this before editing a word out — the cost is usually a whole criterion.

| Rubric criterion | Max | The evidence in the description |
|---|---:|---|
| System Design & Architecture | 15 | a gate that runs *after* the comparison; a model tier behind the deterministic one — two stages and their order |
| Working Core Prototype | **25** | "runs that inbox **end-to-end**, live on Render and Vercel: 520 emails triaged, 124 pairs compared, 13 seconds" |
| Technology Integration | 15 | the model bound to the same rule — "nothing it returns is adopted until found again in the document" — plus the two deployment targets |
| Technical Feasibility & Validation | 15 | 16 kinds of damage with no answer key, 982 → 0, 574 tests, 1.0000 on the organisers' scorer over four draws |
| Problem Statement Understanding | 10 | who (shipping desks), when (before the draft is finalised), why it matters (corrections, delays, rework) |
| Innovation & Solution Approach | 10 | "never report what it cannot prove" — the rule, stated as a rule |
| Practical Value & Potential | 10 | "Next: per-desk rules, pattern alerts across a carrier's inbox" |

**Do not reorder it to put the problem first,** and do not cut the last line to
save space. Problem Statement Understanding is 10 points and already has its
sentence; Practical Value is another 10 and that closing line is its only
evidence in this field.

### 3. GitHub Repository Link

```
https://github.com/TCF1209/duocode-sentinel
```

Public. `README.md` carries the setup instructions the form asks for, verified by
a fresh-clone dry run (`docs/ROADMAP.md` Phase 4).

### 4. Live Prototype / Demo Link

```
https://duocode-sentinel.vercel.app
```

API: <https://sdoc-sentinel-api.onrender.com> — `GET /` reports `ready: true`.

> **Tell the judges about the cold start.** The free tier sleeps after ~15
> minutes idle and the first request then takes 30–60 seconds. The README says so
> at the top; it is worth repeating in the form if there is anywhere to put it.

### 5. Slide Deck / Documentation Link

```
https://github.com/TCF1209/duocode-sentinel/blob/main/README.md
```

The rules allow a GitHub README explicitly, alongside Google Slides, a PDF on
Drive, and Notion. **Nothing needs to be exported to PDF** — this field takes a
URL, not a file.

The README answers all four required items, and says so itself: *This page is
the project documentation*, high on the page, is an index from each requirement
to the section that answers it. It was added for two reasons. Three of the four
requirements matched a heading already, but **Implementation Details** matched
none — it is spread across Quick start, The API and the dashboard, and
Repository map, so a judge scanning headings against the brief's checklist
would not have found it. And this link and the GitHub link (field 3) are the
same repository, so without something on the page announcing itself as the
documentation, field 5 can read as though it were left blank.

| Required by the rules | Where |
|---|---|
| Technical Architecture | [Technical architecture](../README.md#technical-architecture) — six stages and what each decides; `docs/ARCHITECTURE.md` in full |
| Implementation Details | [Quick start](../README.md#quick-start), [The API and the dashboard](../README.md#the-api-and-the-dashboard), [Repository map](../README.md#repository-map), [Verify it yourself](../README.md#verify-it-yourself) |
| Challenges Faced | [Challenges faced](../README.md#challenges-faced) |
| Future Roadmap | [Future roadmap](../README.md#future-roadmap) |

All nine anchor targets were checked to resolve to exactly one heading each.

### 6. Video Demo Link — *maximum 5 minutes*

```
(paste the link here once uploaded)
```

- **YouTube must be unlisted or public.** A private video is not entertained.
- **Google Drive must be shared as "Anyone with the link → Viewer".**
- Script and running order: [`docs/VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md).
- 1 mark is deducted per 30 seconds over 5:00. **Check the uploaded duration,
  not your recording timer.**

---

## Before you press submit

- [ ] Open all four links **in a private window** — that is the only way to catch
      a link that works only because you are signed in.
- [ ] Confirm the deployed dashboard works **from a phone on mobile data**, not
      just the home wifi.
- [ ] Wake the Render API before the judging window; it sleeps after ~15 minutes.
- [ ] Video duration is under 5:00 *as uploaded*.
- [ ] Video visibility is unlisted/public, or Drive is "Anyone with the link".
- [ ] `main` is pushed and Vercel has actually rebuilt from the latest commit —
      the deployed site should match what you recorded.
- [ ] Submitted by **11:00**.

## What the rules require, and where each one is met

| Mandatory | Status |
|---|---|
| AI as a key component | LLM tier for classification, extraction and vision — visible to a judge on `/compare` with the model toggle on |
| Cloud infrastructure, meaningfully used | Docker on Render + Next.js on Vercel, both deployed from this repository by the committed `render.yaml` and `web/vercel.json` |
| Project Description | above |
| Demo Video ≤ 5:00 | `docs/VIDEO_SCRIPT.md` |
| GitHub repo with a clear README | public, dry-run verified |
| Live prototype, publicly accessible | both URLs verified live |
| Slide deck / documentation | README, four required sections present |
