# Deploy — the live demo, step by literal step

Two services, two files, one afternoon's worth of dashboard archaeology avoided.

- **Backend** — FastAPI in Docker on **Render**, configured by `render.yaml`
  at the repository root.
- **Frontend** — the Next.js dashboard on **Vercel**, configured by
  `web/vercel.json`.

Both files are committed, so a failed deploy is retried by pressing the button
again, not by remembering what was clicked. This document covers the parts that
a file cannot do for you.

> **Written to be followed at 2am by someone who is tired.** Every step says
> which site, which button, and what you should see. If a step's check does not
> produce the output shown, stop there and go to
> [Troubleshooting](#troubleshooting) — do not carry a broken step forward, as
> both of the failures that kill this demo are silent and look fine one step
> later.

---

## What a human must do, and it is only this

Everything else is in the two config files. These five cannot be automated,
because they involve creating accounts and holding a secret:

1. Create a **Render** account and authorise it against the GitHub repository.
2. Create a **Vercel** account and authorise it against the same repository.
3. Paste the **OpenAI API key** into Render's prompt when the Blueprint asks.
4. Set Vercel's **Root Directory** to `web` (one dropdown; `vercel.json` cannot
   set this, because Vercel only reads `vercel.json` *after* it knows which
   directory the project lives in).
5. Flip the repository to **public** — `docs/ROADMAP.md` 3c, and the rules
   require a public link.

Budget 30 minutes for a first run, not an afternoon. Do it on the **20th**, not
the 21st.

---

## Step 0 — pre-flight, and the one thing that will otherwise bite

Three things must be true before either deploy is worth starting. The third is
the one that is currently false.

### 0.1 · The Dockerfile and .dockerignore exist at the repository root

```bash
test -f Dockerfile && test -f .dockerignore && echo "both present" || echo "MISSING — stop here"
```

`render.yaml` points at `./Dockerfile` with the build context at the repository
root, and the two files agree on the three things that have to match — checked,
not assumed:

| Contract | `render.yaml` | `Dockerfile` |
|---|---|---|
| Data path | `SENTINEL_DATA_ROOT=/app/demo_data` | `COPY demo_data/ demo_data/`, `WORKDIR /app` |
| Port | Render injects `$PORT` | `uvicorn --host 0.0.0.0 --port ${PORT:-8000}` |
| Health | `healthCheckPath: /` | `HEALTHCHECK` against `/` |

If you change the data path, change it in **both** files.

### 0.2 · The repository is public

Render and Vercel can both build from a private repository, but the judges
cannot read one. Do this now rather than on submission morning:

**GitHub → the repository → Settings → General → scroll to Danger Zone →
Change repository visibility → Make public.**

### 0.3 · There is demo data committed — *there is, now*

`/data/` is git-ignored and Render builds from git, so a container built from
this repo would have nothing to serve. `demo_data/` is the answer and it is
committed:

```bash
git ls-files demo_data/ | wc -l     # 62: 30 emails, 31 attachments, a README
```

Thirty emails, 360 KB, chosen by `scripts/make_demo_data.py` to cover all five
categories, all four escalation reasons, six defect emails across all four
attachment formats, eighteen clean comparisons, and the zero-attachment pair
from `DATA_NOTES.md` §5a whose two emails have opposite correct outcomes. Only
the participant bundle is in there; `data/_grader/` never goes near it.

If you ever replace it, note the two ways the shape bites, at different moments:

> **If `demo_data/` is absent entirely**, the Dockerfile's
> `COPY demo_data/ demo_data/` **fails the build**, with
> `"/demo_data": not found`. That is the good outcome — it is loud, it happens
> in step 1, and nothing gets deployed.
>
> **If `demo_data/` exists but the emails are nested wrongly** — anywhere other
> than `demo_data/inbox/email_*.json` — the build succeeds, the service goes
> green, `GET /` answers `{"status":"ok"}`, and then **Start a run** returns
> `400`. That is the dangerous one. **A green Render dashboard does not mean
> the demo works**, which is why step 2 checks the data with a second call —
> and why `GET /` now carries a `ready` field that does.

## Step 1 — deploy the backend to Render

1. Go to **https://dashboard.render.com** and sign in with GitHub.
2. Click **Add new** (top right) → **Blueprint**.
3. Under **Connect a repository**, find `TCF1209/duocode-sentinel` and click
   **Connect**. If it is not listed, click **Configure account** and grant
   Render access to the repository.
4. Render reads `render.yaml` and shows a plan: one web service named
   **`sdoc-sentinel-api`**. It should say **Docker** and **Free**.
