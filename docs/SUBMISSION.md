# Submission — everything the Google Form asks for

**Form:** <https://forms.gle/XdfpiUEQDXZ6bdzi9>
**Deadline: 22 September 2026, 12:00 PM.** Submit by 11:00, not 11:55.

Open this file on submission morning and copy from it. Nothing here needs to be
composed on the day.

---

## First part — team details

| Field | Answer |
|---|---|
| **1. Team name** | `DuoCode` |
| **2. Team representative** | name / email / contact number — *fill in on the day* |

## Second part — project details

### 1. Project Name

```
Sentinel
```

### 2. Project Description / Summary

The brief asks for *"a brief summary of the project, including its name, purpose
and problem statement."* All three are in the first three paragraphs below.

The capitalised labels are deliberate: the form field is plain text with no
bold, and a judge reading a hundred of these skims for structure. The last two
paragraphs exist because **AI as a key component** and **meaningful use of cloud
infrastructure** are separately mandatory under the rules — a judge should not
have to open the repository to find out whether we met them.

```
Sentinel — every answer comes with its evidence.

THE PROBLEM. A shipping operations team receives everything in one inbox:
requests to check documents, requests for new shipping instructions, invoice
queries, operational updates and spam. For a document check, someone opens the
Shipping Instruction against the draft Bill of Lading and compares seven fields
— shipper, consignee, notify party, port of loading, port of discharge,
container count and gross weight — before the draft is finalised. Finding the
right emails is manual, comparing by hand is repetitive, the same field is
printed under a different name on each document, and a missed discrepancy
becomes a correction, a delay and rework.

WHAT IT DOES. Sentinel reads that inbox end to end. It classifies every email
into five categories, compares each SI/BL pair across the seven fields, and
reports the exact set that disagree. Every value it extracts carries a pointer
back to the line it was read from, so a reviewer can confirm a flag in seconds
instead of reopening the source document.

AND WHEN IT CANNOT. A missing attachment, an unreadable scan, a blank required
value or the wrong document type becomes a case for a human with the reason and
the evidence attached — never a confident guess. An evidence gate sits after the
comparison and can overrule it: a value that cannot be traced back to a real
line in the document is escalated rather than reported as a discrepancy.

AI. Deterministic readers answer all 520 emails of the graded inbox at no
marginal cost. A model tier is spent only on the tail those rules cannot read —
classifying an ambiguous email, reading a field label the table has never seen,
and a vision path for an image-only PDF with no text layer. Nothing the model
returns is adopted until it has been re-located in the source document.

CLOUD. A FastAPI service in a Docker container on Render, and a Next.js 16
dashboard on Vercel, both deployed from configuration committed in the
repository rather than typed into a dashboard.

RESULT. 1.0000 on the organisers' own scorer across four draws of their
generator at three sizes: 225 planted defects, every one caught with the exact
field set, no false alarms, and all 80 escalations correct. 574 tests.
```

If the field turns out to be a short-answer box, use this instead:

```
Sentinel turns a shipping operations inbox into a per-email decision — and every
decision it is not sure about goes to a human with the evidence attached.

It classifies each email into five categories, compares each Shipping Instruction
against its draft Bill of Lading across seven fields, and reports the exact set
that disagree. Every extracted value carries a pointer back to the line it was
read from, so a reviewer can confirm a flag in seconds. A missing attachment, an
unreadable scan or a blank field becomes a reviewable case with a reason — never a
confident guess.

Deterministic readers answer all 520 emails at no marginal cost; an LLM tier is
spent only on what the rules cannot read. Scored 1.0000 on the organisers' own
scorer across four draws of their generator. FastAPI on Render, Next.js on Vercel.
```

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
