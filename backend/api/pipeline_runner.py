"""Runs the pipeline over a bundled inbox in a background thread.

This is `backend/run.py`'s own `load_emails` plus `Pipeline.process`, called
per email instead of in one batch, so `GET /runs/{id}/cases` can show partial
progress while a run is still going. No pipeline logic is reimplemented here.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from sdoc.pipeline import Pipeline, PipelineConfig, build_client
from sdoc.schema import EmailRecord

from .store import Store


def load_emails(data_root: Path, limit: Optional[int] = None) -> list[EmailRecord]:
    inbox = data_root / "inbox"
    if not inbox.is_dir():
        raise FileNotFoundError(
            f"No inbox at {inbox}. Put the participant bundle at {data_root} "
            f"(see docs/SCORING.md) or point SENTINEL_DATA_ROOT elsewhere."
        )
    paths = sorted(inbox.glob("email_*.json"))
    if limit:
        paths = paths[:limit]
    return [EmailRecord.from_json(json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def start_run(store: Store, *, data_root: Path, limit: Optional[int], use_llm: bool) -> str:
    """Validate synchronously (so a bad data root is a 400, not a run that
    immediately fails), then process the inbox on a background thread."""
    emails = load_emails(data_root, limit)
    run_id = store.new_run_id()
    store.create_run(run_id, total_emails=len(emails), llm_enabled=use_llm, data_root=str(data_root))

    thread = threading.Thread(
        target=_execute, args=(store, run_id, emails, data_root, use_llm), daemon=True,
    )
    thread.start()
    return run_id


def retry_case(store: Store, run_id: str, email_id: str):
    """Re-process one email without re-running the inbox.

    The problem statement asks for visible failures *and* retries. A run of
    520 emails that stumbled on one of them should not have to be repeated in
    full — that is minutes of work and a new run_id for a reviewer who was
    looking at this one case.

    The email is re-read from the run's own data root rather than kept in
    memory, so a retry picks up a file that has since been replaced — which is
    the realistic reason to press it: the sender re-sent a readable copy of the
    attachment that came through corrupt.

    Runs synchronously. One email is milliseconds on the deterministic path,
    and a caller who pressed "retry" is waiting for this specific answer.
    """
    rec = store.get_run(run_id)
    if rec is None:
        raise KeyError(f"no run '{run_id}'")

    data_root = Path(rec.data_root)
    path = data_root / "inbox" / f"{email_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no email '{email_id}' under {data_root / 'inbox'}")

    email = EmailRecord.from_json(json.loads(path.read_text(encoding="utf-8")))
    client = build_client(enabled=rec.llm_enabled)
    pipeline = Pipeline(PipelineConfig(data_root=data_root, llm=client))
    result = pipeline.process(email)          # Pipeline.process never raises
    store.replace_case(run_id, result)
    return result


def _execute(
    store: Store, run_id: str, emails: list[EmailRecord], data_root: Path, use_llm: bool,
) -> None:
    try:
        client = build_client(enabled=use_llm)
        pipeline = Pipeline(PipelineConfig(data_root=data_root, llm=client))
        for email in emails:
            result = pipeline.process(email)          # Pipeline.process never raises
            store.add_case(run_id, result)
        metrics = pipeline.stats.to_dict()
        metrics["llm"] = client.stats() if client else {"available": False}
        store.finish_run(run_id, metrics=metrics)
    except Exception as exc:            # a run-level failure must still be visible, not silent
        store.fail_run(run_id, error=f"{type(exc).__name__}: {exc}")
