"""FastAPI surface over the sdoc pipeline (docs/ROADMAP.md Phase 3a).

The pipeline package has no web or database imports (ARCHITECTURE.md section
5), so every route here is a thin adapter: read the request, call the same
pipeline code `backend/run.py` uses, shape the response. No pipeline decision
logic is duplicated in this file.

Run locally:

    .venv/Scripts/python.exe -m uvicorn backend.api.main:app --reload --port 8000

or, with backend/ as the working directory:

    cd backend && ../.venv/Scripts/python.exe -m uvicorn api.main:app --reload
"""
from __future__ import annotations

import mimetypes
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sdoc.pipeline import build_client  # noqa: E402
from sdoc.readers import scan  # noqa: E402

from .direct_compare import MAX_BYTES, compare_uploads  # noqa: E402
from .patterns import summarise as summarise_patterns  # noqa: E402
from .reply_polish import LLMUnavailable, PolishRequest, polish as polish_reply  # noqa: E402
from .models import (  # noqa: E402
    ReviewRequest,
    RunCreateRequest,
    RunCreateResponse,
    RunStatusResponse,
)
from .pipeline_runner import retry_case, start_run  # noqa: E402
from .review_outcome import FIELD_DECISIONS, SIDES, derive as derive_review  # noqa: E402
from .store import store  # noqa: E402

