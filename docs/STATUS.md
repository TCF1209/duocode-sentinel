# Status log

Newest entry at the top. Three lines: **Done / Next / Careful.**

---

## 2026-09-25 — Claude session · reply drafts that say the right thing, and AI wording that cannot touch a fact

Designed with the user before any change (scans get a holding reply; a blank
field is asked about, never confirmed), then reviewed by four independent
lenses with every finding re-verified; the eleven that held are fixed here.
Branch `feat/reply-drafts`. `submission.json` byte-identical
(`1c08cd215b0ba4d3c607a7133212a6f9`).

**Done**
- **Per-reason reply drafts** (`web/lib/reply-draft.ts`). One generic "please
  re-send the affected document(s)" was wrong for 8 of the 20 escalations. Now
  a rule-chosen situation per case: attachments missing, one document missing
  (named by content, not slot), file will not open, scans (no re-send, a person
  reads them), wrong document, fields to confirm (blank *and* mismatched fields
  both listed; an unrecognised label is never put to the customer). No draft is
  offered where "we compared the SI and BL" would be false (every non-comparison
  category, and draft-issue requests). Replies thread under the customer's own
  subject (`CaseResult.subject`, report-only, never scored).
- **AI wording, facts locked** (`backend/api/reply_polish.py`,
  `POST /reply-drafts/polish`). Only the greeting and the closing reach the
  model; what happened, the facts and the request stay locked and are shown so
  in the panel. The rewrite is refused if it adds a number, a name, a claim, a
  request or a second salutation. Measured on gpt-5-mini: 54 of 54 rewrites
  adopted across 9 situations × 3 tones × 2 presses, $0.03 in all.
- `GET /` reports `model_available` and can no longer fail on a bad model
  setting (it is Render's health check). 641 tests; 499 passed / 142 skipped
  on a copy with no `data/`.

**Next**
- Merge after `feat/final-round-differentiators`; both add to the top of this
  file, so keep both entries.

**Careful**
- `reviewReasonClause` in `web/lib/labels.ts` is now unused; left in place
  because the teammate branch edits the lines next to it.
- The panel is keyed on `replyDraftKey(report)`, so a review or re-check closes
  an open draft on purpose: it must not go on describing the old outcome.

---

## 2026-09-24 (evening) — Claude session 8 · the reviewer's round: back to where you were, a Review filter, before-and-after on a correction, a needs-review workspace, and re-sent documents re-checked in place

Six questions from the user after working the real 520-email inbox in the
dashboard, each discussed and designed before anything was changed (the
standing rule: explain → discuss → confirm → then modify), then executed in
the agreed order Q1 → Q2 → Q3 → Q5 → Q4 and verified live in the browser on
`bundle_data` after every step. Session 9 was committing to this same
checkout throughout; file ownership was agreed by message and every `git
add` here names its paths. Follows this file's previous session-8 entry
(the reviewer overlay, `7f0a068`).

**Done**
- **Q1 — Back returns to where the reviewer was, filters included**
  (`ec895bf`, `web/lib/list-memory.ts`, replacing `use-scroll-restoration.ts`).
  The first fix was under-verified and wrong twice over: the router's own
  scroll-to-top overwrote the saved position at leave time, and BackLink
  dropped the query string. Now the list freezes its saved position the
  moment a case link is clicked, remembers its own URL (path + filters),
  and restores only when the case page has flagged a return
  (`sentinel:return-to-run`), never on a fresh visit from Runs. Four paths
  checked live: browser back, "Back to run", back after "View original",
  back with a filter active.
- **Q2 — "confirmed" and "corrected" told apart, and countable**
  (`afd41b4`). A Review filter (pending / confirmed / corrected) on the run
  page beside category and status, a "Reviewed n / N" stat with the
  breakdown on hover, and a "Human review of this run" block on the
  metrics page (the API had returned these counts since the review feature
  shipped; nothing showed them). Filter transitions on 520 `motion.tr` rows
  were 5–8 s with `layout` animation on exit; the table body and mobile
  list now remount on a filter key — 520 → 3 rows in 586 ms desktop / 141
  ms mobile.
- **Q3 — the unchanged version stays visible next to the correction**
  (`91b1afa`). The review panel's reviewed state shows "Sentinel said X /
  Now Y" for a correction, and a "With correction / Sentinel's original"
  toggle in the case header flips the header badge, the banner and every
  field card together without refetching. Nothing is overwritten: the
  system's answer is never replaced, only joined by the person's where they
  differ.
- **Q5 — the NEEDS_REVIEW page as a place to work** (`8f22eca`). It looked
  like a mismatch page in a different colour. Now three sections in the
  order the questions get asked: *why this needs a person* (the reason, and
  each document's state — not attached / could not be read and why / read
  as the wrong kind / fine — with View original), *what to do* (the
  pipeline's own "Suggested action" promoted from a bullet, Retry, the
  reply draft), and *decide it yourself* (the review panel, re-worded for
  this status). Seven identical amber UNCOMPARABLE cards collapse to one
  line with the cards a click away. Seven scenarios checked, including the
  scanned sample on /compare; session 9's scan transcript card slots into
  the per-document card here (`96cf84c`).
- **Q4 — the latest SI/BL dropped back in and checked again, in place**
  (`61aa336` API, `eecb657` dashboard). `POST /cases/{id}/recheck` takes
  the re-sent SI and/or BL as multipart and runs the same comparison
  `/compare` runs, stored against the case: a side not re-sent keeps the
  file the case already has (disk original, or an earlier re-sent copy —
  a second re-check that re-sends only the SI is compared against the BL
  from the first, never the disk BL the desk has moved past); the answer
  it replaces goes into the case's history *with the review that stood
  against it*, and the review is reset (it was about the old documents);
  the email's category, confidence and rationale are carried over — only
  the comparison is new. Decided with the user, each against the
  alternative: list / detail / `/submission` all follow the re-checked
  answer (as `retry` already does); only `BL_COMPARISON` cases can be
  re-checked (409 otherwise); the panel shows on NEEDS_REVIEW and MISMATCH;
  Retry on a re-checked case is refused (409) rather than reinterpreted,
  because it would silently read the disk file back over the re-sent one.
  The attachment route serves the re-sent file from memory and takes
  `?version=N` for the file a superseded version was read from. On the
  page: a "Re-sent documents" panel inside the workspace's *what to do*
  (and under the review panel on a mismatch), the backend's refusals shown
  beside the button, and after a re-check the report leads with
  "Re-checked just now with the re-sent BL — Was: Mismatch on Container
  Count (confirmed by a reviewer) / Now: Matched" and each previous version
  behind a disclosure with "SI at v1 / BL at v1" opening the file that
  version was actually read from. Run rows carry a "re-checked" tag; the
  metrics block gains "Re-checked". Six API tests (`TestRecheck`); suite
  **596 tests, 454 passed, 142 skipped, 0 failed** from `--junitxml`;
  README / `ADVERSARIAL.md` / `/pitch` bumped from 590, and the README's
  route table from 11 to 13 (the attachment route was missing from it
  too). Verified live: `email_043` MISMATCH → Matched on a corrected BL
  with the v1 dialog showing the original `5 x 20'GP`; `email_507` (BL
  never arrived) refused SI-only inline, then resolved on a re-sent BL with
  Retry and the workspace gone; 375 px stacks the pickers with no overflow.
- **Q6 answered, no code:** Sentinel is the documentation desk's automated
  pre-issuance check gate plus the human-review workbench for what it
  cannot decide — not an inbox organiser. Classification exists so the
  comparison requests can be found; the product is the check and the
  evidence.

**Next**
- The final-round deck (session 9's `docs/PITCH_DECK.md` / `/pitch`) and the
  branch push / merge decision for `feat/final-round-differentiators` —
  both the user's call, not started here.
- The Mentor Session reply (25 Sep).
- A light-mode look at the new panel: the pane's colour-scheme emulation did
  not take (the app has its own theme switch), so only dark was seen; the
  panel uses the same semantic tokens as its neighbours and nothing else.

**Careful**
- **Re-sent files live in the API's memory**, like every run: a restart
  loses them and the histories with them. Fine for the demo, and the same
  caveat `store.py` has always carried.
- **`/submission` moves when a case is re-checked** — decided, and the same
  thing `retry` has always done; a judge scoring the API's `/submission`
  after someone re-checked a case with different documents is scoring
  those documents.
- **Retry ≠ re-check.** Retry re-reads the inbox on disk and keeps the
  review; re-check takes uploaded files, keeps history, resets the review.
  Retry is refused (409) on a re-checked case; the UI hides it there.
- **The Browser pane, when hidden, pauses `requestAnimationFrame`**: count-ups
  read 0, Framer transitions never finish, screenshots return stale frames.
  Cost real time twice this session before it was pinned down. Read the
  DOM (`document.visibilityState` first); trust a screenshot only with the
  pane visible.
- This checkout's earlier "45 / 21" was the Windows CRLF artefact session 9
  found and fixed (`c97f192`); the inbox is **46 MISMATCH / 20 NEEDS_REVIEW**
  before any re-check.
- `describeOutcome` is now exported from `review-panel.tsx` and
  `AttachmentAction` lives in `attachment-action.tsx` — both shared with
  `recheck-panel.tsx`; nothing else imports them yet.

---

## 2026-09-24 (afternoon) — Claude session 9 · the final-round rubric read against the repository; a Windows line-ending bug that hid a real defect; the model tier made visible; the pitch's numbers re-measured

Asked to read the organisers' final-round judging rubric (the three PDFs
under `Judging/`), every document and data file this project has, and the
preliminary judges' written feedback, and to say — rigorously, nothing
skipped — where the project stands against each criterion and what to do
about it; then, after a decision round with the user, to close every finding
rather than list it. The mentor session moved to 25 Sep, so the day went on
the fixes. Two other parties (Claude session 8 and the teammate, who pushed
`dbfd528` to `main` mid-afternoon) were committing to this same checkout
throughout; file ownership was negotiated by message, every `git add` here
names its paths, and nothing of anyone else's was staged.

**Done**
- **Found and fixed the reason this checkout has reported 45 MISMATCH /
  21 NEEDS_REVIEW since 21 Sep while the deployed API reports 46 / 20.**
  Not a regression and not the code: no `.gitattributes`, `core.autocrlf`
  on, and `bundle_data/attachments/email_499_BL.pdf` is a PDF-1.3 with no
  NUL byte, so git called it text and the Windows checkout rewrote its 74
  line endings; `startxref` then pointed 74 bytes short, pdfplumber said
  "Unexpected EOF", and a real planted defect (`gross_weight_kg`) came back
  `unreadable` — safe, and wrong, on this platform only. Proven by restoring
  LF in a scratch copy of that one file and re-running: 46 / 20 / 454, 8
  unreadable documents, identical to Render. `git ls-files --eol` showed 34
  committed PDFs exposed to the same rewrite (26 `bundle_data`, 6
  `demo_data`, the two scanned samples under `web/public/samples`); only
  this one broke. `.gitattributes` now declares every attachment format
  binary (`c97f192`), the 34 working files were re-checked-out and read
  `i/lf w/lf`, and `run.py` over `bundle_data` on this machine gives
  **46 / 20 / 454, unreadable 8, decided_by rule 520** — the deployed
  numbers. **Correction to this file's 2026-09-21 entry and to
  `VIDEO_SCRIPT.md`: the "45 MISMATCH · 21 NEEDS_REVIEW" recorded there was
  this artefact, not the pipeline. The README's "46 defects" was always
  right.** Anyone with an older Windows clone: after pulling, delete the 34
  files and `git checkout -- bundle_data demo_data web/public/samples`, or
  re-clone.
- **Measured where the AI actually runs on the real inbox, instead of
  quoting it.** Rule classifier: 0 of 520 emails have `needs_llm`, 0 have
  confidence below the 0.45 floor (lowest is 1.0), so the LLM classifier
  would be asked zero times even with a key. Extractor fallback: 5 readable
  documents have a field no label resolved to, and all 5 are the `BL` side
  of the `wrong_doc_type` pairs (501–505), where `pipeline.py` deliberately
  sets `assisted=False` — zero asks. Scans: exactly 6 attachments are
  `no_text_layer` (512–514, both sides). So "the only live calls in a normal
  run are six scan transcriptions" (`ADVERSARIAL.md` §8) is now a
  measurement on this checkout, not a sentence. Also verified on the
  deployed API with the repo's own public sample pair: `/compare` with the
  model off → `NEEDS_REVIEW`; with it on → `MISMATCH [consignee,
  notify_party]`, `model_used: true` — **Render has a key configured and the
  AI beat works live** (two calls, a fraction of a cent, disclosed to the
  user). Locally there is no `.env`, so the model path cannot run here yet.
- **The six transcriptions are now visible** (`96cf84c`, `49f2f10`). The
  vision transcript never reached `report.json`; `schema._doc` now carries
  `ScanTranscript.as_dict()` on the document, the API passes it through
  unchanged, and `ScanTranscriptCard` renders it inside the needs-review
  workspace's per-document card — model name, legible count, seven values or
  "not legible — blank rather than guessed", and the sentence that nothing
  here entered a comparison. The run page gained **Run with the model
  tier**, off by default, disabled-with-reason when `GET /` reports
  `llm_runs_allowed: false`; `render.yaml` turns that flag on for the
  deployed API with the guards spelled out. Every decision on the inbox is
  still a rule's; a model run there is six vision calls, cached after the
  first. This is the direct answer to the preliminary judge's "using AI
  less than most other teams": the AI is small, specific, and now on screen.
- **The gate no longer says "the documents do not state X" when X is on the
  page under wording it did not recognise** (`b26579d`). Same status and
  review reason; the sentence now distinguishes a blank from an
  unrecognised label and names the document, and the recovery points at the
  label table instead of the sender. Inert on the graded inbox: identical
  metrics, byte-identical `submission.json`, zero cases' notes changed (the
  five `missing_value` cases are genuine blanks), and the adversarial harness
  re-run over `bundle_data` matches `ADVERSARIAL.md` §2 on all sixteen
  modes, every column. Five new tests run the whole `/compare` path on
  inline text.
