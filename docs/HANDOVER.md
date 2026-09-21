# Handover — for Chye Fong (TCF1209)

**Deadline today, 22 Sep, 12:00 PM. Aim to submit by 11:00.**

Two of these only you can do. Everything else is ready and waiting on them.

---

## 1. Make the repository public — 30 seconds, blocking everything

**Right now `github.com/TCF1209/duocode-sentinel` returns 404 to anyone not
signed in as you.** It looks fine from your browser because you are the owner.
It is not fine for a judge.

Two of the six mandatory form fields point at this repository — the GitHub
link and the Slide Deck / Documentation link — so as things stand, **both are
dead links** and the rules require *"a public link to the project's source
code"*.

1. <https://github.com/TCF1209/duocode-sentinel/settings>
2. Scroll to the bottom — **Danger Zone**
3. **Change repository visibility** → **Change to public**
4. Type the repository name to confirm

**Then check it from outside your own login:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://github.com/TCF1209/duocode-sentinel
```

`200` means judges can see it. `404` means it did not take.

### It is safe to publish — this was audited, not assumed

Run before writing this, on the full history, not just the working tree:

| Checked | Result |
|---|---|
| `.env`, `ground_truth.json`, `score_cli.py`, the generator, `_grader/` ever committed in **any** commit | **never** |
| Whole-history diff scanned for `sk-…`, `AKIA…`, `ghp_…`, `xox…` | **0 matches** |
| `data/` ignored, and files tracked under it | ignored by `/data/`; **0 tracked** |
| `.env.example` | `OPENAI_API_KEY=` — empty |

The organisers' mis-sent package has never been in this repository and cannot
appear by making it public.

---

## 2. Trigger Vercel once more — **and this one is before you record**

Your empty commit `8029435` worked and put the five-screen `/pitch` live. Then
`b261600` had to fix something on slide 4, and being pushed from the other
machine it was blocked again. **Checked against production: the old, wrong card
is still what the camera would film.**

```bash
git pull
git commit --allow-empty -m "chore: ship the slide 4 correction"
git push origin main
```

**Verify before recording** — open <https://duocode-sentinel.vercel.app/pitch>,
go to slide 4, and read the orange card on the right. It must talk about a
**masked discrepancy**. If it still says *"151 of 188 documents"*, the build has
not landed and the take will contain a claim our own `docs/ADVERSARIAL.md`
contradicts.

### What that fix was, in case it comes up in questions

The card said OCR digit confusion invents a defect on 151 of 188 documents, and
credited the pinned test to it. Both wrong, and both wrong in the direction of
making us look worse. `ADVERSARIAL.md` line 414 is a before-and-after table —
`false discrepancies | 151 | 0` — so 151 is the figure *before* the digit guard
landed in September; re-running the harness on this commit gives zero. And the
strict `xfail` lives in `test_compare_wrap.py`, pinning something else: when two
parties share an identical first line, the repair that rejoins a wrapped name
can complete the notify party from the consignee's block above it, and report a
real mismatch as a match. One masked discrepancy across 3,008 perturbed
documents. That is the truer card, and a better one — a defect we hide is worse
than one we miss.

What had happened, for the record: Vercel's Hobby plan refuses to build a
commit pushed by anyone who is not the project owner, the project sits under
`vercel.com/tang-chye-fongs-projects/…`, and GitHub was showing **"Vercel —
Deployment was blocked"** on every commit pushed from the other machine. A
commit pushed by you at the tip of `main` is what it wants.

**If you see a red ✗ on a later commit, check what it changed before acting.**
Anything touching only `docs/` cannot alter the deployed app, so a blocked
build on a documentation commit leaves production correct and is not worth a
second empty commit. Only re-trigger when something under `web/` has not
shipped.

**Never use the dashboard's "Redeploy" button** — it rebuilds the last commit
that *successfully* built, which is the old one.

---

## 3. Record the demo video — the only mandatory piece still missing

Script and timings: [`VIDEO_NARRATION.md`](VIDEO_NARRATION.md) is the one to
read while recording. [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) is the same thing
with the reasoning, the source of every number, and a list of things not to
say — read that one **once**, before the first take.

Three things that will cost you the take if you skip them:

1. **Wake Render, then throw away one full run.** Measured on the live
   deployment: the first run after the container has been idle takes **41.6 s**,
   the next **12.7 s**. The script says "thirteen seconds" — true of a warm
   container, and a lie about a cold one.
2. **1280×720**, bookmarks hidden, notifications off.
3. **The inbox run will never show an `llm` badge**, and that is correct —
   `decided_by` is `rule` for all 520 and the deployed API has
   `llm_runs_allowed: false` as a cost guard. The model is visible on
   `/compare` with the toggle on, and nowhere else. Do not promise "watch the
   AI work" over the run.

**Uploading:** YouTube set to **Unlisted** (a private video is not accepted), or
Google Drive shared as **"Anyone with the link → Viewer"**. Check the duration
*after* upload — 1 mark per 30 seconds over 5:00.

---

## 4. The form — every answer, ready to paste

<https://forms.gle/XdfpiUEQDXZ6bdzi9> · four pages · Google sign-in required ·
**only one of us submits, on behalf of the team.** Page 3 will not advance
until every URL is filled, so the video link has to exist before the first
submit. A submission can be edited before the deadline.

Full text and the reasoning behind the description:
[`SUBMISSION.md`](SUBMISSION.md).

| Field | Answer |
|---|---|
| Team Name | `DuoCode` |
| Representative name / WhatsApp / email | yours, phone with `+60` country code |
| Project Name | `Sentinel` |
| Project Description | **148 words** — copy from [`SUBMISSION.md`](SUBMISSION.md); the field caps at 150 |
| GitHub Repository URL | `https://github.com/TCF1209/duocode-sentinel` |
| Live Prototype / Demo URL | `https://duocode-sentinel.vercel.app` |
| Slide Deck / Documentation URL | `https://github.com/TCF1209/duocode-sentinel/blob/main/README.md` |
| Video Demo URL | the unlisted YouTube or shared Drive link |