DEFAULT_DATA_ROOT = Path(os.environ.get("SENTINEL_DATA_ROOT", str(BACKEND.parent / "data" / "bundle")))
_cors_env = os.environ.get("SENTINEL_CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# The deployed API is public and unauthenticated, so the two things a stranger
# could do that cost us something are gated here rather than in the request
# model: spending the OpenAI key, and queueing work without limit.
ALLOW_LLM_RUNS = _flag("SENTINEL_ALLOW_LLM_RUNS", False)
MAX_ACTIVE_RUNS = int(os.environ.get("SENTINEL_MAX_ACTIVE_RUNS", "2"))

# A judge arriving at a cold free-tier container would otherwise land on an
# empty dashboard and have to know to press a button. One deterministic run
# over the demo inbox costs well under a second and no model call, so the
# first screen has something on it. Off when there is no data to read.
AUTORUN = _flag("SENTINEL_AUTORUN", True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Have something to show before anyone asks.

    `store.py` is a single process's memory, and Render's free plan sleeps an
    idle container. So the first judge to open the link after a quiet spell
    arrives at a process that has just booted with nothing in it — an empty
    dashboard and a button they have to know to press. Since the deterministic
    path needs no key, no network and under a second for the demo inbox, the
    honest fix is to have already run it.

    Failure here is not fatal on purpose: if the data root is missing the API
    must still start and say so through `POST /runs`, rather than crash-loop on
    boot and show Render's error page instead of ours.
    """
    if AUTORUN:
        try:
            start_run(store, data_root=DEFAULT_DATA_ROOT, limit=None, use_llm=False)
        except Exception as exc:               # noqa: BLE001 - see docstring
            print(f"[startup] no warm run: {type(exc).__name__}: {exc}", flush=True)
    yield


app = FastAPI(
    title="Sentinel API",
    description="Shipping document verification — Averis x Monash Hackathon 2026",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_or_404(run_id: str):
    rec = store.get_run(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no run '{run_id}'")
    return rec


def _split_case_id(case_id: str) -> tuple[str, str]:
    run_id, sep, email_id = case_id.partition(":")
    if not sep or not email_id:
        raise HTTPException(status_code=400, detail="case id must be '<run_id>:<email_id>'")
    return run_id, email_id


def _record_to_status(rec) -> RunStatusResponse:
    return RunStatusResponse(
        run_id=rec.run_id,
        status=rec.status,
        total_emails=rec.total_emails,
        processed=rec.processed,
        llm_enabled=rec.llm_enabled,
        error=rec.error,
        metrics=rec.metrics,
    )


@app.get("/")
def root() -> dict:
    """Render's health check target — there is no /health route.

    It deliberately touches nothing: a green health check says the container
    is listening, and says nothing about whether the demo data is readable.
    `ready` is the field that answers the second question.

    `model_available` says whether a key is configured at all, which is what
    the reply draft's optional wording pass needs before it offers itself.
    It makes no network call, and it cannot fail this route: this is Render's
    health check, so a bad model setting must switch the model features off,
    never take the container down (`_model_available`).
    """
    return {
        "service": "sentinel-api",
        "status": "ok",
        "data_root": str(DEFAULT_DATA_ROOT),
        "ready": store.latest_done_run() is not None,
        "llm_runs_allowed": ALLOW_LLM_RUNS,
        "model_available": _model_available(),
    }


@app.post("/runs", response_model=RunCreateResponse)
def create_run(body: Optional[RunCreateRequest] = None) -> RunCreateResponse:
    """Start a run over the bundled demo inbox at SENTINEL_DATA_ROOT.

    Unauthenticated on purpose — a judge should not need an account to press
    the button — which is exactly why the two expensive requests are refused
    here rather than served: a model-enabled run on a server that has not
    opted in, and a run queued behind two that are already going.
    """
    body = body or RunCreateRequest()

    if body.use_llm and not ALLOW_LLM_RUNS:
        raise HTTPException(
            status_code=403,
            detail="this server does not allow model-enabled runs; "
                   "set SENTINEL_ALLOW_LLM_RUNS=1 to permit them. The "
                   "deterministic path runs either way.",
        )

    active = sum(1 for r in store.list_runs() if r.status == "running")
    if active >= MAX_ACTIVE_RUNS:
        raise HTTPException(
            status_code=429,
            detail=f"{active} runs already in progress; wait for one to finish.",
        )

    try:
        run_id = start_run(store, data_root=DEFAULT_DATA_ROOT, limit=body.limit, use_llm=body.use_llm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunCreateResponse(run_id=run_id)


@app.get("/runs", response_model=list[RunStatusResponse])
def list_runs() -> list[RunStatusResponse]:
    """Not in this file's original endpoint table — added for the dashboard's
    own run list (docs/ROADMAP.md 3b), since `store.list_runs` already existed
    for `latest_done_run` to build on."""
    return [_record_to_status(rec) for rec in store.list_runs()]


@app.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run(run_id: str) -> RunStatusResponse:
    return _record_to_status(_run_or_404(run_id))


def _shipper_name(c) -> Optional[str]:
    """The shipper's name as read off whichever side has it.

    Read-only projection of a value `pipeline.py` already computed — no new
    extraction, no new comparison, nothing that touches a decision. Exists so
    the dashboard's pattern view (docs/ROADMAP.md backlog) can group cases by
    counterparty without an extra request per case.
    """
    for comp in c.comparisons:
        if comp.field == "shipper":
            return comp.si.raw or comp.bl.raw
    return None


def _scan_state(c) -> tuple[bool, bool]:
    """(any document is an image-only scan, a vision model read one out).

    Read-only, like `_shipper_name`. `review_reason == "unreadable"` cannot
    tell a scan from a corrupt file, and the home page's "Scans transcribed for the
    reviewer" tile (web/lib/showcases.ts) opened a corrupt BL because of it -- there is
    nothing to read out of one. A scan is not always read out either: the
    startup warm run makes no model call by design, so its scans escalate
    with no transcript, and the tile has to know that too.
    """
    scans = [d for d in (c.si_doc, c.bl_doc) if d is not None and d.unreadable_reason == "no_text_layer"]
    return bool(scans), any(scan.transcript_of(d) is not None for d in scans)


@app.get("/runs/{run_id}/cases")
def list_cases(
    run_id: str,
    category: Optional[str] = None,
    status: Optional[str] = None,
    decided_by: Optional[str] = None,
) -> dict:
    _run_or_404(run_id)
    out = []
    for c in store.list_cases(run_id):
        # The effective outcome, so a `status=NEEDS_REVIEW` filter stops
        # returning a case a person has already resolved. Filtering on
        # `c.status` here was the bug: a correction saved, the detail page
        # showed it, and the queue it was supposed to clear never moved.
        eff = store.effective_outcome(run_id, c)
        if category and c.category != category:
            continue
        if status and eff["status"] != status:
            continue
        if decided_by and c.decided_by != decided_by:
            continue
        inbox = store.inbox_of(run_id, c.email_id)
        scanned, scan_transcribed = _scan_state(c)
        out.append({
            "case_id": f"{run_id}:{c.email_id}",
            "email_id": c.email_id,
            "sender": c.sender,
            # The email as it arrived, for the dashboard's "Before Sentinel"
            # view -- the desk's own inbox, no classification on it yet.
            "subject": inbox["subject"],
            "attachments": inbox["attachments"],
            "category": c.category,
            "category_confidence": round(c.category_confidence, 3),
            "status": eff["status"],
            "review_reason": eff["review_reason"],
            "has_defect": eff["has_defect"],
            "defect_fields": eff["defect_fields"],
            "shipper": _shipper_name(c),
            "decided_by": c.decided_by,
            # Both halves stay visible. A row the system called NEEDS_REVIEW
            # and a person corrected to OK is not the same thing as a row the
            # system called OK, and an operator scanning the queue should be
            # able to see which is which without opening it.
            "reviewed": eff["reviewed"],
            "outcome_source": eff["source"],
            "system_status": c.status,
            # Sentinel's own discrepant fields, so the list can tell a review
            # that left Sentinel's outcome standing from one that changed it,
            # by the same rule as store.review_summary.
            "system_defect_fields": sorted(c.defect_fields),
            # How many times this case's answer was replaced by a re-check on
            # re-sent documents (0 for almost every row). The list is the
            # place a reviewer notices "this one has moved on since the run".
            "recheck_count": store.recheck_count(run_id, c.email_id),
            # Which unreadable pairs are image-only scans, and whether one was
            # read out by the model (_scan_state) -- so the home page's scan
            # tile opens a scan that shows its transcript, not a corrupt file.
            "scanned": scanned,
            "scan_transcribed": scan_transcribed,
        })
    return {"run_id": run_id, "count": len(out), "cases": out}


def _case_report(run_id: str, email_id: str, result) -> dict:
    """The case detail's shape, shared by every route that returns one case.

    The system's own answer stays where it was, under the keys it has always
    used; `effective` is what the case is now. A UI that wants to show "we
    said X, a reviewer said Y" has both without diffing anything. `recheck`
    and `history` are null / empty for a case whose documents were never
    re-sent, so those cases read exactly as they did before re-checking
    existed.
    """
    report = result.to_report()
    report["review"] = store.get_review(run_id, email_id)
    report["effective"] = store.effective_outcome(run_id, result)
    report["recheck"] = store.recheck_info(run_id, email_id, result)
    report["history"] = store.get_history(run_id, email_id)
    report["inbox"] = store.inbox_of(run_id, email_id)
    return report


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    return _case_report(run_id, email_id, result)


def _disk_attachment(run_id: str, rel_path: str) -> Path:
    """Resolve an attachment path under the run's data root, or refuse.

    `rel_path` is the attachment path exactly as the inbox JSON's own
    "attachments" list wrote it (readers/__init__.py's read_attachment) --
    not request input, but resolved and contained anyway as a cheap,
    correct habit rather than a trust judgement call on data that happens
    to come from this dataset today.
    """
    run = store.get_run(run_id)
    if run is None or not run.data_root:
        raise HTTPException(status_code=404, detail=f"no data root recorded for run '{run_id}'")
    data_root = Path(run.data_root).resolve()
    full_path = (data_root / rel_path).resolve()
    if data_root not in full_path.parents and full_path != data_root:
        raise HTTPException(status_code=400, detail="attachment path escapes the data root")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"{rel_path} is no longer on disk")
    return full_path


def _inline_bytes(filename: str, data: bytes) -> Response:
    """A re-sent file, served from memory the way `FileResponse` serves one
    from disk: inline, named, never cached (see get_case_attachment)."""
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # Same rule FileResponse applies to its own filename: plain quoting when
    # the name is ASCII-safe, RFC 5987's filename* form otherwise.
    quoted = quote(filename)
    disposition = (
        f"inline; filename*=utf-8''{quoted}" if quoted != filename else f'inline; filename="{filename}"'
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disposition, "Cache-Control": "no-store"},
    )


@app.get("/cases/{case_id}/attachments/{side}")
def get_case_attachment(case_id: str, side: str, version: Optional[int] = None) -> Response:
    """The original SI or BL file a case was read from, not just its evidence.

    An evidence snippet is deliberately short (SNIPPET_MAX in
    extract/fields.py) -- enough to confirm a value in place, not to read
    the whole document. This is the document itself, for the reviewer who
    wants more context than one line gives. Only ever the file a *run*
    read off disk: /compare holds an upload in memory and writes nothing
    (direct_compare.py's own docstring says so), so there is no case_id in
    the run_id:email_id shape this route expects and nothing to serve.

    After a re-check (POST /cases/{id}/recheck) a side may instead be the
    re-sent file, held in memory -- this serves whichever the case's current
    answer was actually reached on. `version=N` serves the file that side
    was at superseded version N (1 = the run's original answer), so the
    history a re-check leaves behind can be read against its documents.
    """
    if side not in ("si", "bl"):
        raise HTTPException(status_code=404, detail="side must be 'si' or 'bl'")
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")

    if version is None:
        resent = store.current_file(run_id, email_id, side)
    else:
        entry = store.get_version(run_id, email_id, version)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"case '{case_id}' has no superseded version {version}")
        result = entry["result"]
        resent = entry["files"].get(side)
    if resent is not None:
        return _inline_bytes(*resent)

    doc = result.si_doc if side == "si" else result.bl_doc
    if doc is None or not doc.path:
        raise HTTPException(status_code=404, detail=f"no {side} attachment on this case")
    full_path = _disk_attachment(run_id, doc.path)

    media_type = mimetypes.guess_type(full_path.name)[0] or "application/octet-stream"
    # inline, not FileResponse's own "attachment" default: docs/DATA_NOTES.md's
    # own attachment-format count is 192 .txt + 28 .pdf out of 250 total, and a
    # browser renders both of those in the tab when told "inline" -- the whole
    # point of this route is a reviewer looking at the document, not a forced
    # save-as dialog for a file they have to go find in Downloads afterward.
    # The remaining .xlsx/.docx have no in-browser renderer either way, so
    # "inline" costs those nothing next to "attachment" -- the browser's own
    # fallback for a type it can't display is to download it regardless.
    #
    # Cache-Control: no-store -- found the hard way, not added speculatively.
    # FileResponse sets last-modified/etag (set_stat_headers), which is enough
    # for a browser to cache and later revalidate a GET by default; live
    # testing during this same session hit exactly that path -- one response
    # cached from an earlier, briefer server state (this route did not exist,
    # or CORS was not yet configured, at various earlier points tonight) kept
    # being served/revalidated afterward, reproducibly failing every default-
    # mode fetch() to the same URL while curl and a cache-bypassed fetch() to
    # the identical URL always succeeded -- proof it was a stale cache entry,
    # not the route or its CORS setup. A case's underlying file can also
    # change under a retry (retry_case re-reads it from disk), which this
    # would otherwise paper over with a stale copy. There is no scenario
    # where caching this response is wanted, only ones where it silently
    # goes stale, so it is turned off outright rather than tuned.
    return FileResponse(
        full_path,
        media_type=media_type,
        filename=full_path.name,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/cases/{case_id}/review")
def review_case(case_id: str, body: ReviewRequest) -> dict:
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    if body.decision not in ("confirm", "correct"):
        raise HTTPException(status_code=422, detail="decision must be 'confirm' or 'correct'")
    # The per-field choices and corrections, when sent, must be about this
    # case's own fields, name a real side and a real choice -- anything else
    # is a client bug, and a review that silently kept it would show a case
    # page that could never be reproduced.
    known = {c.field for c in result.comparisons}
    for name, mapping in (("decisions", body.decisions), ("corrections", body.corrections)):
        unknown = sorted(f for f in (mapping or {}) if f not in known)
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"{name} names fields this case does not compare: {', '.join(unknown)}"
            )
    bad = sorted({v for v in (body.decisions or {}).values() if v not in FIELD_DECISIONS})
    if bad:
        raise HTTPException(
            status_code=422, detail=f"decisions must be one of {', '.join(FIELD_DECISIONS)}; got {', '.join(bad)}"
        )
    # A blank correction is no correction: the reviewer cleared the box.
    corrections: dict[str, dict[str, str]] = {}
    for field_name, sides in (body.corrections or {}).items():
        bad_sides = sorted(s for s in sides if s not in SIDES)
        if bad_sides:
            raise HTTPException(
                status_code=422, detail=f"corrections must name a side ({' or '.join(SIDES)}); got {', '.join(bad_sides)}"
            )
        kept = {s: v.strip() for s, v in sides.items() if isinstance(v, str) and v.strip()}
        if kept:
            corrections[field_name] = kept

    # In place, the outcome is derived here from what the reviewer did --
    # the corrected pairs compared again by the pipeline's own comparison
    # (review_outcome.py) -- never taken from the client. The whole-case
    # form (a case with nothing comparable) still sends the outcome itself.
    decisions = body.decisions or {}
    in_place = body.decisions is not None or body.corrections is not None
    if in_place and (decisions or corrections or body.cant_tell):
        derived = derive_review(result, decisions=decisions, corrections=corrections, cant_tell=body.cant_tell)
        status, defect_fields, field_verdicts = derived.status, derived.defect_fields, derived.field_verdicts
    else:
        if body.decision == "correct" and not body.status and not in_place:
            raise HTTPException(status_code=422, detail="status is required when decision is 'correct'")
        status = body.status or result.status
        defect_fields = body.defect_fields if body.defect_fields is not None else list(result.defect_fields)
        field_verdicts = {}

    return store.set_review(
        run_id,
        email_id,
        decision=body.decision,
        status=status,
        defect_fields=defect_fields,
        note=body.note,
        reviewer=body.reviewer,
        decisions=decisions,
        cant_tell=body.cant_tell,
        corrections=corrections,
        field_verdicts=field_verdicts,
    )


@app.delete("/cases/{case_id}/review")
def withdraw_review(case_id: str) -> dict:
    """Withdraw the review on a case: Sentinel's own answer stands again, and
    the case is back in the "nobody has looked" queue.

    Exists for the case page's in-place review, where each choice on a field
    card is saved as it is made: a reviewer who takes back their last choice
    has no review left to save, and what they mean is "nothing from me" --
    not a review record whose content happens to equal Sentinel's answer,
    which the list would go on tagging as reviewed. Nothing else is touched:
    the system's answer was never overwritten (store.py's effective_outcome),
    so there is nothing to restore.
    """
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    if not store.clear_review(run_id, email_id):
        raise HTTPException(status_code=404, detail=f"no review on '{case_id}' to withdraw")
    return _case_report(run_id, email_id, result)


@app.post("/cases/{case_id}/retry")
def retry_one_case(case_id: str) -> dict:
    """Re-process a single email in place.

    The problem statement asks for visible failures and retries together, and
    they belong together: a case that shows `errors` or an `unreadable` reason
    is exactly the one a reviewer wants to run again after the sender re-sends
    a readable attachment. Re-running the whole inbox to find out is minutes of
    work and a different run_id from the one they were looking at.

    The email is re-read from disk, so a replaced attachment is picked up. The
    case keeps its position in the run and `processed` does not double-count.
    Any review recorded against it is deliberately left alone — the new result
    is the system's answer, and whether it still needs the reviewer's
    correction is the reviewer's call, not ours.
    """
    run_id, email_id = _split_case_id(case_id)
    if store.get_case(run_id, email_id) is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    # A retry re-reads the inbox on disk. Once a case has been re-checked on
    # re-sent documents, the disk copy is precisely the version the desk has
    # moved past -- a retry here would quietly reinstate it over the re-sent
    # one, and leave no history of having done so. Refused rather than
    # reinterpreted: the re-check route is the one that runs this case again.
    if store.recheck_count(run_id, email_id):
        raise HTTPException(
            status_code=409,
            detail="this case has been re-checked on amended documents; reprocessing would "
                   "re-read the run's original files over them. Re-check it again instead.",
        )

    try:
        result = retry_case(store, run_id, email_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    return _case_report(run_id, email_id, result)


def _safe_filename(raw: Optional[str], side: str) -> str:
    """The uploaded name as a bare file name -- it is echoed in a
    Content-Disposition header and shown in the report, never used as a
    path, so a directory prefix or a quote in it has no business surviving."""
    name = Path(raw or "").name
    name = "".join(ch for ch in name if ch not in '"\r\n')
    return name or f"resent_{side}"


@app.post("/cases/{case_id}/recheck")
async def recheck_one_case(
    case_id: str,
    si: Optional[UploadFile] = File(None, description="the re-sent Shipping Instruction"),
    bl: Optional[UploadFile] = File(None, description="the re-sent draft Bill of Lading"),
) -> dict:
    """Run the check again on documents the counterparty re-sent.

    The realistic follow-up to a MISMATCH or an unreadable attachment is not
    a correction typed into a form: someone emails the shipper, a corrected
    BL comes back, and the desk wants the same check run on what came back.
    `retry` cannot do that -- it re-reads the run's own inbox -- and
    `/compare` can, but stores nothing and knows no case. This does both:
    the same comparison `/compare` runs, stored against this case.

    One side or both. A side not re-sent keeps the file the case already
    has (its disk original, or the copy from an earlier re-check). The
    answer this replaces goes into the case's history together with any
    review that stood against it, and the review is reset: it was a
    judgement about the old documents, not these. The email's category is
    kept as the run decided it -- re-sent documents change what the
    documents say, not what kind of email asked for them -- which is also
    why a case that is not a BL_COMPARISON has nothing here to re-check.
    """
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    if result.category != "BL_COMPARISON":
        raise HTTPException(
            status_code=409,
            detail=f"this email was classified {result.category}, which has no SI/BL "
                   f"pair to compare; there is nothing to re-check.",
        )
    if si is None and bl is None:
        raise HTTPException(status_code=422, detail="attach the amended SI, the amended BL, or both")
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run '{run_id}'")

    uploaded: dict[str, tuple[str, bytes]] = {}
    for side, upload in (("si", si), ("bl", bl)):
        if upload is None:
            continue
        data = await upload.read()
        # An empty upload is a slip, not a document: `/compare` lets one
        # through as NEEDS_REVIEW because it stores nothing, but here it
        # would push a real answer into history under a blank one.
        if not data:
            raise HTTPException(status_code=422, detail=f"the amended {side.upper()} is empty (0 bytes)")
        if len(data) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"the amended {side.upper()} is {len(data)} bytes, above the {MAX_BYTES} limit",
            )
        uploaded[side] = (_safe_filename(upload.filename, side), data)

    inputs: dict[str, tuple[str, bytes]] = {}
    for side in ("si", "bl"):
        if side in uploaded:
            inputs[side] = uploaded[side]
            continue
        current = store.current_file(run_id, email_id, side)
        if current is not None:
            inputs[side] = current
            continue
        doc = result.si_doc if side == "si" else result.bl_doc
        if doc is None or not doc.path:
            raise HTTPException(
                status_code=422,
                detail=f"this case has no {side.upper()} on file to compare against; attach it as well",
            )
        # The relative path stays as the file name on purpose: read_upload
        # keeps it as the document's `path`, which is what the attachment
        # route resolves under the data root for a side still read from disk.
        inputs[side] = (doc.path, _disk_attachment(run_id, doc.path).read_bytes())

    # Same rule `retry_case` applies: the model is offered exactly when the
    # run it belongs to was allowed it, never because a re-check asked.
    #
    # The SHARED client, not a fresh one -- for the reason written out ninety
    # lines below, where the same mistake was found and fixed for /compare:
    # SENTINEL_RUN_BUDGET_USD lives on the client's own usage counter, so a new
    # client per request resets the ceiling every time and bounds nothing. This
    # route is public, unauthenticated and takes uploads, and `render.yaml` now
    # sets SENTINEL_ALLOW_LLM_RUNS=1, so an unshared client here is an
    # unbounded spend path. `build_client(enabled=False)` returns None and so
    # does `_shared_compare_client()` with no key configured, so the
    # model-disabled behaviour is unchanged.
    client = _shared_compare_client() if run.llm_enabled else None
    fresh = compare_uploads(*inputs["si"], *inputs["bl"], llm=client)
    # What the run decided about the *email* is carried over untouched;
    # only what the documents say has changed. `decided_by` is left as the
    # comparison set it -- which tier answered this time is its own fact.
    fresh.email_id = result.email_id
    fresh.sender = result.sender
    fresh.subject = result.subject
    fresh.category = result.category
    fresh.category_confidence = result.category_confidence
    fresh.category_rationale = list(result.category_rationale)
    store.recheck_case(run_id, fresh, uploaded=uploaded)
    return _case_report(run_id, email_id, fresh)


@app.get("/metrics")
def metrics(run_id: Optional[str] = None) -> dict:
    rec = _run_or_404(run_id) if run_id else store.latest_done_run()
    if rec is None:
        raise HTTPException(status_code=404, detail="no completed run yet")
    if rec.metrics is None:
        raise HTTPException(status_code=409, detail=f"run '{rec.run_id}' has not finished")
    # The pipeline's own numbers are left exactly as the run produced them —
    # they are what Sentinel did, and a human confirming a case afterwards
    # must not retro-improve them. What humans did is reported beside them.
    return {"run_id": rec.run_id, **rec.metrics,
            "review": store.review_summary(rec.run_id),
            "recheck": store.recheck_summary(rec.run_id)}


@app.get("/runs/{run_id}/patterns")
def patterns(run_id: str) -> dict:
    """What is wrong across the whole inbox, rather than in one case.

    Answers while a run is still going, on whatever has finished — unlike
    `/metrics` and `/submission`, which refuse a partial run because a partial
    *submission* is a wrong answer to the scorer. A partial aggregation is not
    wrong, it is early, and the page says how many cases it is drawn from.
    """
    rec = _run_or_404(run_id)
    cases = store.list_cases(run_id)
    senders = {c.email_id: store.sender_of(run_id, c.email_id) for c in cases}
    return {
        "run_id": rec.run_id,
        "run_status": rec.status,
        "cases_counted": len(cases),
        "total_emails": rec.total_emails,
        **summarise_patterns(cases, senders),
    }


@app.get("/submission")
def submission(run_id: Optional[str] = None) -> dict:
    """The graded artefact — every email_id, in the scorer's shape.

    Guarded the same way `/metrics` is, and for a sharper reason. Mid-run this
    used to answer HTTP 200 with however many emails happened to be finished:
    207 keys, then 407 on a refresh. The official scorer counts a missing
    email_id as a wrong answer rather than skipping it, so a partial file that
    looks complete does not score slightly lower — it scores wrong, and
    nothing about the response says so.
    """
    rec = _run_or_404(run_id) if run_id else store.latest_done_run()
    if rec is None:
        raise HTTPException(status_code=404, detail="no completed run yet")
    if rec.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"run '{rec.run_id}' is {rec.status} "
                   f"({rec.processed}/{rec.total_emails}); a partial submission "
                   f"would score as wrong answers, not as fewer answers.",
        )
    out = {}
    for c in store.list_cases(rec.run_id):
        # A reviewer's correction is the answer that ships. The submission is
        # what the desk stands behind, not a record of what the machine
        # thought before a person looked at it — `GET /cases/{id}` keeps that.
        eff = store.effective_outcome(rec.run_id, c)
        out[c.email_id] = {
            "category": c.category,
            "status": eff["status"],
            "review_reason": eff["review_reason"],
            "defect_fields": eff["defect_fields"],
            "has_defect": eff["has_defect"],
            "decided_by": c.decided_by,
        }
    return out


# One client for every model-enabled upload, for the life of the process.
#
# `build_client()` per request looked harmless and was not: the run budget
# (SENTINEL_RUN_BUDGET_USD) lives on the client's own usage counter, so a fresh
# client per call meant the ceiling reset every time and bounded nothing. On a
# public, unauthenticated endpoint with a visible "use the model" switch, that
# is an invitation to spend the key one upload at a time. Sharing the client
# makes the ceiling cumulative, which is what a ceiling is for — and it shares
# the response cache too, so a judge pressing the button twice on the same
# document pays once.
_compare_client = None
_compare_client_built = False


def _shared_compare_client():
    global _compare_client, _compare_client_built
    if not _compare_client_built:
        _compare_client = build_client(enabled=True)
        _compare_client_built = True
    return _compare_client


def _model_available() -> bool:
    """Whether the shared client exists, without ever raising.

    `build_client` reads the model settings, and `load_settings` raises on a
    model with no pinned price or a malformed budget. That is right for the
    routes that would spend money, and wrong for `GET /`, which Render polls
    as its health check: a typo in one environment variable would otherwise
    fail every health check and restart the whole service.
    """
    try:
        client = _shared_compare_client()
    except Exception:
        return False
    return client is not None and client.available


@app.post("/reply-drafts/polish")
def polish_reply_draft(body: PolishRequest) -> dict:
    """Reword a reply draft's greeting and closing, and nothing else.

    The request has no field for the draft's context, facts or action: those
    never leave the browser, so the model is not shown a single case value
    (backend/api/reply_polish.py). Not gated behind SENTINEL_ALLOW_LLM_RUNS
    for the same reason `/compare` is not: it is one small call, it draws on
    the same shared, budgeted client, and an identical request is answered
    from the response cache for nothing.

    503 when no model is configured or it cannot be reached; the page keeps
    the template's own wording either way.
    """
    try:
        client = _shared_compare_client()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"the model settings are invalid ({exc}); the template wording stands")
    if client is None or not client.available:
        raise HTTPException(status_code=503, detail="no model is available on this server; the template wording stands")
    try:
        return polish_reply(body, client).model_dump()
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"the model could not be reached ({exc}); the template wording stands")


@app.post("/compare")
async def compare(
    si: UploadFile = File(..., description="Shipping Instruction"),
    bl: UploadFile = File(..., description="draft Bill of Lading"),
    use_llm: bool = False,
) -> dict:
    """Compare two uploaded documents. Nothing is stored.

    `use_llm` is the switch the dashboard exposes, and it is the point of this
    endpoint: run the same pair twice, once each way, and the difference shows
    where the model actually sits in this system. Unlike `POST /runs` it is not
    gated behind SENTINEL_ALLOW_LLM_RUNS — one document pair is bounded work,
    where a model-enabled run is the whole inbox — but it draws on a shared,
    budgeted client so the spend is bounded across requests as well as within
    one.
    """
    si_bytes = await si.read()
    bl_bytes = await bl.read()
    client = _shared_compare_client() if use_llm else None
    result = compare_uploads(si.filename or "si", si_bytes, bl.filename or "bl", bl_bytes, llm=client)

    report = result.to_report()
    # So the page can say which tier answered rather than the reader guessing
    # from the extractor tags.
    report["model_used"] = bool(client) and any(
        side and side.get("extractor") == "llm"
        for f in report["fields"] for side in (f.get("si"), f.get("bl"))
    )
    report["model_offered"] = bool(client)
    return report
