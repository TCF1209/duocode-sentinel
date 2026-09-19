"""In-memory run/case storage for the API.

ARCHITECTURE.md's deployment diagram plans a managed Postgres for runs, cases
and review actions. There is no database yet, so this is that store for now —
a single process's memory, gone on restart. Every route talks to it only
through this class, so replacing it with Postgres later is a one-file change,
not a rewrite of the routes.
"""
from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from sdoc.schema import CaseResult


@dataclass
class RunRecord:
    run_id: str
    status: str = "running"          # running | done | failed
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    total_emails: int = 0
    processed: int = 0
    error: Optional[str] = None
    metrics: Optional[dict] = None
    llm_enabled: bool = False
    data_root: str = ""


class Store:
    """Thread-safe in-memory store. A background thread writes; routes read."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}
        self._cases: dict[str, dict[str, CaseResult]] = {}
        self._order: dict[str, list[str]] = {}
        self._reviews: dict[str, dict[str, dict]] = {}
        self._counter = itertools.count(1)

    def new_run_id(self) -> str:
        return f"run_{next(self._counter):06d}_{int(time.time())}"

    def create_run(self, run_id: str, *, total_emails: int, llm_enabled: bool, data_root: str) -> RunRecord:
        rec = RunRecord(run_id=run_id, total_emails=total_emails, llm_enabled=llm_enabled, data_root=data_root)
        with self._lock:
            self._runs[run_id] = rec
            self._cases[run_id] = {}
            self._order[run_id] = []
        return rec

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)

    def add_case(self, run_id: str, result: CaseResult) -> None:
        with self._lock:
            self._cases[run_id][result.email_id] = result
            self._order[run_id].append(result.email_id)
            self._runs[run_id].processed += 1

    def get_case(self, run_id: str, email_id: str) -> Optional[CaseResult]:
        with self._lock:
            return self._cases.get(run_id, {}).get(email_id)

    def list_cases(self, run_id: str) -> list[CaseResult]:
        with self._lock:
            order = self._order.get(run_id, [])
            cases = self._cases.get(run_id, {})
            return [cases[eid] for eid in order if eid in cases]

    def finish_run(self, run_id: str, *, metrics: dict) -> None:
        with self._lock:
            rec = self._runs[run_id]
            rec.status = "done"
            rec.finished_at = time.time()
            rec.metrics = metrics

    def fail_run(self, run_id: str, *, error: str) -> None:
        with self._lock:
            rec = self._runs[run_id]
            rec.status = "failed"
            rec.finished_at = time.time()
            rec.error = error

    def latest_done_run(self) -> Optional[RunRecord]:
        with self._lock:
            done = [r for r in self._runs.values() if r.status == "done"]
        return max(done, key=lambda r: r.finished_at or 0) if done else None

    def set_review(
        self, run_id: str, email_id: str, *, decision: str, status: str,
        defect_fields: list[str], note: Optional[str], reviewer: Optional[str],
    ) -> dict:
        review = {
            "decision": decision,
            "status": status,
            "defect_fields": sorted(defect_fields),
            "note": note,
            "reviewer": reviewer,
            "reviewed_at": time.time(),
        }
        with self._lock:
            self._reviews.setdefault(run_id, {})[email_id] = review
        return review

    def get_review(self, run_id: str, email_id: str) -> Optional[dict]:
        with self._lock:
            return self._reviews.get(run_id, {}).get(email_id)


# One process-wide store. Fine for a single-instance hackathon deployment;
# a multi-instance deploy would need the Postgres swap noted above.
store = Store()