---

## 5. Before pressing submit

- [ ] Open all four URLs **in a private window**. That is the only way to catch
      a link that works solely because you are signed in — which is exactly the
      bug in step 1.
- [ ] The dashboard loads on a phone, on mobile data.
- [ ] Wake Render again shortly before you submit; it sleeps after ~15 minutes
      and the first request then takes 30–60 seconds.
- [ ] Video duration under 5:00 **as uploaded**, visibility unlisted/public.
- [ ] `git status` before any last commit — **do not `git add -A`.** There is an
      untracked `duocode-sentinel-main/` copy of the whole project sitting
      inside the working directory, plus `pytest_result.txt` and
      `web/.claude/`. None of them belong in a public repository.
- [ ] Submitted by **11:00**, not 11:55.

---

## What is already done, so you do not redo it

Verified by running it, on the current commit, not quoted from an older
document:

| | |
|---|---|
| `pytest` | 574 tests, 0 failures, 0 errors |
| `eslint` · `tsc --noEmit` · `npm run build` | all clean, build exits 0 |
| Adversarial harness re-run on the committed `bundle_data/` | 16 modes, 3,008 perturbed documents, 20,496 field reads; `ocr_confusions` 0 silent wrong values and 0 invented defects; `unseen_labels` escalates 168; thirteen modes at zero movement |
| Deployed API, 520-email run | 12.7 s warm, 41.6 s cold |
| Deployed `POST /compare` with the model on | `decided_by: llm`, `model_used: true`, 1 call, and it surfaces the planted consignee / notify-party mismatch — **the AI path is live right now** |
| README | four required headings present, 26 relative links resolve, 2 product screenshots, no broken anchors |
| `1.0000` | not re-runnable without the organisers' dataset, but provably unchanged: `git log 4c852a7..HEAD -- backend/sdoc/` is empty |