5. Render prompts for the one value not in the file: a field labelled
   **`OPENAI_API_KEY`**. Paste the key. It is stored encrypted and never
   written to the repository — that is what `sync: false` in `render.yaml`
   means.
   - Leaving it blank is **safe**: the pipeline runs fully without a key
     (`CLAUDE.md` rule 5) and simply escalates the cases the model would have
     recovered. A blank key degrades the demo; it does not break it.
6. Click **Apply** / **Deploy Blueprint**.

The first build takes **5–10 minutes** — it compiles the PDF and imaging
dependencies. Watch **Logs**. You are waiting for a line like
`Uvicorn running on http://0.0.0.0:10000`, then the status badge turning
**Live**.

**Write down the hostname Render gives you**, shown at the top of the service
page. It should be:

```
https://sdoc-sentinel-api.onrender.com
```

If it is anything else — `onrender.com` subdomains are globally unique, so a
taken name gets a suffix — **note the difference now**; step 4 depends on it.

---

## Step 2 — check the backend is actually up

From any terminal. On **PowerShell use `curl.exe`**, not `curl`, which is an
alias for `Invoke-WebRequest` and takes different arguments.

```bash
curl -s https://sdoc-sentinel-api.onrender.com/
```

Expected, exactly:

```json
{"service":"sentinel-api","status":"ok"}
```

Now the check that matters — **does it have data?** This is the one step 0.3
warned about:

```bash
curl -s -X POST https://sdoc-sentinel-api.onrender.com/runs \
  -H 'content-type: application/json' -d '{"use_llm": false}'
```

- Success: `{"run_id":"run_000001_1758..."}` — the data is there.
- Failure: `{"detail":"No inbox at /app/demo_data/inbox. ..."}` — a `400`.
  Step 0.3 is unresolved. Go back and fix it; nothing downstream will work.

Give it ten seconds, then confirm the run finished and the pipeline behaved:

```bash
curl -s https://sdoc-sentinel-api.onrender.com/metrics
```

You want a JSON body with `emails`, `by_category`, `rule_share` and
`mean_ms_per_email`. A `rule_share` at or near `1.0` and a low
`mean_ms_per_email` are the numbers the project's claims rest on — if they look
wrong here, the image is not carrying the data you think it is.

---

## Step 3 — deploy the frontend to Vercel

1. Go to **https://vercel.com/new** and sign in with GitHub.
2. Find `duocode-sentinel` in the repository list and click **Import**.
3. **This is the step that cannot be put in a file.** Expand
   **Root Directory**, click **Edit**, and select the **`web`** folder.
   - Vercel only reads `web/vercel.json` once it knows the project lives in
     `web/`. Leave Root Directory at the repository root and the build fails
     with "No Next.js version detected", because the root has no
     `package.json`.
4. **Framework Preset** should now auto-detect as **Next.js**. Leave Build and
   Output settings alone — `vercel.json` sets `npm ci` and `next build`.
5. Do **not** add an environment variable here. `vercel.json` already sets
   `NEXT_PUBLIC_SENTINEL_API_URL` at build time, and a value set in both places
   is a value you will later change in the wrong one. See step 4.
6. Click **Deploy**. The build takes 2–4 minutes.

---

## Step 4 — the failure that kills this demo in front of a judge

Read this even if everything is green.

`web/lib/api.ts` resolves the backend address like this:

```ts
export const API_BASE =
  process.env.NEXT_PUBLIC_SENTINEL_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
```

`NEXT_PUBLIC_*` variables are **inlined by `next build`**. They are baked into
the JavaScript bundle that ships to the browser; they are not read at runtime.
So the value must be correct *at build time*, and changing it later requires a
**rebuild**, not a restart. The behaviour, verified rather than assumed:

| Value at build time | Resulting `API_BASE` | What the judge sees |
|---|---|---|
| **unset** | `http://127.0.0.1:8000` | The page loads, then hangs. The browser is asking **the judge's own laptop** for the data. No error is shown on screen. |
| **empty string** | `""` | Requests go to `/runs` on the Vercel domain and 404. Note the `??` does **not** save you — `""` is not nullish, so the fallback never fires. |
| `https://…onrender.com/` (trailing slash) | slash stripped — fine | Works. |
| `https://…onrender.com` | as given | Works. |

**This is why the URL is committed in `web/vercel.json` rather than typed into
the Vercel dashboard.** A dashboard variable can be forgotten; a committed one
cannot, and it is reviewable. It is a public hostname, not a secret, so there is
no reason to hide it.

### The one line to check

```bash
cat web/vercel.json
```

The `NEXT_PUBLIC_SENTINEL_API_URL` value must equal the hostname Render printed
in step 1, **with no trailing slash**. If Render gave you a different hostname,
edit that one line, commit, and push — Vercel rebuilds automatically.

### Confirm it landed in the bundle

