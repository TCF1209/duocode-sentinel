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
only in the field's own help text. The version below is **147**. Count again if
you edit it.

That cap is the whole design constraint. At 150 words there is no room to
restate the problem the judges wrote themselves, so this leads with what the
system does at a scale a reader can picture, then spends the middle on the two
things no other entry will have, and closes on the measurement. AI and cloud
each get a sentence because both are separately mandatory under the rules and a
judge should not have to open the repository to check them.

```
Sentinel — every answer comes with its evidence.

A shipping desk compares each Shipping Instruction against its draft Bill of Lading across seven fields, inside an inbox that also carries invoice queries and spam. Sentinel reads that inbox end to end: 520 emails triaged and 124 document pairs compared in 13 seconds.

Two things are unusual. Every extracted value carries the source line it came from. And an evidence gate runs after the comparison and can overrule it — anything untraceable, blank or OCR-damaged becomes a reviewable case with its reason, never a reported discrepancy.

The model tier reads what rules cannot: ambiguous emails, labels never seen before, scanned PDFs. Nothing it returns is adopted until re-located in the source. FastAPI on Render, Next.js on Vercel.

1.0000 on the organisers' own scorer — dev set plus three held-out seeds never developed against. 225 defects caught, 80/80 escalations correct, 574 tests.
```

**Do not reorder it to put the problem first.** Problem Statement Understanding
is 10 points; Working Core Prototype is 25 and Technology Integration is 15.
The first sentence a judge reads should be doing work the other fields cannot.

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
