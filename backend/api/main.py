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

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sdoc.pipeline import build_client  # noqa: E402

from .direct_compare import compare_uploads  # noqa: E402
from .models import (  # noqa: E402
    ReviewRequest,
    RunCreateRequest,
    RunCreateResponse,
    RunStatusResponse,
)
from .pipeline_runner import start_run  # noqa: E402
from .store import store  # noqa: E402

DEFAULT_DATA_ROOT = Path(os.environ.get("SENTINEL_DATA_ROOT", str(BACKEND.parent / "data" / "bundle")))
_cors_env = os.environ.get("SENTINEL_CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]

app = FastAPI(
    title="Sentinel API",
    description="Shipping document verification — Averis x Monash Hackathon 2026",
    version="0.1.0",
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
    return {"service": "sentinel-api", "status": "ok"}


@app.post("/runs", response_model=RunCreateResponse)
def create_run(body: Optional[RunCreateRequest] = None) -> RunCreateResponse:
    """Start a run over the bundled demo inbox at SENTINEL_DATA_ROOT."""
    body = body or RunCreateRequest()
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
        if category and c.category != category:
            continue
        if status and c.status != status:
            continue
        if decided_by and c.decided_by != decided_by:
            continue
        out.append({
            "case_id": f"{run_id}:{c.email_id}",
            "email_id": c.email_id,
            "category": c.category,
            "category_confidence": round(c.category_confidence, 3),
            "status": c.status,
            "review_reason": c.review_reason,
            "has_defect": c.has_defect,
            "defect_fields": sorted(c.defect_fields),
            "decided_by": c.decided_by,
        })
    return {"run_id": run_id, "count": len(out), "cases": out}


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    report = result.to_report()
    report["review"] = store.get_review(run_id, email_id)
    return report


@app.post("/cases/{case_id}/review")
def review_case(case_id: str, body: ReviewRequest) -> dict:
    run_id, email_id = _split_case_id(case_id)
    result = store.get_case(run_id, email_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no case '{case_id}'")
    if body.decision not in ("confirm", "correct"):
        raise HTTPException(status_code=422, detail="decision must be 'confirm' or 'correct'")
    if body.decision == "correct" and not body.status:
        raise HTTPException(status_code=422, detail="status is required when decision is 'correct'")

    return store.set_review(
        run_id,
        email_id,
        decision=body.decision,
        status=body.status or result.status,
        defect_fields=(
            body.defect_fields if body.defect_fields is not None else list(result.defect_fields)
        ),
        note=body.note,
        reviewer=body.reviewer,
    )


@app.get("/metrics")
def metrics(run_id: Optional[str] = None) -> dict:
    rec = _run_or_404(run_id) if run_id else store.latest_done_run()
    if rec is None:
        raise HTTPException(status_code=404, detail="no completed run yet")
    if rec.metrics is None:
        raise HTTPException(status_code=409, detail=f"run '{rec.run_id}' has not finished")
    return {"run_id": rec.run_id, **rec.metrics}


@app.get("/submission")
def submission(run_id: Optional[str] = None) -> dict:
    rec = _run_or_404(run_id) if run_id else store.latest_done_run()
    if rec is None:
        raise HTTPException(status_code=404, detail="no completed run yet")
    return {c.email_id: c.to_submission() for c in store.list_cases(rec.run_id)}


@app.post("/compare")
async def compare(
    si: UploadFile = File(..., description="Shipping Instruction"),
    bl: UploadFile = File(..., description="draft Bill of Lading"),
    use_llm: bool = False,
) -> dict:
    si_bytes = await si.read()
    bl_bytes = await bl.read()
    client = build_client(enabled=use_llm)
    result = compare_uploads(si.filename or "si", si_bytes, bl.filename or "bl", bl_bytes, llm=client)
    return result.to_report()