Do not trust the config; check the artefact. Open the deployed site, open
**DevTools → Network**, reload, and look at where the `runs` request goes. It
must be your `onrender.com` host. If it says `127.0.0.1:8000`, the variable was
not present at build time — go to [Troubleshooting](#b-the-page-loads-then-hangs-forever).

---

## Step 5 — the run that has to exist before the judge arrives

The API stores runs **in memory** (`backend/api/store.py`: "a single process's
memory, gone on restart"), and Render's free plan **spins the container down
after roughly 15 minutes of inactivity**. Every cold start therefore wipes
every run.

**The API now handles this itself.** A lifespan handler runs the demo inbox
once at boot — deterministic, no key, under a second — so a judge opening a
cold link lands on a dashboard with a completed run already on it rather than
on "No runs yet". `GET /` reports it:

```bash
curl -s https://sdoc-sentinel-api.onrender.com/
# {"service":"sentinel-api","status":"ok","data_root":"/app/demo_data",
#  "ready":true,"llm_runs_allowed":false}
```

`ready` is the field that matters. `status: ok` only says the container is
listening; `ready: true` says a run completed, which means the data was found
and the pipeline worked.

**What is still a demo ritual.** Autorun removes the empty dashboard, not the
cold start itself: the container still has to wake, and that first request is
the slow one (see Troubleshooting A). So **five minutes before any demo or
recording**, spend it yourself:

```bash
curl -s https://sdoc-sentinel-api.onrender.com/     # wakes it; expect ready:true
```

If `ready` comes back `false`, the container is up and the data is not — go to
Troubleshooting F before you record anything.

To disable autorun (for instance to demonstrate the button live), set
`SENTINEL_AUTORUN=0` on the service.

---

## Step 6 — the final check, as a judge would do it

Do this on a phone, on mobile data, not on the laptop that has been talking to
these services all evening. A cached bundle or a warm container will hide
exactly the failures you are testing for.

| # | Check | Expected |
|---|---|---|
| 1 | Open the Vercel URL | The dashboard renders, with at least one run listed |
| 2 | Click that run | The case list loads, with category, status and `rule`/`llm` badges |
| 3 | Open a `MISMATCH` case | SI and BL side by side, mismatched fields highlighted, **an evidence snippet under each value** |
| 4 | Open the metrics page | Cost, latency and rule share, all populated |
| 5 | Go to **/compare** and upload two documents | A comparison report, or an honest `NEEDS_REVIEW` with a reason — both are good outcomes |

Check 3 is the screen the whole project exists to produce. If only one thing
gets tested, test that.

---

## Troubleshooting

### A. The first request takes 50 seconds, or times out

**Render free-tier cold start.** The container is spun down after ~15 minutes
idle and must be rebuilt from its image on the next request. The first request
waits 30–60 seconds; everything after it is fast.

This is the single most likely thing to happen to a judge, because judges arrive
at links that have been sitting idle.

- **Before a demo:** run the warm-up in step 5. Always.
- **During:** if it happens live, say what it is — a cold container on a free
  tier — and keep talking. It resolves itself.
- **For an unattended link** (a submission form a judge opens whenever they
  like): set up an external pinger — https://uptimerobot.com, free, `GET /`
  every 5 minutes. This keeps the container warm but **does not** preserve runs,
  because a request that arrives while the process is alive does not restart it,
  whilst any restart still empties the store. Pair it with step 5 on demo day.
- Do **not** "fix" this by upgrading the plan without checking the budget.

### B. The page loads, then hangs forever

`NEXT_PUBLIC_SENTINEL_API_URL` was not set at build time, so the bundle is
pointing at `127.0.0.1:8000` — the judge's own machine. See step 4.

Confirm it, do not guess: DevTools → Network → reload → look at the request
host. Or from a terminal, grep the shipped JavaScript:

```bash
curl -s https://<your-app>.vercel.app | grep -o '127\.0\.0\.1:8000' && echo "CONFIRMED: localhost is baked in"
```

Fix: correct the value in `web/vercel.json`, commit, push. Then — and this is
the part people miss — **make sure a rebuild actually happened**. Changing an
environment variable in Vercel's dashboard does *not* rebuild by itself; in
**Deployments → ⋯ → Redeploy**, untick **Use existing Build Cache**.

### C. CORS errors in the browser console

`Access-Control-Allow-Origin` errors mean the API is reachable but refusing the
origin. `backend/api/main.py` defaults `SENTINEL_CORS_ORIGINS` to `*`, and
`render.yaml` sets it to `*` explicitly, so this should not happen — if it does,
someone narrowed it.

- Check **Render → the service → Environment** for a `SENTINEL_CORS_ORIGINS`
  that is not `*`. A dashboard edit overrides the file until the Blueprint is
  re-applied, which is precisely the drift `render.yaml` exists to prevent.
- Each Vercel **preview** deployment gets its own hostname, so any allow-list
  narrow enough to name production will break previews. Leave it at `*`:
  `allow_credentials=False` in `main.py` means `*` carries no cookie risk.
- A CORS error in the console **with no network response at all** is usually not
  CORS — it is the backend being down or cold. Check `curl -s <api>/` first.

### D. The Vercel build runs out of memory

Unlikely at this size — the app is five routes, and the only heavy dependency is
Recharts on the metrics page — but the error is `JavaScript heap out of memory`
or a bare `exit code 137`, and it is unmistakable when it happens.

In **Vercel → Settings → Environment Variables**, add:

```
NODE_OPTIONS = --max-old-space-size=4096
```

then redeploy **without** the build cache. If it still fails, the cause is
usually a dependency cycle rather than genuine memory pressure — reproduce it
locally with `cd web && npm ci && npm run build`, which fails the same way and
gives a far better error.

### E. The Render build runs out of memory, or the container restarts in a loop

The free plan is 512 MB RAM. The pipeline itself is light (~3 ms/email), but
`pypdfium2` rendering a scanned page to a bitmap is not.

- If it dies **during build**, the image is too heavy — a `python:3.10-slim`
  base and a single-stage `pip install --no-cache-dir` is the intended shape.
- If it dies **under use**, it will be on a scanned PDF. Run with `use_llm:
  false` for the demo; the rules decide 100% of cases on this dataset anyway,
  and the vision path is the only thing that needs that memory.
- `Exited with status 1` immediately after `==> Starting service` is almost
  never memory — it is the container not binding `$PORT`. See step 0.1.

### F. `POST /runs` returns 400

```json
{"detail": "No inbox at /app/demo_data/inbox. ..."}
```

The image has data at `/app/demo_data` but no `inbox/` **inside** it — if
`demo_data/` were missing altogether the build would have failed instead (step
0.3). So this is a nesting mistake: the emails are at `demo_data/email_*.json`
rather than `demo_data/inbox/email_*.json`.

Confirm it without redeploying, in **Render → the service → Shell**:

```bash
ls /app/demo_data && ls /app/demo_data/inbox | head
```

Fix the layout in the repository, commit, push. This is the most likely reason
for a deploy that looks perfect and demos badly.

### G. The Render build fails with `"/demo_data": not found`

`demo_data/` has not been committed at all — step 0.3. Note this is the *safe*
failure: nothing was deployed, and the previous live version, if any, is
untouched. `git ls-files demo_data/ | wc -l` will print `0`.

### H. `GET /metrics` returns 404 `"no completed run yet"`

Not a fault. The store is empty because the container restarted. Start a run —
step 5.

---

## Recommended follow-up: make the localhost fallback fail loudly

Not applied here, because `web/lib/api.ts` belongs to the dashboard work and
this task is the deployment configuration — changing it is a drive-by edit. It
is worth doing, and it is a five-line change.

**The case for it:** the committed URL in `vercel.json` closes the most likely
route to this failure, but not every route. A preview deployment built from a
branch where someone edited `vercel.json`, a Vercel project whose Root Directory
was misconfigured so the file is never read, or an environment variable set to
`""` in the dashboard, all still produce a bundle that quietly points at the
judge's own laptop. The current code cannot tell the difference between "running
locally, use localhost" and "shipped to production with no configuration". The
build knows, and should say so.

In `web/lib/api.ts`, replace the `API_BASE` export with:

```ts
// NEXT_PUBLIC_* is inlined by `next build`, so an unset value is baked into the
// shipped bundle and cannot be corrected at runtime — the page would silently
// ask the visitor's own machine for data and hang with no error. Failing the
// build is the only place this is still cheap to fix. See docs/DEPLOY.md step 4.
const configured = process.env.NEXT_PUBLIC_SENTINEL_API_URL?.trim();

if (!configured && process.env.NODE_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_SENTINEL_API_URL is not set. A production build without it " +
      "points the browser at http://127.0.0.1:8000. Set it in web/vercel.json.",
  );
}

export const API_BASE = (configured || "http://127.0.0.1:8000").replace(/\/$/, "");
```

Three things this deliberately gets right:

1. It tests `!configured` after `.trim()`, so the **empty-string** case is
   caught too. The original's `??` does not fire on `""` — verified — and `""`
   fails differently and more confusingly, as 404s against the Vercel domain.
2. It is guarded on `NODE_ENV === "production"`, so `npm run dev` keeps working
   against a local backend with no configuration at all.
3. Being at module scope, it throws during **prerendering**, which fails
   `next build` and so fails the Vercel deploy. The broken bundle is never
   published — the deploy goes red instead of the demo going quiet.

Verify after applying: `cd web && npm run build` with the variable unset should
fail with that message; with it set, it should build.