- **The pitch's numbers re-measured** (`1c691e0`): `/pitch` said "574 tests,
  1 held failing on purpose" and slide 4 described §5.4 — fixed on 24 Sep —
  as the open defect. Now 590 tests · 0 failing, and the card describes
  §5.2 (`email_145`), with the 92% figure for why the obvious guard is worse
  than the gap. README, `ADVERSARIAL.md`'s header and §5.4 tail, and both
  video scripts (banner: no video this round; the three stale figures not to
  say aloud) corrected in `0ceaa15`.
- **`docs/ARCHITECTURE.md` §5 stops drawing a database that does not
  exist.** Postgres marked planned, with what stands in for it and a
  paragraph on how the system scales as built. **Decision, taken by this
  session after the user asked for the lowest-risk call: no database before
  the final.** Render's free disk resets on redeploy, so SQLite would not
  persist there either; a managed Postgres is a new external dependency and
  a credential in the last 36 hours before a live demo that does not need
  persistence (the API re-runs the inbox at boot). The trade is written
  where a judge will read it.
- **README gains an adoption path and the measures a pilot would watch**
  (Impact & Future Potential is a 10-point criterion whose Excellent band
  asks for exactly "a credible adoption path and clear measures of
  success"), with today's measured figures kept apart from targets, and the
  desk counts from the inbox itself (AFEMY 35, AIE 30, AFRT 29, AFPTME 22;
  404 emails carry no desk code).
- **CI** (`f8b2e2f`): `.github/workflows/ci.yml` runs the README's own
  commands — pytest + the demo inbox, then build/tsc/lint — on every push;
  badge in the README. Each step verified locally; the first run on GitHub
  happens when `main` is next pushed.
- Verification, on this checkout after every change: **590 tests, 448
  passed, 142 skipped, 0 failed, 0 xfailed** (`--junitxml`); `run.py` over
  `bundle_data` 46 / 20 / 454; harness sixteen-for-sixteen; `npm run build`,
  `npx tsc --noEmit`, `npm run lint` clean. Seven commits, each naming its
  own paths.

**Later the same afternoon — the model-tier run verified end to end, and
the deck built**
- The user placed a key in a local `.env` (after two wrong locations —
  `backend/tools/`, then the nested stale copy of the repository; the
  loader walks *upward* from `backend/sdoc/llm/`, so only the repository
  root or an ancestor works). A throwaway API on `:8010` with
  `SENTINEL_ALLOW_LLM_RUNS=1` and a production build of the dashboard on
  `:3005` pointed at it; both stopped afterwards, `:8000`/`:3000` untouched.
- Through the real switch on the run page: `llm_enabled: true`, **6 live
  vision calls, all `read_scan`, $0.0119, 18,045 input / 3,681 output
  tokens, 0 refusals, 0 errors**. `email_512`–`514` carry `scan_transcript`
  on both documents (gpt-5-mini, 7/7 fields legible, confidence
  0.85–0.88), the card renders inside `DocumentStatus`, and the case stays
  `NEEDS_REVIEW`. A second run: **6 cached, 0 live, $0.00** — the "a re-run
  answers from the cache" sentence is a measurement. Over the whole inbox
  with the model tier on: 46 / 20 / 454, 6 model calls, `decided_by` rule
  for all 520.
- **`docs/Sentinel-final-pitch.pptx` and `.pdf`**, ten slides (the nine in
  `PITCH_DECK.md` plus a demo divider), generated by
  `scripts/build_pitch_deck.ps1` driving PowerPoint over COM —
  `pptxgenjs` cannot be installed on this machine (TLS interception) and
  LibreOffice is absent, so PowerPoint's own render is the QA. Every slide
  was viewed; three rounds of fixes (the 10-inch preset canvas, the script's
  encoding, an image overlapping its caption). Screenshots under
  `docs/img/pitch/` are from the `:8010` model-tier run, canonical numbers.
  The mismatch view on slide 8 is `docs/img/report.png` (the older case
  page): the field cards animate in on scroll and never appear in a
  headless capture.
- Test count moved to **596** when session 8 landed the recheck endpoint
  (`61aa336`); every copy in the pitch and video documents updated
  (`a09edb6`).

**Evening — the mentor session (20:30), and what it changed**
- Thirty minutes with a mentor; notes in the user's
  `mentor suggestion/1sts Meeting.pdf`, the table of points → changes in
  `docs/PITCH_DAY.md`. The substance: reframe the AI ("reserved for what
  rules can't handle, performs just as well" — never "we use less AI");
  differentiate on the special features at the top-ten stage; put "why we
  built it" and a manual-check benchmark in the intro; show how a person
  uses it, not only the pipeline; design is better than most of the ten
  but font sizes are uniform, capitalisation inconsistent, the Compare
  samples don't look clickable, and mismatches should be visible from the
  list; some judges dislike "Matched/Mismatched"; a judge asked another
  team about KG vs MT.
- Done tonight, mine: status words **No mismatch / Mismatch / Needs
  review** (one map, `lib/labels.ts`); nav **Home · Compare · Runs · How it
  works**; Compare page three-step strip and button-like sample cards;
  deck slides 2/3/5/7 and their notes reworked (why + benchmark, the four
  usage steps, the AI rule, "What makes it different" with the five
  features at thirty seconds); `PITCH_DAY.md`'s mentor table and the unit
  answer (re-checked: `20 MT` → 20,000 kg, `21 MT` → 21,000 kg). tsc, lint,
  build clean; run page and Compare page re-captured.
- Assigned to session 8 by file ownership: mismatch visibility on the run
  table (count on the status cell, mismatches-first), chip capitalisation
  (`all` → `All`), case-page type hierarchy.
- The deck file was open in PowerPoint when the generator ran, so the
  `.pptx`/`.pdf` rebuild is the commit after this one.

**Next**
- **The one path not yet exercised end to end: a model-enabled run.** Needs
  `OPENAI_API_KEY` in a local `.env` (the user places it) and
  `SENTINEL_ALLOW_LLM_RUNS=1` on a local API; then a run over the three scan
  emails should show six calls in `metrics.json`, `scan_transcript` on
  512–514's documents, and the card on their case pages. Also `/compare`
  with the scanned sample and the toggle on.
- `docs/PITCH_DECK.md` (slide-by-slide, rubric-mapped, numbers with their
  source) and `docs/PITCH_DAY.md` (day-of checklist, Q&A bank) — then the
  PPTX from the Markdown.
- **(T)** Push and merge (owner push for Vercel), then on the deployed
  URLs: `GET /` → `llm_runs_allowed: true`; a model-tier run shows six
  calls and the transcript cards; CI green on GitHub. The pitch time limit
  and Q&A format from the Finalist Portal are still unknown to this session.
- Mentor session: 25 Sep.

**Careful**
- **Three parties commit to this checkout.** The protocol that worked
  today: announce the file list by message before touching anything,
  `git add` explicit paths only, and STATUS entries in an agreed order.
  Session 8's running backend still holds a run made with the CRLF-mangled
  PDFs; it will show 45/21 until restarted.
- The test count in README, `ADVERSARIAL.md` and `/pitch` is **590 as of
  this entry**. Any test added after it moves the number; update all three
  in the same commit, not one.
- `SENTINEL_ALLOW_LLM_RUNS=1` on a public URL is bounded by the $2 per-run
  budget, the cache and `SENTINEL_MAX_ACTIVE_RUNS`, and on this inbox costs
  six vision calls per fresh run — but the container's cache directory is
  emptied on every redeploy, so the first model run after each deploy pays
  again. Cents, not dollars; still worth knowing.
- The gate's new wording changes `notes` text only. Nothing in
  `submission.json` moved and the harness proves no decision changed; if
  `review_reason` is ever made to distinguish absent from blank as an enum,
  that *would* be a graded-shape change and needs the scorer.

---

## 2026-09-24 (night, continued a fifth time) — Claude session 8 · the case page now shows the reviewer's correction beside Sentinel's answer, not instead of it

Raised with a screenshot after the previous entry's field-level
correction shipped: having un-checked Port of Discharge as "not actually
wrong" on `email_025`, the Port of Discharge card below still showed a
red MISMATCH badge. The user asked whether the cards would follow a
correction, proposed "keep the original, attach the corrected view
beside it for comparison", and asked for a full discussion of
consequences before any code changed. Discussed first, with the cause
traced from the code, then two AskUserQuestion rounds: (A) the
verdict-level overlay below -- approved; (B) letting a reviewer type the
correct *value* for a field -- declined, on the reasoning that the
review record holds no such thing, nothing consumes one, "the correct
value" in an SI-vs-BL check is almost always the SI side anyway, and a
human-typed value carries no Evidence. Nothing was built before the
answers came back.

**Done**
- **Root cause, stated precisely**: the case detail page painted only
  the system's keys (`report.status`, `report.review_reason`,
  `report.fields[].verdict`) and never read `report.effective`. So one
  screen contradicted itself -- `email_270`'s header said Mismatch, the
  line under it said "corrected to Matched", every field card still said
  MISMATCH -- while the run table, the reply draft, and the pattern
  alerts already used the corrected view. The detail page was the one
  surface in the app that hadn't caught up. The user's proposal is
  literally the design `lib/api.ts` already describes for `effective`
  ("the keys above stay the system's own answer, so a card can show
  both"); it had only been half-applied.
- **`field-comparison-row.tsx`** gained optional `reviewerView`
  ("cleared" | "flagged") and `reviewerNote` props. Sentinel's verdict
  badge is never removed: dimmed, still legible, titled "What Sentinel
  itself said", with the reviewer's badge beside it; the card's tint
  follows whichever judgement currently stands; the SI/BL values and
  evidence are untouched. The reviewer's note is case-level, not
  per-field, so it rides as a hover on every reviewer badge rather than
  being pretended to belong to one -- "why was this cleared when the two
  values visibly differ" is the question a reader has at that spot.
- **`case-report-view.tsx`** computes the per-field view from
  `effective` only for a "correct" decision (a "confirm" leaves
  `effective` identical to system, source "system"; NEEDS_REVIEW as a
  corrected status is "couldn't tell", not a per-field claim, so it
  changes the header only). Header shows the standing status with
  "Sentinel said X" in words only when the two differ; the review-reason
  banner, once resolved, stays but muted -- "Sentinel had flagged: ...
  Resolved by a reviewer — corrected to Matched." `/compare` has no
  `effective` and renders exactly as before.
- One nit caught in verification and fixed before committing: the muted
  banner's "Sentinel had flagged:" had a CSS margin but no actual space
  before the reason text (`innerText` ran them together). Replaced with
  a real space.

**Verification** -- every row of the design table, live, on the real
`bundle_data/` run, read from the DOM rather than eyeballed:
- MISMATCH kept: `email_025` Container Count -- red, single badge.
- MISMATCH cleared: `email_025` POD (its note verbatim in the hover),
  `email_270` POD -- neutral card, dimmed MISMATCH + "Cleared by
  reviewer". Screenshot checked the two badges side by side: not
  crowded, the one visual risk flagged in the discussion.
- MATCH flagged: `email_001` Consignee, corrected OK→MISMATCH via the
  API -- red card, dimmed MATCH + "Flagged by reviewer".
- NEEDS_REVIEW→OK: `email_499` -- header "Matched / Sentinel said Needs
  Review", banner muted with the resolved line, all seven UNCOMPARABLE
  cards untouched (the system never claimed a defect on them; nothing
  to clear, and saying so would be false).
- OK→NEEDS_REVIEW with seven fields: `email_005` -- header only, zero
  reviewer badges, all cards unchanged. (`email_002` and `email_003`
  were tried first and turned out to have no field cards at all -- an
  invoice query and a "please issue the draft BL" request -- so they
  proved the header path but not the card path; `email_005` was found
  by scanning for a 7-field OK comparison case.)
- Confirm only: `email_013` unchanged. Never reviewed: `email_004`
  unchanged. `/compare`: no reviewer badge, no "Sentinel said", cards
  as before.
- `npx tsc --noEmit`, `npm run lint`, `npm run build`: clean, re-run
  after the spacing fix. One code commit (`6ba94fd`), two files, `git
  status` checked before staging.

**Next**
- Same open items as the entries below: slide deck, branch push/merge
  decision, Mentor Session reply.
- Both local servers still running.

**Careful**
- **Option B (typing a correct value) was declined, not forgotten.** If
  it comes back after the pitch, the sane shape is a three-way "SI is
  right / BL is right / neither (enter it)" rather than a free text box,
  and the value must be labelled as a reviewer's assertion, never mixed
  into the system's evidence-bearing fields.
- Test corrections made via the API to exercise the paths above
  (`email_001` → MISMATCH/consignee, `email_499` → OK, `email_002`,
  `email_003`, `email_005` → NEEDS_REVIEW) are in-memory only, gone on
  the next backend restart, same as every prior entry's note on this.

---

## 2026-09-24 (night, continued a fourth time) — Claude session 8 · the review panel explained, then fixed with the user's sign-off, not before

User asked "why does the review panel work this way" in detail (what
Confirm vs Correct actually do, why a MISMATCH can be confirmed, what the
three status choices in Correct it mean, why a NEEDS_REVIEW case asks for
a reason) and explicitly asked for an explanation and a discussion before
any code changed -- "你不要擅自修改" (don't modify on your own). Answered
first from the actual code (review-panel.tsx, store.py's
effective_outcome), not from memory, surfacing two real gaps along the
way rather than only answering what was asked: "Confirm outcome"'s
wording is genuinely ambiguous on a MISMATCH, and "Correct it" had no way
to say *which* field was wrong, which silently produced an empty
defect_fields list server-side whenever a false negative got corrected up
to MISMATCH. Also separately asked to check "run pages look empty for a
few seconds", and floated an AI-driven "learns this shipper's habits"
idea for the correction flow, which got a direct "this isn't buildable
properly right now, here's why, here's a smaller thing that is" answer
rather than a yes. Scope for all four (loading skeleton, copy fix,
field-level correction, a same-run pattern hint instead of the AI
version) was confirmed with the user via two AskUserQuestion rounds
before any file was touched.

**Done**
- **Loading skeleton for the run table.** Root-caused: the stat strip,
  patterns, and table were conditionally *absent* (not loading) while
  data was in flight, and the table's own empty-state row read "No cases
  match this filter" during that same window -- actively misleading, not
  just quiet. New `casesLoaded` flag, kept separate from
  `allCases.length > 0` so a genuinely empty run and a not-yet-loaded one
  read differently. Also explained, not fixed: part of the reported delay
  is Next.js dev-mode's on-demand compile on a route's first hit after a
  server restart (719-843ms, measured from the dev server's own logs) --
  a dev-only cost, gone in a production build.
- **`review-panel.tsx`'s MISMATCH/NEEDS_REVIEW copy rewritten.** "Confirm
  outcome" read as confirming the documents are fine; it confirms
  Sentinel's *call* instead, which on MISMATCH means the opposite. The
  description above the buttons now says so explicitly and points at
  Correct it as the alternative, read in context rather than the button
  label alone.
- **Field-level correction, the actual fix for "I don't know what to
  correct".** Correct it now shows a checkbox per field -- all 7, in
  `FIELD_LABELS`' own order -- but only when the corrected status is
  MISMATCH (the only status `defect_fields` means anything for;
  `store.py`'s `effective_outcome` forces it to `[]` for the other two
  regardless of what's sent). Pre-checked to whatever Sentinel itself
  flagged, so a reviewer un-checks what wasn't actually wrong rather than
  re-finding every defect from a blank slate. This also fixes the silent
  bug the investigation surfaced: the frontend never sent `defect_fields`
  before tonight, so a false-negative correction up to MISMATCH always
  produced an empty list, invisible to "Patterns worth a second look".
- **A same-run pattern hint, instead of the AI-habit-learning idea.**
  Evaluated and turned down as asked, not built: no persistent review
  history exists to learn from (the `Store` resets on every restart) and
  an ungrounded LLM suggestion would cut against this project's own
  evidence-gated thesis two days before the pitch. Shipped the smaller
  thing instead -- a badge next to each field checkbox showing how many
  *other* cases from this case's shipper, in the current run, already
  carry a defect on that field. Reuses data the run already computed; no
  AI, no new storage. `case-detail-page-view.tsx` now also fetches the
  run's case list (best-effort, failure doesn't block the report itself)
  to compute it.

**Verification**
- `npx tsc --noEmit`, `npm run lint`, `npm run build`: clean after both
  commits.
- Live, against a real MISMATCH case (`email_025`, APRIL FAR EAST (M) SDN
  BHD, flagged `container_count` + `port_of_discharge`) in a fresh run
  over the real `bundle_data/`: opened Correct it, confirmed both fields
  pre-checked and every prior-count badge against a hand count of the
  run's other same-shipper cases (Shipper 2, Consignee 2, Notify Party 2,
  Port of Discharge 3, Container Count 4); un-checked Port of Discharge,
  saved with a note, and confirmed via the API that the stored review,
  the effective view, *and* the pattern groupings all updated exactly as
  expected (`port_of_discharge` pattern dropped 4→3, `container_count`
  stayed at 5, `email_025` present in one, not the other). Separately
  corrected a different case fully to OK and confirmed `defect_fields`
  came back empty and it left its pattern entirely.
- Two commits on `feat/final-round-differentiators`, `git status` clean
  before and after each stage.

**Next**
- Same open items as the entries below: slide deck, branch push/merge
  decision, Mentor Session reply.
- Both local servers still running.

**Careful**
- **Every one of the four changes above was confirmed with the user
  first**, including the exact shape of the field-checkbox UI (asked
  specifically, not assumed) -- explicit standing instruction this round
  was "ask immediately on any uncertainty, don't decide alone."
- The in-memory corrections made to verify this
  (`run_000002_1790220546:email_025`, `email_270`) are local test state
  only, gone on the next backend restart, same as every prior session's
  note on this.

---

## 2026-09-24 (night, continued a third time) — Claude session 8 · the attachment link became a dialog; two real bugs it took to get there; scroll restoration; a pattern-emailed badge

Two things raised directly after the entry below shipped: (1) clicking
"View original" then pressing the browser's back button lost the
reviewer's place in the run table -- asked for a full check of every
"back" path in the app, not just a patch for this one; (2) sending a
pattern's summary email left no trace that it had been sent, so a
pattern looked exactly as untouched five minutes after being emailed as
it did before. Both investigated properly before touching code, per this
session's own standing rule against deciding alone on an ambiguous
design tradeoff -- see the two AskUserQuestion calls this session logged
for the actual choices put to the user (dialog + fix scroll app-wide;
local-only "emailed" marker over a backend one) rather than picked here.

**Done**
- **"View original" is now a dialog, not a link.** The investigation
  found the `target="_blank"` version never opened a second tab in this
  app's own preview surface -- confirmed with `tabs_context` before and
  after a click, same tab, origin changed under it -- so the click was a
  full navigation away, and the back button's return landed scrolled to
  the top, not where the reviewer had been. A dialog removes the
  navigation entirely rather than patching around its side effect:
  nothing to come back from. txt/pdf render inline (fetched text in a
  themed `<pre>`, a PDF in an `<iframe>` using `inline`
  Content-Disposition from earlier tonight); docx/xlsx fall back to a
  plain download link, since neither browser-renders regardless.
- **Found and fixed a real, reproducible bug building it, not a
  hypothetical one.** The dialog's fetch failed on click with a
  CORS-shaped `net::ERR_FAILED` while curl and a manually-typed
  `fetch()` to the identical URL never once failed. Root-caused, not
  guessed: forcing one cache-bypassed request immediately fixed every
  later default-mode fetch to that same URL too, which is the signature
  of a stale cached response -- `FileResponse` sets `last-modified`/
  `etag`, enough for a browser to cache and revalidate by default, and
  at some earlier point tonight (before this route existed, or before
  CORS was configured on it) a response without correct CORS headers got
  cached under that URL and kept being served afterward. Fixed with
  `Cache-Control: no-store` on the response in `backend/api/main.py` --
  there was never a reason to want this cached, and `retry_case` can
  change the underlying file, so a cached copy would go stale on its own
  even ignoring the CORS angle. A short retry-with-backoff stays in the
  dialog too, as a separate, real mitigation for ordinary transient
  network blips, not as the fix for this bug.
- **`useScrollRestoration` (`web/lib/use-scroll-restoration.ts`),
  applied to the run table.** The *general* case behind the bug above:
  clicking into any case from partway down the 520-row table and using
  the browser's own back button reset to the top regardless of the
  attachment feature, because this page's case list is fetched
  client-side after mount -- at the moment restoration would normally
  run, the page is still its pre-fetch height. Saves `scrollY`
  continuously (rAF-throttled), restores once the list has actually
  loaded, keyed by path so each run remembers its own position.
- **A pattern's card now shows when it was last emailed.** Raised
  directly: sending "Email this" on a pattern changed nothing anyone
  could see later, so there was no way to tell "I already followed up
  here" without remembering or re-checking. Recorded in `localStorage`
  (`web/lib/pattern-contact.ts`) rather than the backend -- matches this
  system's existing persistence level (the in-memory `Store` already
  resets on every restart) rather than adding new backend state two days
  out. Deliberately kept separate from case-review state: a sent email
  does not mean the shipper fixed anything, so it must not make the
  pattern disappear the way a real correction already does (confirmed
  live tonight, not just from reading the code: correcting one case in a
  real 5-case pattern dropped it to 4 immediately, `has_defect` threading
  through `store.effective_outcome` exactly as designed). Shown on the
  collapsed row, not only inside the opened drafting panel.
- **A second, unrelated bug the new attachment test surfaced**:
  `_write_attachment`'s `Path.write_text()` writes CRLF on Windows while
  the fixture's text constants are plain `\n`, invisible until a test
  did a byte-exact comparison against a served file, which nothing did
  before this route existed. Fixed in the test's assertion, not the
  route -- serving the literal on-disk bytes is correct, the
  fixture/OS mismatch is not.

**Verification**
- `backend/tests`: full suite green after every change (exit 0, zero
  `F`/`E` markers in the run); new assertions lock in the `inline` and
  `no-store` headers and the CRLF-normalised comparison.
- `npx tsc --noEmit`, `npm run lint`, `npm run build`: clean after each
  of the three commits.
- Live, repeatedly, against a fresh run over the real 520-email
  `bundle_data/`: reproduced the CORS/cache failure on a poisoned URL,
  fixed it, then confirmed a completely fresh run (a URL never fetched
  by this browser before) opens the dialog cleanly three separate times
  in a row across fresh page loads; confirmed browser-back scroll
  restoration by scrolling to `scrollY` 3000, clicking into a case, and
  checking the exact value came back after a real back navigation, not
  this page's own in-app link; confirmed the emailed badge appears
  immediately, only on the pattern actually emailed, and survives a
  reload.
- Three commits on `feat/final-round-differentiators`, each scoped to
  one of the three pieces above, `git status` checked clean before and
  after each stage.

**Next**
- Same open items as the entries below: slide deck, branch push/merge
  decision, Mentor Session reply.
- Both local servers left running (backend on `bundle_data/`, frontend
  dev server) so this is ready to look at directly rather than needing a
  cold-start re-verify.

**Careful**
- **The CORS/cache bug above was very likely self-inflicted by this
  session's own extended, iterative testing** -- restarting the backend
  repeatedly across many hours, at points with the route not yet added
  or CORS not yet configured, is what let a bad response get cached in
  the first place. `Cache-Control: no-store` closes the door regardless
  of cause, but it is worth knowing this was probably never reachable by
  an actual end user against a normally-deployed, stably-running
  backend, not a defect this session's users would necessarily have hit.
- **The in-memory run created to verify this
  (`run_000002_1790220546`) is local test state only**, gone on the next
  backend restart, same as every prior session's note on this.

---

## 2026-09-24 (night, continued again) — Claude session 8 · view the original SI/BL, not just its evidence snippet

The previous entry below closed the session out and stopped both local
servers. This is a fresh ask that came in after that close: "when I click
into a case, can the original SI and BL be attached right there so they're
easy to look at?" One feature, built and verified the same way as
everything else tonight — not batched with the entry below because that
entry's own "Careful" section already declared itself finished and
shouldn't be edited after the fact.

**Done**
- **`GET /cases/{case_id}/attachments/{side}`** (`backend/api/main.py`):
  serves the literal file a run read off disk — the same `si_doc`/`bl_doc`
  path the pipeline already resolved, re-contained under `data_root` as a
  cheap correctness habit rather than a real trust boundary (the path
  comes from the inbox JSON, not the request). 404s on an unknown case, an
  unknown side, or a file no longer on disk; only ever wired up for a run
  (`caseId` is `<run_id>:<email_id>`) — `/compare` holds its upload in
  memory and persists nothing, so there is nothing this route could point
  at there, and no link renders on that page (checked live, not just by
  reading the prop-drilling).
- **Served `inline`, not `FileResponse`'s own `attachment` default.**
  Caught before it shipped, not after: the framework default forces a
  save-as dialog, which is the opposite of "easy to look at." Checked what
  that actually costs against `docs/DATA_NOTES.md`'s own attachment count
  — 192 `.txt` + 28 `.pdf` of 250 total render directly in a browser tab
  under `inline`; the remaining `.xlsx`/`.docx` have no in-browser renderer
  either way and download regardless of the header, so `inline` has no
  downside for those. Locked in with a header assertion in the new test,
  not just eyeballed once.
- **Frontend**: `attachmentUrl()` (`lib/api.ts`), a "View original" link
  next to the existing "SI: {path}…" / "BL: {path}…" line
  (`case-report-view.tsx`, gated on a new optional `caseId` prop),
  wired from `case-detail-page-view.tsx` as `` `${runId}:${emailId}` ``.
- **A real, pre-existing test bug this surfaced, not introduced by it**:
  `_write_attachment`'s `Path.write_text()` writes CRLF on Windows while
  the fixture's own text constants are plain `\n` — invisible until a test
  did a byte-exact comparison against the served file, which nothing did
  before this route existed. Fixed in the test's assertion
  (`.replace("\r\n", "\n")`), not the route: the route serving the literal
  on-disk bytes is correct behaviour, the fixture/OS mismatch is not.

**Verification**
- `backend/tests`: full suite re-run after the fix, zero failures (exit
  0; every progress character is `.`/`s`, none `F`/`E` — the run's own
  final summary line did not print to this shell for reasons unrelated to
  the tests themselves, so pass/fail was confirmed by exit code and the
  absence of any failure marker instead of by that line). New test covers
  byte-for-byte content, the `inline` header, and all three 404 paths.
- `npx tsc --noEmit`, `npm run lint`, `npm run build`: all clean.
- Live, against real data, not the synthetic fixture: restarted the
  backend (it had been stopped per the prior entry) with
  `SENTINEL_DATA_ROOT=bundle_data`, ran a fresh 520-email pass, opened
  `email_004` (a real MISMATCH) in the browser, clicked "View original,"
  and watched the actual shipping-instruction text — including fields no
  other part of the UI shows, like vessel/voyage/HS code — render in the
  tab with no download prompt. Confirmed `/compare` shows no such link
  after running a sample comparison there.
- Committed (`2332f96`) on `feat/final-round-differentiators`, five files,
  nothing untracked swept in alongside it (`git status` checked before and
  after staging).

**Next**
- Servers left running this time (backend on the real `bundle_data/`,
  frontend dev server) since the user may want to look at this directly
  rather than re-verify it themselves from a cold start.
- Same open items as the entry below: slide deck, branch push/merge
  decision, Mentor Session reply — all still untouched.

**Careful**
- The in-memory run created to verify this (`run_000002_1790218514`) is
  local test state only, gone on the next backend restart, same as every
  prior session's note on this.

---

## 2026-09-24 (night) — Claude session 8, continued · overnight autonomous pass: real-time sync, mailto, discoverability, a design critique acted on

Explicitly asked to keep working unattended overnight and have it "done to
the best it can be" by morning. Everything below is closed-loop the same
way the rest of this session has been -- built, verified, committed,
written up here -- but with nobody available to redirect a wrong call
until this is read, so the bar for "verified before committing to it" is
higher here than earlier the same day, not lower.

**Done**
- **Investigated "can Sentinel email the counterparty for real" properly
  instead of just saying no.** Found that `EmailRecord.sender` (the
  inbox record's own "from" address) was parsed and then discarded before
  reaching the API -- nothing under `backend/api/` or the dashboard could
  see who actually sent an email. Threaded it through
  (`backend/sdoc/schema.py`, `pipeline.py`, `backend/api/main.py`) as a
  plain read-only field; never read by `backend/sdoc/` itself, not part
  of `to_submission()`'s shape. **Did not build real sending** — no email
  infrastructure exists in this project, and standing up SMTP/an email
  API plus credentials with nobody available overnight to configure or
  approve them was the wrong tradeoff two days out. Built a `mailto:`
  link instead (`lib/reply-draft.ts`'s `mailtoHref`, wired into
  `reply-draft-panel.tsx`): opens the operator's own mail client with
  To/Subject/Body pre-filled, editable, and the actual send click still
  happens in their own already-authenticated app — Sentinel never
  transmits anything itself, same rule the review panel already holds
  to. `buildReplyDraft` now returns `{subject, body}` instead of one
  flat string so this never has to re-parse a "Subject: ..." line back
  out of the textarea.
- **Moved the reply-draft button next to Review, not after every field.**
  User's own words: "if I hadn't discussed this with you today, I really
  wouldn't have noticed this feature existed." It sat after every field
  comparison, a long scroll on a real multi-field mismatch. Now sits
  right below Confirm outcome / Correct it, same reasoning the review
  panel's own placement already used.
- **Fixed a typography complaint, diagnosed rather than guessed at.**
  "The text all feels chaotic, not clearly expressed" turned out to have
  a specific, checkable cause: `field-comparison-row.tsx` set both the
  extracted value and its own supporting evidence quote in the same
  `font-mono`, and the source data is almost always an already-upper-case
  name or address — monospace on a long upper-case run is a genuinely
  hard combination to scan, and with the value and its proof in identical
  type there was no visual way to tell them apart. Fixed typographically
  only: the text and its case are untouched (the case is part of what
  "exact evidence" means here), the value moved to a plain proportional
  font, and the snippet gained a left border instead of relying on
  typeface to read as a quote. Checked across MATCH and MISMATCH cards
  and numeric fields, not just the one card that prompted it.
- **Real-time sync, the explicit ask, and two real bugs it took to get
  there safely.** The run page used to stop polling entirely once a run
  was "done," on the (previously correct, now stale) premise that a done
  run's cases never change — a review can happen well after. Re-enabled
  polling unconditionally (2s running / 20s done), but only after fixing
  *why* it was disabled: added a same-data no-op guard (compare the
  fetch against current state, hand back the same reference if unchanged)
  so a 20s "nothing happened" tick no longer re-renders and re-animates
  all 520 rows. Testing that surfaced two more bugs, not introduced by
  it: (1) the case list was always fetched pre-filtered, so the pattern
  alerts and this session's own new stat strip silently meant "of the
  filtered subset" the instant a filter was active — refactored to fetch
  the whole run once (`allCases`) and filter client-side
  (`visibleCases`) for the visible table/cards only; (2) `run.metrics.by_status`
  is a snapshot `finish_run` writes once and never recomputes — confirmed
  by correcting a real case and watching it not move — so the stat strip
  this session added earlier was already stale by the same bug. Switched
  it to count `allCases` (which already carries effective status)
  instead. Verified passively, not by re-triggering it manually:
  corrected a case via the API with the browser left alone, waited past
  one 20s tick untouched, watched the stat strip move on its own.
- **Pattern-level batch draft, the other half of the mailto: ask.** "N
  cases from this shipper, one summary email instead of N separate ones."
  `buildPatternDraft()` (`lib/reply-draft.ts`) reuses the same
  `{subject, body}` shape `buildReplyDraft` already returns; the "To"
  line collects every *distinct* sender across the cases in that pattern
  group, not one picked arbitrarily. Verified this was not a
  hypothetical before trusting it: a real 6-case pattern in
  `bundle_data/` (APRIL FINE PAPER TRADING (MIDDLE EAST) FZE, Container
  Count) turned up 6 different individual senders at the same company,
  confirming live the same "a real thread can carry more than one
  signature" reasoning the per-case mailto: work was already built on.
  Kept as its own small component rather than generalising
  `ReplyDraftPanel` — that panel was already fully verified earlier the
  same night, and reopening it to save a dozen duplicated form lines
  was the wrong trade under the same time pressure.
- All of the above: build, `tsc --noEmit`, `lint` clean after every
  commit; the sender-threading backend change additionally re-verified
  against `bundle_data/` the same way as the day's earlier backend
  changes (full suite, adversarial harness byte-identical).

**Next**
- **The critical design pass stopped deliberately, not because time ran
  out.** Looked fresh at the home page and `/compare` after the pattern-
  draft work; found nothing else worth the same bar of confidence the
  items above were held to. Padding this list with marginal nitpicks to
  look busy was exactly the failure mode worth naming and not doing —
  see this file's own long-standing rule about not adding complexity
  beyond what a change actually needs. `/compare`'s upload flow itself
  is still only verified through the API directly (`docs/STATUS.md`
  session 5 already flagged this once): this session's browser tool has
  no way to drive a native OS file picker, so the actual click-to-upload
  interaction remains the one thing about that page nobody has watched
  happen in a live browser.
- Slide deck, the branch push/merge decision and the Mentor Session
  email reply are all still exactly where the last entry left them —
  human tasks, untouched by anything overnight.

**Careful**
- **Nobody was available to redirect a wrong call while this ran.** Every
  design opinion acted on tonight (typography, button placement, the
  mailto: vs. real-send judgment call) is defensible and was checked
  before committing to it, but "defensible" is not the same bar as
  "the user explicitly signed off on this exact choice" — worth a second
  look in the morning specifically because of *when* it was made, not
  because anything specific is suspected wrong.
- **Two scratch corrections were made on the live local test run**
  (`run_000002_1790189003`, `email_004` and `email_013`, both flipped to
  `OK`) purely to verify the sync/staleness fixes end to end. In-memory
  only — gone on the next backend restart, never touched real data or
  anything committed.
- **Session ended clean**: full backend suite re-run one more time after
  every change tonight — 440 passed, 0 failed, 0 xfailed, same as the
  last checkpoint. Frontend `build` + `tsc --noEmit` + `lint` re-run
  together on the accumulated state, not just per-commit — all clean.
  Both local servers stopped (not left running this time — there is no
  next step queued that needs them up). To look at any of this live:
  `SENTINEL_DATA_ROOT=bundle_data .venv/Scripts/python.exe -m uvicorn
  backend.api.main:app --port 8000`, then `npm --prefix web run dev`,
  then `POST /runs` to get a fresh run (the store is in-memory and empty
  on every restart, same as every prior session's note on this).
- **22 commits total on `feat/final-round-differentiators` for the whole
  2026-09-24 session**, counted with `git log main..HEAD --oneline` just
  now rather than estimated — that command is the complete, literal list
  if a summary here or in chat ever disagrees with the branch.

---

## 2026-09-24 — Claude session 8 · final round: three differentiators shipped, one real bug found along the way

**Done**
- **Team advanced to the Top 10 finalists.** New deadline **26 Sep 2026,
  00:05**, submitted through the hackathon's own website (not the old Google
  Form). Requirements changed: (1) repository, accessible — already true;
  (2) **presentation slides — the one real gap**, last round's "README
  counts as the slide deck" answer does not apply to a live Final Pitch Day;
  (3) no video this round. Final Pitch Day itself is the same morning,
  10:30 AM, Monash University Malaysia — live, in person, with Q&A.
- **Evaluated connecting Agenticcs (a separate DuoCode product) into
  Sentinel, verified against its actual code, and did not.** Six reasons,
  written up in memory rather than here since it is a decision about scope,
  not a change to this repo: it is a whole multi-service platform (Convex,
  Stripe, OpenAI File Search, GCP), hard-depends on network/API keys
  (`CLAUDE.md` rule 5 exists specifically against this), solves a
  differently-shaped problem (RAG question-answering vs. structured
  field comparison), and adds a new external-dependency failure surface
  two days before a live pitch for no rubric points. What shipped instead:
  a one-line credit + link in this README's byline (real visibility, the
  team's actual goal, zero engineering risk) — no code integration.
- **Tested against a real carrier's own document, not just our generator.**
  CMA CGM's public SI template — see
  [`docs/EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) for the full
  write-up. Found and fixed a real bug: `Shipper/Forwarders Reference` (a
  tracking-number label) was read into the `shipper` field because it
  contains the word "Shipper," producing a false `MISMATCH` — same trap
  `Booking Reference` already guarded against, one field over. Fixed in
  `labels.py`'s `IGNORE_LABELS`, pinned by a new test. Verified two ways:
  the added strings appear nowhere in `bundle_data/`, and a full
  `adversarial.py` re-run against it — 16 modes, 94 pairs, 20,496 reads —
  matches `docs/ADVERSARIAL.md` exactly, zero movement. Left open and
  disclosed, not rushed: the container table's six real columns don't fit
  `readers/office.py`'s two-column label:value assumption, so
  `container_count`/`gross_weight_kg` came back `missing` rather than
  guessed — safe, but a real reader-architecture gap.
- **Built two items straight from this file's own "Future roadmap" list**,
  both requested in substance by the organisers' final-round prompt to show
  additional value: throughput/cost projection on the metrics page
  (`web/components/metrics-page-view.tsx` — processing time scales this
  run's own measured ms/email, cost shows "today's mix" next to a worst-case
  ceiling at `docs/ADVERSARIAL.md` §8's $0.0013/document, never a single
  invented blended number); and batch pattern alerts on the run page
  (`web/components/pattern-alerts.tsx` — groups `MISMATCH` cases by
  shipper + field, 2+ only, largest first). The second needed one
  deliberate, scoped exception to "don't touch the backend": `shipper` is
  now a field on the case-list API response, projected from a comparison
  `pipeline.py` already computes — no new extraction, nothing in
  `backend/sdoc/` touched. Verified against the real 520-email
  `bundle_data/`, not a demo fixture: 21 real patterns exist, largest is
  seven cases on one shipper's gross weight, independently cross-checked
  in a one-off script before trusting the UI, then confirmed the UI matches
  it exactly in a live browser, including the expand interaction and a
  followed link into the real case detail underneath it.
- **Found and fixed a real bug in the reply-draft feature while extending
  it**, not the extension itself: `buildReplyDraft` read `report.status` /
  `report.defect_fields` directly, which `lib/api.ts`'s own comment says
  deliberately stay the system's original answer everywhere on this page
  so a card can show both. Every other use of that has a human on screen
  with the full context; the drafted reply is the one artifact that leaves
  it. A reviewer correcting a false mismatch, then drafting a reply, would
  have sent the counterparty an email about a discrepancy a human had just
  said does not exist. Now reads `report.effective` when present, falls
  back to the system's own answer when absent (always true on `/compare`,
  where nothing is stored and nothing can be reviewed). Verified live, not
  just read: drafted a real mismatch, corrected it to "Matched" through the
  actual review UI, drafted again — the draft changed from listing two
  false fields to "No mismatch was found."
- All of the above is on branch `feat/final-round-differentiators`,
  committed, **not pushed**. Full backend suite 432 passed / 0 failed after
  every backend-touching commit; frontend `build` + `tsc --noEmit` + `lint`
  clean after every frontend-touching commit.

**Next**
- **The slide deck is the only mandatory piece still missing**, and unlike
  last round, the README cannot stand in for it — Final Pitch Day is live
  and in person. Nothing in this session's work is blocking it; if
  anything, `docs/EXTERNAL_VALIDATION.md` and this entry are exactly the
  raw material a deck needs.
- **(T) Decide whether/when to push and merge this branch.** Same
  Vercel constraint as last round applies again if it matters before the
  deadline: the Hobby plan only builds a commit pushed by the project
  owner, so whoever merges should be the one who also triggers the deploy.
- **(T) Reply to the Mentor Session email** — a human task, not a coding
  one, mentioned here only so it doesn't get lost.
- The container-table reader gap (`docs/EXTERNAL_VALIDATION.md`) is a real,
  disclosed limitation, not a to-do for the next 24 hours — generalising a
  reader used everywhere `.docx` is read is not a change to rush two days
  before a live pitch.

**Later the same day — the two disclosed gaps above, closed, plus what
closing them cost in bookkeeping**

Asked explicitly to close every finding from the external-validation pass
rather than leave both disclosed. Both turned out safe to fix once actually
scoped:

- **`readers/office.py`** now recognises a container-manifest table (3+
  columns, header row names a container column) and derives
  `container_count` from the row count, fed into `extract/fields.py`'s
  existing scoring as an ordinary chunk — no change to that module at all.
  `gross_weight_kg` from such a table is still left open on purpose: summing
  per-container weights into a shipment total is a domain judgement call,
  not a parsing gap. 7 new tests
  (`test_office_container_manifest.py`), and the original CMA CGM document
  re-run to confirm `container_count` now reads `1` and `MATCH`s the BL.
- **`compare._extend`** now anchors on `evidence.locator` when it names a
  line, instead of `text.find`'s first occurrence — the last known,
  deliberately-pinned gap, `docs/ADVERSARIAL.md` §5.4. The strict `xfail`
  pinning it was run first with the marker still in place to see the XPASS
  happen, then removed per the test's own documented instruction.
- **Both are provably inert on the graded data**, same standard as the
  `labels.py` fix earlier the same day: `adversarial.py` against
  `bundle_data/` reports all 16 modes byte-identical to the run before each
  fix, because neither triggering shape occurs in the real 520-email set.
- **Found something to fix in the bookkeeping, not the pipeline**: these two
  fixes, on top of the `labels.py` one, meant three commits had now touched
  `backend/sdoc/` since `4c852a7` — which made the README's own literal
  claim, "no commit since has touched `backend/sdoc/`", false, with a `git
  log` command a judge could run and get a non-empty result from. Not a
  claim the score moved; a specific, checkable sentence that stopped being
  checkable-true. Rewrote it as a table (commit, why the score can't have
  moved) and fixed every other place quoting the now-stale `574`/`1 xfail`
  figures or the §5.4 framing — including a mix-up predating this session,
  not introduced by it: the real `1 masked discrepancy` `bundle_data/` has
  always belonged to §5.2 (`email_145`, unfixable by the repair *by
  construction*, still open), not §5.4, which fired on zero real documents
  both before today's fix and after it.
- Final count: **440 passed, 0 failed, 0 xfailed** locally (582 total,
  reasoned from `574 + 8 new`, arithmetic explained in the README rather
  than asserted as a fresh clone's own output — this checkout is not a
  fresh clone and its skip count does not match the documented 142 for
  reasons that predate this session).

**Careful**
- **`data/_grader/` is not on this machine**, so the literal `1.0000` score
  could not be re-verified here for any of today's four `backend/sdoc/`
  commits — what *was* verified, on the real committed `bundle_data/`, is
  that the adversarial harness's full set of safety numbers (false
  discrepancies, silent wrong values, masked discrepancies) are
  byte-for-byte identical before and after every one of them. Different
  evidence than re-running the scorer, not weaker evidence for what changed.
- **The `shipper` API field is additive and read-only**, but it is still a
  boundary crossed on purpose after a specific ask to keep it in check —
  worth another look before it is taken for granted on the next feature
  that wants "just one more field."
- **The README's fresh-clone test counts (440 passed / 142 skipped) are
  computed, not re-observed** — re-run `pytest backend/tests` on an actual
  fresh clone before quoting that split as measured; the pass count and
  zero `xfailed` are what every commit message above verified directly, the
  142 is carried over from before `4c852a7`.
- Two local servers (`uvicorn` on `:8000` against `bundle_data/`, the
  dashboard on `:3000`) were left running through this whole session for
  live verification. Stop whatever owns those ports before starting your
  own, same as every prior session's note on this.

---

## 2026-09-21 — Claude session 7 · Phase 4, and the numbers re-measured

**Done**
- **Read the rules PDF against what we have.** The one finding that changes
  work: the rules list a **GitHub README** as an acceptable Slide Deck /
  Documentation link, and ours already carries all four required sections
  (Technical Architecture, Implementation Details, Challenges Faced, Future
  Roadmap). Phase 4's deck is therefore answered without building a deck, which
  leaves the evening for the video — the only component with a time penalty.
- **`docs/SUBMISSION.md`** — every Google Form field, written out. Project
  description in a full and a short version, all four links, a pre-submit
  checklist, and a table mapping each mandatory rule to where it is met.
- **`docs/VIDEO_SCRIPT.md`** — the ≤5:00 script with per-section timings
  (target 4:30, thirty seconds of margin), the pre-record checklist, a table
  of every spoken number with its source, and a "do not say" list.
- **Re-measured every number the video speaks**, on this commit against the
  committed 520-email `bundle_data/`, rather than trusting an older doc: 520
  emails · 220/125/75/60/40 by category · 45 MISMATCH · 21 NEEDS_REVIEW over
  4 reasons · `decided_by_rule` 520, `llm_calls` 0 · 2.37 ms/email, 1.23 s
  total · **124 document pairs** actually compared, counted from `report.json`,
  which is the pitch's own figure and had never been checked · 574 tests, 0
  failures via `--junitxml`. All consistent with `SCORING.md` and
  `ADVERSARIAL.md` §8.
- **Shipped the three uncommitted demo-recording changes** that were sitting in
  the working tree (progress panel holds the final tally for 2.5 s; the pitch
  remembers its slide across the trip to `/runs` and back), and fixed a real
  lint error they revealed: `ModelTier` was declared *inside* `CaseReportView`'s
  body, so it was a new component type every render. Lint and `tsc --noEmit`
  are both clean again.

**Next**
- **Record the video.** It is the only mandatory component still missing, and
  the roadmap's own gate on everything else.
- The two unchecked **(T)** items that are still a human's job and always were:
  spot-check 10 escalated cases by hand (Phase 2), and confirm the public URL
  from a phone on mobile data (Phase 3c).

**Careful**
- **The inbox run will never show an `llm` badge, and that is correct.**
  `decided_by` is `rule` for all 520 and the deployed API sets
  `llm_runs_allowed: false` as a cost guard on whole-inbox runs. The model is
  demonstrable on `/compare` with the toggle on — `POST /compare` is
  deliberately not gated — and nowhere else. A video that promises "watch the
  AI work" over `/runs` cannot deliver it.
- **`data/` is not on this machine** — no `data/bundle`, no `data/_grader`. So
  the 1.0000 score could **not** be re-run here; it is quoted from
  `SCORING.md`, unchanged, and 142 of the 574 tests skip for the same reason.
  Everything else above was measured fresh.
- Slide 4 says 520 emails in **13 seconds**; a laptop does it in 1.2. Both are
  true and the slide is explicit that 13 is the free-tier container. Say 13 in
  the video, because 13 is what the screen will show.

---

## 2026-09-21 — Claude session 6 · the evidence gate measured, and the OCR row closed

**Done**
- **Ablated the evidence gate** instead of continuing to argue for it
  (`scripts/ablate_gate.py`, `ADVERSARIAL.md` §6). Layered arms, one veto at a
  time, scored by the organisers' own scorer. The result is not flattering and
  is written up as it came out: `final_score` cannot move, because Stage 3
  excludes gold `NEEDS_REVIEW` emails and end-to-end counts only gold defect
  emails — so a veto whose job is to stop us auto-deciding an uncertain case
  has nowhere to appear in the headline number. The effect lands on escalation
  recall (1.000 → 0.750 without the blank veto), which the organisers report
  and deliberately leave unweighted. **The untraceable veto — the distinctive
  half — fires on zero of 520 emails.** On this inbox it is untested, not
  proven.
- **Closed the worst row in the adversarial suite** (`ADVERSARIAL.md` §4.4),
  which turned out to be two different defects wearing one name.
  - The numeric half was a *parsing* bug and worse than the row implied:
    `normalize._NUM_RE` is a prefix match, so `216,9S0 KG` parsed as **2169
    kg** and `13B MT` as 13,000 instead of 138,000 — confident wrong numbers on
    a field whose planted defects are ±500 kg, and nothing downstream could
    tell a truncated number from a short one. `normalize.digits_contaminated`
    now refuses a number whose own edges touch a digit lookalike.
  - The text half needed a judgement call: `compare.ocr_confusable` sends two
    equal-length values that differ only where both characters sit in one OCR
    confusion class to a human rather than reporting a discrepancy.
  - Measured on the dev bundle: silent wrong values **982 → 0**, invented
    defects **151 → 0**, masked defects 0 → 0, readable container counts
    unchanged at 72. Held-out seed agrees (949 → 0, 150 → 0). All four
    datasets still score **1.0000** with escalation precision and recall both
    1.000, and the veto fires on none of the 520 graded emails.
- Narrowed the digit guard after measuring it, not before. Checking the whole
  value instead of the parsed number's edges cost 72 readable container counts
  and bought no accuracy — in `6 x 4O'HC` the damage is in the box size.
- **Falsified the veto before shipping it** rather than reasoning about it:
  across the entity pools of all four datasets, none of 804 pairs of genuinely
  different parties and ports is confusable, and none is even within two
  characters at equal length. `backend/tests/test_ocr_confusion.py` (41 tests)
  re-runs that sweep so a future pool containing such a pair fails the build.
  Suite is 573 passing.
- **Fixed a trap in `scripts/evaluate.py` that nearly cost this change.** It
  hardcoded `data/_grader/ground_truth.json` while `--data` accepted any
  dataset, so re-scoring the three held-out draws returned 0.0998 / 0.0672 /
  0.0844 — a catastrophic-looking regression that was entirely the wrong
  answer key. It now prefers the dataset's own key and prints which one it
  used. The held-out re-run in `SCORING.md` §4.1 is exactly the step where a
  good change is most likely to be rolled back for the wrong reason.

**Next**
- The (T) items are the whole remaining critical path: slide deck, ≤5-min demo
  video, project description, Google Form by 22 Sep 12:00. Nothing in the code
  is blocking them.
- `ROADMAP.md` 3d's open decision (curated `demo_data/` vs the whole
  participant bundle) is still open and still (T).

**Careful**
- **The amendment in `CLAUDE.md` rule 3 has exactly one justification and it
  must survive any future edit: `ocr_confusable` never produces `MATCH`.** It
  escalates. The moment someone widens it into something distance-based, or
  lets it return a match on a "close enough" pair, it becomes the similarity
  threshold `DECISIONS.md` §D2 bans, and it will swallow a planted defect. The
  trap tests in `test_ocr_confusion.py` are there to fail first.
- The gate ablation says the gate costs nothing *on this inbox*. It does not
  say the gate earns the score, and §6 is worded to stop anyone quoting it
  that way. The untraceable veto's value is argued in §1, on documents this
  generator cannot produce — not measured on the graded set.
- `ADVERSARIAL.md`'s headline pass rate **did not move** (88.4%) and will not:
  the reads still change because the document genuinely changed. Only the
  consequence columns moved. Quote both or neither.

---

## 2026-09-19 — Claude session 5 · Phase 3b (`web/` dashboard) built and verified

**Done**
- Scaffolded `web/` (Next.js 16.3.5 App Router, Turbopack, shadcn/ui, Recharts)
  and built all five items in this file's own 3b checklist: run list + create,
  inbox triage, the discrepancy report (`components/case-report-view.tsx` —
  "the screen the whole project exists to produce"), review confirm/correct,
  a client-side generated reply draft, and a metrics page with three charts.
  `POST /compare` (3d) has its own page too (`/compare`). `docs/ROADMAP.md`
  3b is ticked.
- Dropped `@tanstack/react-table` before writing a single row with it: the
  installed version is 9.2.4, a ground-up API rewrite from the `useReactTable`
  API this codebase's own training-era knowledge expected (confirmed by
  `node -e "require('@tanstack/react-table')"` listing its real exports — no
  `useReactTable`, no `getCoreRowModel`). A five-column table with manual
  filters does not need it; uninstalled rather than fighting an unfamiliar v9
  surface under a 3-day clock.
- Checked Next's own bundled docs before writing App Router code — `next dev`
  auto-generates a `web/AGENTS.md` warning that this Next version "has
  breaking changes" from training data and pointing at
  `node_modules/next/dist/docs/`. It was right to check: Next 16 ships a new
  Cache Components model (`cacheComponents` in `next.config.ts`, `'use cache'`,
  `<Suspense>`-gated runtime APIs). It is **off by default** and this
  dashboard never turns it on — every page is a plain Client Component
  fetching the FastAPI backend directly, which sidesteps that whole surface
  on purpose; if a future session enables `cacheComponents`, re-read that doc
  first, this dashboard was not written against it.
- Added two small, honest gaps found while building, not before:
  `GET /runs` (list all runs) — not in `backend/api/`'s original endpoint
  table, needed for the dashboard's own run list, `Store.list_runs` already
  existed for `latest_done_run` to build on; and `category_confidence` on
  `GET /runs/{id}/cases` — this file's own 3b line says the inbox triage needs
  a confidence column, and the API never exposed it until now. Both covered
  by `backend/tests/test_api.py` (still synthetic fixtures, still not
  `data/bundle`).
- **Found and fixed a real, non-obvious build bug, not a preference.**
  Utility classes written directly inside a Next.js dynamic-route folder
  (`app/runs/[runId]/...`) silently do not compile under this project's
  Tailwind v4 + Turbopack setup. Found by noticing a 4-column stat grid
  rendered as one column, then proven by fetching the actual served CSS and
  diffing it byte-for-byte (`md5sum`): `sm:grid-cols-2` (used in
  `components/case-report-view.tsx`, outside any bracket folder) compiled;
  `grid-cols-4` (used only in the metrics page, inside `[runId]/`) never did,
  with or without an explicit `@source` pointed at that exact path, before or
  after a full `rm -rf .next` restart. **Fix:** every `page.tsx` under a
  dynamic route segment is now a thin shell that only unwraps `params` (React
  `use()`, per Next's own file-conventions doc — a Client Component page
  cannot be `async`); all real markup moved to `components/*-page-view.tsx`,
  which compiles correctly. Keep this pattern for any new page added under a
  `[param]` segment, or the same silent failure comes back.
- **Correction, same day, from `a01dd91` (main): the diagnosis two bullets up
  was wrong.** The real cause was an unanchored `runs/` line in the
  repo-root `.gitignore` matching `web/app/runs/` at any depth — the same
  bug that had also swallowed three page files whole (`git status` never
  mentioned them, `git add -A` staged nothing under that path, no error).
  Tailwind was never broken; it correctly skips git-ignored files, and those
  files were git-ignored. `.gitignore` is now anchored (`/data/`, `/runs/`,
  `/.cache/`). The `components/*-page-view.tsx` split is kept as a plain
  layout choice, not as a fix for anything — the false claim is removed from
  `globals.css`'s comment. Left visible here rather than silently corrected,
  same reason this file keeps its other wrong-turn rows.
- **A second, sharper bug found while fixing the first one.** Documenting the
  fix above inside a CSS comment in `globals.css` — the comment's prose
  literally contained the word `@source` and a `[` character — crashed the
  Turbopack/PostCSS build outright: `CssSyntaxError: ... Unknown word [`, from
  a line that was supposed to be inside `/* ... */`. Whatever preprocesses
  `@source` in this pipeline is not respecting comment boundaries reliably.
  Reworded the comment in plain prose with no `@`-directive-looking text and
  no literal brackets; confirmed clean by watching the same error disappear
  from the dev server log on restart.
- Verified, not asserted: `npx tsc --noEmit` clean, `npm run lint` clean,
  backend suite unchanged at **391 passed / 141 skipped / 1 xfailed** after
  all of this (nothing under `backend/sdoc/` or `backend/api/`'s existing
  routes changed behaviour). Then a full manual click-through in a real
  running browser (not just curl) against a synthetic 3-email demo inbox
  (`data/manual_check_bundle/` — scratch data for this session, **not** the
  organisers' bundle and not a `demo_data/` proposal, see Careful below):
  created a run, watched inbox triage show the right category/confidence
  (100%)/status/`rule` badge for all three emails, opened all three case
  outcomes (OK all-MATCH, MISMATCH on `consignee` with real evidence
  snippets, NEEDS_REVIEW/`missing_attachment` with a recovery suggestion),
  confirmed a review and watched it persist across reload, generated a reply
  draft and read its text, and watched all three metrics charts render the
  correct real numbers (3/3/3 category count, a 1/1/1 outcome pie, 1
  `missing_attachment` bar).

**Next**
- **3c, deploy, is still zero lines** and is explicitly not something this
  session did unattended — it needs Render/Vercel accounts and a decision
  the team owns (which service account, what the public URL becomes), and it
  touches shared/external state. `docs/ROADMAP.md` still says do this on the
  20th.
- The `/compare` page's actual file-picker interaction was not click-tested
  in a live browser — this session's browser tool has no scriptable way to
  drive a native OS file picker. The endpoint underneath it is proven
  (3 pytest cases plus an earlier real `curl -F` multipart upload against a
  running server), and the page typechecks and lints clean, but a human
  should click through the literal upload flow once before demo day.
- Retry-a-single-case (docs/ROADMAP.md 3a, still `[~]`) is still not built.
- The metrics page deliberately does not show a confusion matrix or accuracy
  score — `docs/SCORING.md` and `CLAUDE.md` rule 1 both say nothing under
  `backend/` may read `data/_grader/ground_truth.json`, and the dashboard
  only calls `backend/api/`, which only ever sees what `backend/sdoc/` sees.
  If the team wants that number on-screen for the demo, it has to come from
  a human pasting the `score_cli.py` output in, not from a new code path.

**Careful**
- `data/manual_check_bundle/` is scratch data this session wrote to disk to
  have something real to click through — three emails, one clean, one with a
  planted consignee mismatch, one missing its second attachment. It is
  git-ignored like everything under `data/`. Do not confuse it with the real
  participant bundle or with the curated `demo_data/` the team still needs to
  decide on (`docs/ROADMAP.md`, "What the data problem is").
- `backend/api/store.py` is in-memory and empty on every restart — this
  session restarted the API once (to pick up `category_confidence`) and lost
  the first demo run; had to click "Start a run" again. Anyone deploying to
  Render should expect the same on every redeploy.
- Both dev servers were left running for hands-on inspection: backend on
  `:8000` (`SENTINEL_DATA_ROOT` pointed at `data/manual_check_bundle`),
  frontend on `:3000` (`web/.env.local` points at `:8000`). Stop them with
  whatever owns those ports before starting your own.
- If you add a new page under any `app/**/[param]/...` folder, put its markup
  in a `components/*-page-view.tsx` and keep the `page.tsx` to a two-line
  `params` unwrap. This is not a style preference — skipping it reproduces
  the silent Tailwind compile failure two sections up.

---

## 2026-09-19 — Claude session 4 · Phase 3a (`backend/api/`) built and verified

**Done**
- Built `backend/api/` end to end: `main.py` (FastAPI app + CORS), `store.py`
  (in-memory run/case store — no Postgres yet, see `ARCHITECTURE.md` §5),
  `pipeline_runner.py` (background-thread run over a bundled inbox),
  `direct_compare.py` (`POST /compare` logic), `models.py` (Pydantic at the
  boundary only, per `ARCHITECTURE.md`). All 8 endpoints from this file's own
  table are live: `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/cases`,
  `GET /cases/{id}`, `POST /cases/{id}/review`, `POST /compare`, `GET /metrics`,
  `GET /submission`. Nothing under `backend/sdoc/` was touched — the API calls
  the same `Pipeline`, `evidence_gate.evaluate` and `Pipeline._apply` the CLI
  uses, so the decision rule is not duplicated.
- `/compare` reuses the exact reader/doctype/extract/compare/gate stages
  `Pipeline._process` runs for a `BL_COMPARISON` email, so a judge's own
  upload gets the same evidence-gated decision the graded inbox does — no
  separate, weaker code path for the demo case.
- Found and fixed a real gap while building this, not before: `requirements.txt`
  listed `fastapi`/`uvicorn`/`pydantic` but nothing had ever exercised
  `UploadFile`, so the missing `python-multipart` dependency had never
  surfaced. Added it, plus `httpx` under `# --- dev ---` for
  `fastapi.testclient.TestClient`. Both installed clean in a fresh venv.
- Wrote `backend/tests/test_api.py` — 7 tests against synthetic fixtures built
  in the file itself, never `data/bundle` (`COLLABORATION.md` non-negotiable
  #1). Covers: matching documents → `OK`; a planted consignee mismatch →
  `MISMATCH` with a traceable evidence snippet on both sides; an empty upload
  → `NEEDS_REVIEW`, not a crash; and the full run lifecycle — create, poll
  status, list cases, fetch one, submit a review, confirm it persists, read
  `/metrics` and `/submission` — against a 3-email synthetic inbox (clean
  match / planted mismatch / missing second attachment), asserting the exact
  `OK` / `MISMATCH` / `NEEDS_REVIEW` split. All 7 passed on the first real run.
- Verified independently, not just asserted: fresh `.venv`, clean
  `pip install -r backend/requirements.txt` (confirms the `pdfplumber==0.11.10`
  pin from session 3 really does resolve), full suite **391 passed / 141
  skipped / 1 xfailed** (up from 384 before this session's 7 new tests — exact
  match, nothing else moved). Then booted a **real** `uvicorn` process (not
  TestClient) and hit it with `curl`: `GET /` → 200, `GET /openapi.json` → 200,
  a real multipart `POST /compare` → 200 with a traced, evidence-linked
  response. Stopped the process afterward.
- Note for whoever reads session 3's own numbers next to this one: this
  session's from-scratch venv measured **384 passed**, not the 330 that
  session 3's entry states for the same "no bundle" condition. Both agree on
  141 skipped. Recorded rather than quietly using whichever number was
  convenient — if it matters, `git log`/`git blame` on `docs/STATUS.md` and
  the test files will show which count is stale.

**Next**
- **3b, `web/` — does not exist yet.** The dashboard is the actual point of
  the project ("the discrepancy report... is the screen the whole project
  exists to produce; build it first" — this file's own words below). The API
  underneath it is now real, not a placeholder to build against.
- **3c, deploy — does not exist yet.** Render + Vercel accounts, Dockerfile,
  the public-vs-private repo flip: none of this is something a coding session
  can do unattended — it needs the humans' accounts and a decision on what
  goes in `demo_data/` (the open question two sections below, still open).
- Job handling from this file's own checklist is **half done**: a failed run
  is visible (`status: "failed"` + `error` on `GET /runs/{id}`, and a crashed
  *email* already always became a `NEEDS_REVIEW` case rather than losing the
  run — that part is `Pipeline.process`'s own existing behavior, not new).
  Retrying **one case** without re-running the whole inbox is not built; there
  is no endpoint for it. Small to add (`pipeline.process()` on one
  `EmailRecord`, overwrite that case in the store) but it is untested and
  unbuilt, not merely undocumented — do not assume it exists.
- `POST /runs` cannot be exercised against the real inbox from this session:
  `data/bundle` is git-ignored and was not present in the working copy this
  session ran in. Every `/runs` assertion above is against a synthetic 3-email
  inbox built in the test file. Point `SENTINEL_DATA_ROOT` at a real bundle
  and re-run `docs/SCORING.md`'s commands through the API instead of the CLI
  as the first thing the next session does, before trusting this further.

**Careful**
- `store.py` is one process's memory. It is fine for a single Render instance
  and it is gone on every restart — no run history survives a redeploy. That
  is an explicit, documented trade, not an oversight; swapping in the planned
  Postgres touches that one file's internals, not the routes, because nothing
  outside `store.py` reaches into its dict.
- `direct_compare.py` calls `Pipeline._apply`, a name-mangled-looking internal
  of `sdoc.pipeline`. Deliberate — the alternative was re-deriving the
  grounded/`NEEDS_REVIEW` decision rule a second time, which is exactly the
  kind of duplication `DECISIONS.md` warns against elsewhere. If `_apply`'s
  signature ever changes, this file breaks loudly at import or at the first
  test run, not silently.
- Do not read the "391 passed" figure above as license to stop checking
  numbers against `docs/SCORING.md`'s official scorer — this count is pytest
  health, not accuracy. Nothing in `backend/sdoc/` changed this session, so
  the score is still exactly what session 2/3 measured it at.

---

## 2026-09-19 — Claude session 3 · Phase 2 closed

**Done**
- **Phase 2 is complete.** Both fixes the previous session left unverified are
  now measured, tested and green; the adversarial evidence is regenerated; and
  three real defects found along the way are fixed. `ROADMAP.md` Phase 2 is
  ticked and `docs/ADVERSARIAL.md` is the write-up.
- Finished the work session 2 died mid-edit on. It had written the truncation
  repair in `compare.py` and hit its usage limit before running anything. The
  repair is sound: wrapped-value false discrepancies **64 → 0**, and it is
  provably inert on real data — over 520 emails the prefix relationship is hit
  exactly once (`email_145` shipper) and the repair declines, so the genuine
  defect survives. The separator fix in `readers/rows.py` recovers 3 × 1281
  field reads that were being lost.
- Wrote the tests neither fix had: `test_compare_wrap.py` (24) and
  `test_rows_separators.py` (53). A mutation review then found two loosenings
  of the repair's central promise — *it may recognise that we cut a value
  short; it may never invent agreement* — that the whole suite missed. Both
  now have killers: dropping the whitespace boundary guard fabricates
  `NANTONG , CHINA`, text that appears in no document; relaxing `==` to
  `startswith` silently rewrites a value and its evidence snippet.
- **Closed a hole the harness structurally cannot see.** `WRatio` folds in a
  partial-ratio component, so the three-character synonyms `POL`, `POD` and
  `G.W.` scored 90 inside any longer string containing those letters:
  `resolve("NAPOLI CENTRALE")` answered `port_of_loading`, `PODIUM TOWER`
  answered `port_of_discharge`, and so did `43-45 METROPOLITAN ROAD`. The old
  guard rejected a short *query*; nothing rejected a short *candidate*. Fixed
  with `_MIN_FUZZY_SYNONYM_CHARS = 6` and pinned by `test_labels_fuzzy.py`.
- **That fix then had a cost of its own, and the review caught it — worth
  reading as a pattern, not an anecdote.** Pruning the pool dropped three
  keys: `POL`, `POD` and `G.W.`. The code comment justified it by saying an
  abbreviation is caught by pass 1 or pass 2 anyway. True for the two port
  ones, which have their own alternatives in the pass-2 rules — and **false
  for `G.W.`**, which had no rule at all, so the fuzzy pass was its only
  resolver. Every decorated spelling (`G.W. (KGS)`, `TOTAL G.W.`,
  `G.W. 毛重(KGS)`) silently began resolving to nothing while the bare form
  kept working, and the test written to guard the invariant checked only that
  bare form. `DATA_NOTES.md` §2b says every weight label in this set carries
  exactly such a parenthetical, so the regressed spellings are the realistic
  ones. Fixed by giving the abbreviation the rule the comment assumed it had
  (`\bG\s*W\b`, matching nothing in any of the four datasets), and the tests
  now pin the family a spelling at a time. **The score never moved through any
  of this** — which is the point: it could not have told us.
- Three real defects fixed: `llm_calls` was declared, aggregated and printed
  but never incremented, so every run reported "0 model calls" while the usage
  block said six — `Pipeline.process` now differences `client.usage.calls`
  around each email, outside the `except`, because a crashed email may already
  have paid for a call. `pypdfium2` and `pillow` are pinned: `readers/scan.py`
  imports both directly and they were only ever present as pdfplumber's
  dependencies, so a resolver change would have switched the vision path off
  in silence. And `pip install -r backend/requirements.txt` **failed outright**
  with `ResolutionImpossible` — `pdfplumber==0.11.4` under the `>=0.11.9` that
  `markitdown[pdf]` demands — meaning no judge following the README could
  install the project at all. The pin is now 0.11.10, the version every
  measured score was actually produced with.
- The suite no longer breaks on a fresh clone. 304 tests read git-ignored
  `data/bundle/` with no guard and *errored* rather than skipped; with the
  guard in `conftest.py` a clone with no data is 330 passed / 141 skipped /
  **0 errors**.

- **Phase 2's definition of done is now actually met, not rounded up.** The
  bar was "what breaks the deterministic path *and what the LLM layer
  recovers*", and the second half had never been measured — both harness runs
  were `pipeline_mode: deterministic`. Ran it with the model on
  (`adversarial.py --only unseen_labels --llm`): unfamiliar label wording
  forces **168 of 188** cases to a human on the rules alone and **2** with the
  model, while false discrepancies, silent wrong values and masked
  discrepancies all stay at **zero**. 178 calls, $0.2447. Written up as
  `ADVERSARIAL.md` §8, which also spells out how to quote it honestly — the
  model does no work on the graded inbox.
- Added `--llm` to the harness CLI. It refuses to write a report labelled
  `assisted` if no usable client is configured, because a file that misstates
  which pipeline it measured is worse than no file.

**Next**
- **Phase 3, and it is the whole remaining risk.** See `ROADMAP.md` — it now
  carries the endpoint list, the screen list and the deploy plan, so the next
  session can start writing instead of re-deriving. Roughly 40 of the judges'
  100 points ride on a live deployed demo and meaningful cloud use, and that
  is currently zero lines of code. Do the deploy on the 20th, not the 21st.
- The one Phase 2 box still open is **(T)**, not (C): hand-check ten escalated
  cases. A score cannot tell us whether a reason reads sensibly to an operator.

**Careful**
- **No decision moved.** All four datasets still score **1.0000** and every
  `submission.json` is byte-identical to the previous run. The no-key run is
  byte-identical to the LLM-enabled run, which is the honest way to say that
  the model changes nothing here — the 1.0000 is entirely the rules'.
- **The fuzzy pass fires on zero labels in all four datasets.** Every real
  label is answered by pass 1 or pass 2 — 13,620 chunk labels were classified
  by pass to confirm it. So the score *cannot* detect a regression in
  `labels.py`; measure that one on the unit tests and the harness instead.
- One `xfail` remains and it is legitimate: `_extend` uses
  `text.find(value.raw)`, taking the *first* occurrence rather than the one
  the evidence locator points at. Consignee and notify party are frequently
  the same company here, so a continuation can be read from the wrong block.
  It has fired 0 times on real data. Anchoring `_extend` on the locator is the
  fix, and `test_compare_wrap.py:601` goes green the day it lands.
- **`runs/` is git-ignored and agents write into it.** The full 94-pair
  adversarial report was silently overwritten by a 40-pair partial run during
  verification, so the file on disk stopped reproducing the numbers
  `ADVERSARIAL.md` cites. Regenerated and checked cell by cell. If you script
  anything against the harness, write it to the scratchpad, not to `runs/`.
- `runs/adversarial.json` was previously a snapshot taken *between* two fixes
  and understated the system. It is regenerated. If you change extraction,
  regenerate it again — a table a judge cannot reproduce is worse than none.
- OCR character confusion is **open** and stated plainly in `ADVERSARIAL.md`.
  Do not let a judge discover it unprompted; the mitigation is real
  (`readers/scan.py` keeps image-only scans unreadable, so our own OCR never
  feeds a decision) and the caveat is honest (the perturbation really does
  alter the document).

---

## 2026-09-19 — Claude session 2

**Done**
- Phase 1 is complete. The deterministic pipeline runs end to end over all 520
  emails in ~2.3 ms each, with no model calls and no network.
- Repository published: `TCF1209/duocode-sentinel` (private — **make it public
  before the submission deadline**, the rules require a public link).
- Scores 1.0000 on the dev set **and on three held-out seeds** at three
  different scales — 225 defect emails in total, every one caught with the
  exact field set, no false alarms, 80/80 escalations correct. Table in
  `SCORING.md` §4.1.
- Found and fixed the only two false alarms the system produced, which shared
  one cause: a long PDF label drawn through its own value, interleaving the
  characters (`"...Intermediate ConsCigEnReIEeX"`). Labels and values are now
  separated by font where the geometry is ambiguous.
- Fixed a second, subtler fault the first fix exposed: the value column was
  detected from the most common word left-edge, so a fifteen-row container
  table outvoted the form's own value column.
- Added the markitdown fallback reader for formats we have no precise reader
  for, `scripts/evaluate.py` (pipeline + official scorer in one command), and
  `docs/DECISIONS.md`.

**Next**
- Phase 2, but **not** as "raise the score" — it is already at the ceiling on
  everything this generator can produce. The real work is robustness *beyond*
  the generator: the LLM fallback for unseen label wording (the classifier
  already reports `needs_llm` and nothing consumes it), the vision path for
  scans, and adversarial perturbation of the documents to find where we break.
- Then Phase 3: API, dashboard, deployment.

**Careful**
- **A perfect score is a reason for suspicion, not celebration.** All four
  datasets come from one generator, with one label vocabulary and one set of
  renderers. It proves we do not memorise a draw; it does not prove we survive
  a real document. Say it that way in the pitch too — judges respect a team
  that states the limits of its own evidence.
- Do not "simplify" `_value_column_from_labelled_rows()` in `readers/pdf.py`
  back to counting word edges. That is exactly the bug that cost an end-to-end
  point, and the score log records it.
- The score log in `SCORING.md` deliberately keeps the row where the score went
  *down*. Do not tidy it away.

---

## 2026-09-19 — Claude session 1

**Done**
- Read every artefact (problem statement, rules, infopack, participant bundle,
  organiser Docker bundle) and wrote up the findings in `docs/DATA_NOTES.md`.
- Repo scaffold, venv, dependencies, git-ignored `data/`.
- Architecture settled and documented: deterministic-first pipeline with an
  LLM fallback, evidence attached to every extracted value, `NEEDS_REVIEW` as
  a first-class outcome.
- Core modules written: `schema.py`, `normalize.py`, `labels.py`, and the
  readers for `.txt`, `.docx`, `.xlsx` and `.pdf`.

**Next**
- Phase 1 in `docs/ROADMAP.md`: `doctype.py`, `readers/__init__.py`,
  `extract/fields.py`, `compare.py`, `classify/`, `pipeline.py`, `run.py` —
  then the first measured score.

**Careful**
- The PDF reader reconstructs columns from word coordinates on purpose. Do not
  replace it with a line-based parser, however much simpler that looks:
  `pdftotext -layout` pairs labels with the wrong values on these documents and
  produces *confident* false discrepancies. See `DATA_NOTES.md` §3.
- In `labels.py`, the `NOTIFY` rule must stay above the `CONSIGNEE` rule —
  "Notify Party/Intermediate Consignee" contains the word *Consignee*.
- Two different emails in the set have zero attachments and *opposite* correct
  outcomes, separated only by intent. See `DATA_NOTES.md` §5a.
