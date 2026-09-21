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

## 2. Unblock Vercel — one command, and it may already be fixed by step 1

The deployed dashboard is **11 commits behind**. GitHub shows a red ✗ on recent
commits, and opening it says:

> **Vercel — Deployment was blocked**

The Details link points at `vercel.com/tang-chye-fongs-projects/…`, so the
project is under your account and Vercel's Hobby plan refuses to build commits
pushed by anyone else. Everything on `main` is correct; it simply has not been
built.

**Do step 1 first**, then check whether Vercel picked it up on its own — a
public repository is one of the fixes Vercel itself offers. If the dashboard
still looks old:

```bash
git pull
git commit --allow-empty -m "chore: trigger vercel build"
git push origin main
```

The tip of `main` is then a commit you pushed, which is what Vercel wants.

**Do not use the Vercel dashboard's "Redeploy" button** — it rebuilds the last
commit that *successfully* built, which is the old one, not the new work.

**Check it landed:** open <https://duocode-sentinel.vercel.app/pitch> and press
→ to slide 2, then leave and come back. If it returns to the slide you were on
rather than slide 1, the new build is live.

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
