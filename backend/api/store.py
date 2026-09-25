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
        # Superseded answers, oldest first, per case -- written only by
        # `recheck_case` below. `retry` overwrites in place and always has;
        # a re-check with re-sent documents is the one replacement where the
        # old answer is worth keeping, because it was reached on different
        # documents and a reviewer may need to see what the desk said about
        # the first version of the BL.
        self._history: dict[str, dict[str, list[dict]]] = {}
        # The re-sent files themselves, per case and side: (filename, bytes).
        # A run's own attachments live on disk under its data root; a re-sent
        # one never touches disk (the data root is the organisers' bundle,
        # not ours to write into), so the attachment route reads it from here.
        self._files: dict[str, dict[str, dict[str, tuple[str, bytes]]]] = {}
        # Who sent each email, kept beside the case rather than on it.
        # `CaseResult` is a `backend/sdoc/` type and the official scorer reads
        # what it serialises, so the sender -- which no pipeline stage needs and
        # the submission format has no field for -- lives here in the API layer
        # instead. `/runs/{id}/patterns` is the only consumer.
        # (Merged from main: this branch also carries `CaseResult.sender`,
        # set by the pipeline for the case list and re-checks -- two homes
        # for one value; reconciling them is noted in docs/STATUS.md.)
        self._senders: dict[str, dict[str, str]] = {}
        # The inbox record's own subject line and attachment names, per
        # case -- what a person saw before Sentinel touched the email. The
        # dashboard's "Before Sentinel" view (docs/PITCH_DAY.md, the mentor
        # session of 24 Sep) shows the inbox as it arrived, and nothing in
        # CaseResult carries these: they are not pipeline outputs and not
        # part of the submission, so they live here in the API layer like
        # the sender does.
        self._inbox: dict[str, dict[str, dict]] = {}
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

    def add_case(
        self, run_id: str, result: CaseResult, *, sender: str = "",
        subject: str = "", attachments: Optional[list[str]] = None,
    ) -> None:
        with self._lock:
            self._cases[run_id][result.email_id] = result
            self._order[run_id].append(result.email_id)
            self._runs[run_id].processed += 1
            if sender:
                self._senders.setdefault(run_id, {})[result.email_id] = sender
            self._inbox.setdefault(run_id, {})[result.email_id] = {
                "subject": subject,
                "attachments": list(attachments or []),
            }

    def inbox_of(self, run_id: str, email_id: str) -> dict:
        """The email as it arrived: subject and attachment names. Empty
        strings/lists for a case this store never saw an inbox record for."""
        with self._lock:
            rec = self._inbox.get(run_id, {}).get(email_id)
        return {"subject": rec["subject"], "attachments": list(rec["attachments"])} if rec else {"subject": "", "attachments": []}

    def sender_of(self, run_id: str, email_id: str) -> str:
        """Empty string when unknown -- a run started before this existed, or
        an inbox record with no `from`. Patterns groups those under one bucket
        rather than dropping the case."""
        with self._lock:
            return self._senders.get(run_id, {}).get(email_id, "")

    def get_case(self, run_id: str, email_id: str) -> Optional[CaseResult]:
        with self._lock:
            return self._cases.get(run_id, {}).get(email_id)

    def replace_case(self, run_id: str, result: CaseResult) -> None:
        """Overwrite one case after a retry, keeping its place in the order.

        Distinct from `add_case`, which appends and increments `processed`.
        Retrying an email that has already been counted must not count it
        twice, and must not move it to the bottom of the operator's list.
        """
        with self._lock:
            self._cases[run_id][result.email_id] = result
            if result.email_id not in self._order[run_id]:
                self._order[run_id].append(result.email_id)
                self._runs[run_id].processed += 1

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
        decisions: Optional[dict[str, str]] = None, cant_tell: bool = False,
        corrections: Optional[dict[str, dict[str, str]]] = None,
        field_verdicts: Optional[dict[str, dict]] = None,
    ) -> dict:
        review = {
            "decision": decision,
            "status": status,
            "defect_fields": sorted(defect_fields),
            "note": note,
            "reviewer": reviewer,
            "reviewed_at": time.time(),
            # The per-field choices and corrected values the outcome above
            # was built from (models.py's ReviewRequest), kept verbatim so
            # the case page can show the review as it was made, and the
            # per-field verdicts the corrected pairs got (review_outcome.py).
            # All empty for a whole-case review.
            "decisions": dict(decisions or {}),
            "cant_tell": bool(cant_tell),
            "corrections": {f: dict(sides) for f, sides in (corrections or {}).items() if sides},
            "field_verdicts": dict(field_verdicts or {}),
        }
        with self._lock:
            self._reviews.setdefault(run_id, {})[email_id] = review
        return review

    def get_review(self, run_id: str, email_id: str) -> Optional[dict]:
        with self._lock:
            return self._reviews.get(run_id, {}).get(email_id)

    def clear_review(self, run_id: str, email_id: str) -> bool:
        """Withdraw a review: the case is unreviewed again and Sentinel's own
        answer stands. The review is dropped, not kept as history -- it was
        a person's decision *about the current answer*, and they have taken
        it back; a re-check (below) is the one thing that supersedes a review
        and keeps it, because there the answer itself changed under it.
        Returns False when there was nothing to withdraw."""
        with self._lock:
            return self._reviews.get(run_id, {}).pop(email_id, None) is not None

    # -- what the case is NOW -------------------------------------------
    #
    # The problem statement asks that a reviewer be able to "confirm or
    # correct it, then update the report". The obvious way to do that is to
    # overwrite the CaseResult, and it is the wrong way: it destroys the
    # distinction between what Sentinel decided and what a person decided,
    # which is the one thing an audit trail exists to keep. It would also
    # quietly flatter our own accuracy — a corrected case would look like a
    # case we got right.
    #
    # So the system's answer is immutable and the review sits beside it.
    # Everything that reports an outcome — the case list, the submission,
    # the metrics — asks this method instead of reading `result.status`
    # directly, and the answer carries `source` so a reader can always see
    # which of the two they are looking at.
    def effective_outcome(self, run_id: str, result: CaseResult) -> dict:
        return self._effective(result, self.get_review(run_id, result.email_id))

    @staticmethod
    def _effective(result: CaseResult, review: Optional[dict]) -> dict:
        """`effective_outcome` with the review passed in, so a superseded
        version in `_history` (whose review is no longer in `_reviews`) can
        be reported the same way the live case is."""
        system = {
            "status": result.status,
            "review_reason": result.review_reason,
            "has_defect": result.has_defect,
            "defect_fields": sorted(result.defect_fields),
        }
        if review is None:
            return {**system, "source": "system", "reviewed": False,
                    "review_decision": None}

        # `confirm` signs the system's answer off without changing it. That is
        # not a no-op — it is the difference between "nobody has looked" and
        # "a person looked and agreed", which is what a review queue is for.
        if review.get("decision") != "correct":
            return {**system, "source": "system", "reviewed": True,
                    "review_decision": review.get("decision")}

        status = review.get("status") or result.status
        fields = sorted(review.get("defect_fields") or [])
        # Derived, never taken from the request: the submission shape requires
        # has_defect and defect_fields to agree with status, and a reviewer
        # correcting a status should not have to know that rule.
        if status == "MISMATCH":
            has_defect, defect_fields = True, fields
        else:
            has_defect, defect_fields = False, []
        reason = result.review_reason if status == "NEEDS_REVIEW" else None

        return {
            "status": status,
            "review_reason": reason,
            "has_defect": has_defect,
            "defect_fields": defect_fields,
            "source": "review",
            "reviewed": True,
            "review_decision": "correct",
        }

    def review_summary(self, run_id: str) -> dict:
        """Counts for the metrics page's "Reviewer decisions" tiles.

        Every review is exactly one of three: `confirmed` (the reviewer
        confirmed the Sentinel result), `unresolved` (a correction whose
        outcome is still NEEDS_REVIEW -- the reviewer could not decide, so the
        case stays escalated) or `corrected` (any other correction -- the
        reviewer overrode the Sentinel result; shown as "Overridden").
        `unresolved` is additive: the earlier keys are kept for old clients.
        """
        with self._lock:
            reviews = list(self._reviews.get(run_id, {}).values())
        corrections = [r for r in reviews if r.get("decision") == "correct"]
        unresolved = sum(1 for r in corrections if r.get("status") == "NEEDS_REVIEW")
        return {
            "reviewed": len(reviews),
            "confirmed": len(reviews) - len(corrections),
            "corrected": len(corrections) - unresolved,
            "unresolved": unresolved,
        }

    # -- re-checking a case on re-sent documents -------------------------
    #
    # The realistic follow-up to a MISMATCH or a NEEDS_REVIEW is not a
    # correction typed into a form: it is the counterparty re-sending the
    # document, and the desk wanting the same check run again on what came
    # back. `retry` cannot do that -- it re-reads the run's own inbox from
    # disk -- and `/compare` can, but stores nothing and knows no case.
    #
    # A re-check replaces the case's system answer the way a retry does, with
    # two differences that are the whole point. The answer it replaces goes
    # into `_history` together with whatever review stood against it, so
    # "Sentinel said MISMATCH on the first BL, a reviewer confirmed it, then
    # the shipper sent a second BL that matched" stays readable in that
    # order. And the review itself is reset: it was a judgement about the old
    # documents, and carrying it forward onto documents it never looked at
    # would put a person's signature on something they did not sign.
    def recheck_case(
        self, run_id: str, result: CaseResult, *, uploaded: dict[str, tuple[str, bytes]],
    ) -> dict:
        """Replace one case with `result`, keeping the superseded answer.

        `uploaded` maps the re-sent side(s) ("si"/"bl") to (filename, bytes).
        A side not in it keeps whatever file the case already had -- the
        disk original, or an earlier re-sent copy -- which is exactly what
        the caller compared against, so the served attachment and the
        reported answer never disagree.
        """
        email_id = result.email_id
        with self._lock:
            previous = self._cases[run_id][email_id]
            files_before = dict(self._files.get(run_id, {}).get(email_id, {}))
            history = self._history.setdefault(run_id, {}).setdefault(email_id, [])
            entry = {
                "version": len(history) + 1,
                "result": previous,
                "review": self._reviews.get(run_id, {}).pop(email_id, None),
                # What the case's files were while `previous` stood; a side
                # absent here was the disk original, at previous.<side>_doc.path.
                "files": files_before,
                "replaced_at": time.time(),
                "resubmitted": sorted(uploaded),
                "uploaded": {side: name for side, (name, _) in uploaded.items()},
            }
            history.append(entry)
            self._cases[run_id][email_id] = result
            self._files.setdefault(run_id, {}).setdefault(email_id, {}).update(uploaded)
        return self._history_entry_view(entry)

    def current_file(self, run_id: str, email_id: str, side: str) -> Optional[tuple[str, bytes]]:
        """The re-sent file standing in for this side, or None: the case
        still reads that side from the run's data root."""
        with self._lock:
            return self._files.get(run_id, {}).get(email_id, {}).get(side)

    def recheck_count(self, run_id: str, email_id: str) -> int:
        with self._lock:
            return len(self._history.get(run_id, {}).get(email_id, []))

    def get_version(self, run_id: str, email_id: str, version: int) -> Optional[dict]:
        """One superseded version, 1 being the run's original answer. The
        raw entry (CaseResult and bytes included) -- for the attachment
        route; `get_history` is the JSON-shaped view."""
        with self._lock:
            history = self._history.get(run_id, {}).get(email_id, [])
            if 1 <= version <= len(history):
                return history[version - 1]
            return None

    def get_history(self, run_id: str, email_id: str) -> list[dict]:
        with self._lock:
            history = list(self._history.get(run_id, {}).get(email_id, []))
        return [self._history_entry_view(e) for e in history]

    def recheck_info(self, run_id: str, email_id: str, result: CaseResult) -> Optional[dict]:
        """What the case detail says about its re-checks, or None when there
        were none -- so an unchanged case's report is byte-for-byte what it
        was before this feature existed, plus one null key."""
        with self._lock:
            history = list(self._history.get(run_id, {}).get(email_id, []))
            files = dict(self._files.get(run_id, {}).get(email_id, {}))
        if not history:
            return None
        last = history[-1]
        return {
            "count": len(history),
            "last_at": last["replaced_at"],
            "last_resubmitted": last["resubmitted"],
            # Which file each side is currently read from -- "resent" is
            # served from memory by the attachment route, "original" from
            # the run's data root. A side with no document at all (the case
            # never had a BL and none was re-sent) is reported as None.
            "sources": {
                side: (
                    "resent" if side in files
                    else "original" if getattr(result, f"{side}_doc") is not None
                    else None
                )
                for side in ("si", "bl")
            },
        }

    def recheck_summary(self, run_id: str) -> dict:
        """Counts for the metrics page, beside `review_summary`."""
        with self._lock:
            per_case = list(self._history.get(run_id, {}).values())
        return {
            "cases": sum(1 for h in per_case if h),
            "rechecks": sum(len(h) for h in per_case),
        }

    def _history_entry_view(self, entry: dict) -> dict:
        result: CaseResult = entry["result"]
        return {
            "version": entry["version"],
            "replaced_at": entry["replaced_at"],
            "resubmitted": entry["resubmitted"],
            "uploaded": entry["uploaded"],
            "report": result.to_report(),
            "review": entry["review"],
            "effective": self._effective(result, entry["review"]),
        }


# One process-wide store. Fine for a single-instance hackathon deployment;
# a multi-instance deploy would need the Postgres swap noted above.
store = Store()
