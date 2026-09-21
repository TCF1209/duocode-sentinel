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

The brief asks for *"a brief summary of the project, including its purpose and
the problem it aims to solve."* Paste this:

```
Sentinel — every answer comes with its evidence.

A shipping operations team receives everything in one inbox: requests to check
documents, requests for new shipping instructions, invoice queries, operational
updates, and spam. For a document check, someone opens the Shipping Instruction
against the draft Bill of Lading and compares seven fields — shipper, consignee,
notify party, port of loading, port of discharge, container count and gross
weight — looking for anything wrong before the draft is finalised. It is slow and
repetitive, the same field is printed under different names on the two documents,
and a missed discrepancy becomes a correction, a delay and rework.

Sentinel reads that inbox end to end. It classifies every email into five
categories, compares each SI/BL pair across the seven fields, and reports the
exact set that disagree. Every value it extracts carries a pointer back to the
line it was read from, so a reviewer can confirm a flag in seconds instead of
reopening the source document.

The half that matters in an operations setting is the other one: Sentinel knows
when it cannot decide. A missing attachment, an unreadable scan, a blank required
value or the wrong document type becomes a case for a human, with the reason and
the source evidence attached — never a confident guess. An evidence gate sits
after the comparison and can overrule it: a value that cannot be traced back to a
real line is escalated rather than reported as a discrepancy.

Deterministic readers answer all 520 emails of the graded inbox at no marginal
cost. An LLM tier — classification, extraction and vision — is spent only on the
tail the rules admit they cannot read: an ambiguous email, a field label the table
has never seen, an image-only PDF. The pipeline runs with no API key and no
network, so the demo does not depend on a third-party API being up.

Scored 1.0000 on the organisers' own scorer across four draws of their generator
at three sizes: 225 planted defects, every one caught with the exact field set,
no false alarms, and all 80 escalations correct. 574 tests.

Python and FastAPI in Docker on Render; Next.js 16 and React 19 on Vercel.
```

If the field is short, use this instead:

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

The rules allow a GitHub README explicitly, alongside Google Slides, PDF and
Notion. All four required sections exist in it:

| Required by the rules | Where |
|---|---|
| Technical Architecture | `### Technical architecture` — six stages, module table; `docs/ARCHITECTURE.md` in full |
| Implementation Details | `## Quick start`, `### The API and the dashboard`, `## Repository map` |
| Challenges Faced | `## Challenges faced` |
| Future Roadmap | `## Future roadmap` |

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
