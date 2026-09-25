"""Pydantic models — the API boundary only.

`backend/sdoc` stays plain dataclasses (see schema.py's own docstring); nothing
in there imports pydantic. These models exist to validate what crosses the
HTTP boundary, not to re-describe the pipeline's internal shapes.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    # `gt=0` rather than a bare int: `limit: -5` used to reach
    # `paths[:limit]` and silently drop the LAST five emails, returning a
    # 515-email "submission" with HTTP 200. A partial submission that looks
    # complete is worse than a rejected request.
    limit: Optional[int] = Field(
        default=None, gt=0, description="Process only the first N emails"
    )
    # Defaults to OFF. This endpoint is public and unauthenticated on the
    # deployed demo, and an empty `POST /runs` body used to start a
    # model-enabled run over the whole inbox — anyone who found the URL could
    # spend the team's OpenAI key by holding down a button. Turning it on is
    # now a deliberate act by the caller AND requires the server to allow it
    # (SENTINEL_ALLOW_LLM_RUNS, see main.py). The deterministic path answers
    # 100% of the graded inbox anyway, so the default costs the demo nothing.
    use_llm: bool = Field(
        default=False, description="Allow the model fallback when a key is configured"
    )


class RunCreateResponse(BaseModel):
    run_id: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str                       # running | done | failed
    total_emails: int
    processed: int
    llm_enabled: bool
    error: Optional[str] = None
    metrics: Optional[dict] = None


class ReviewRequest(BaseModel):
    decision: str = Field(description="'confirm' the system's outcome, or 'correct' it")
    status: Optional[str] = Field(
        default=None, description="Required when decision == 'correct': OK | MISMATCH | NEEDS_REVIEW"
    )
    defect_fields: Optional[list[str]] = None
    note: Optional[str] = None
    reviewer: Optional[str] = None
    # The choices behind `status` / `defect_fields`, one per field the
    # reviewer touched: "cleared" (Sentinel's mismatch taken off the list),
    # "flagged" (a field Sentinel passed or could not compare, added to it),
    # "fine" (an uncomparable field the reviewer has read both sides of and
    # is satisfied with). `status` and `defect_fields` stay the outcome the
    # submission reports -- these only let the case page show a saved review
    # exactly as it was made, choice by choice, so it can be changed one
    # choice at a time. Optional: a review without them is a whole-case
    # decision, as every review was before they existed.
    decisions: Optional[dict[str, str]] = Field(
        default=None, description="Per field: cleared | flagged | fine"
    )
    # "I can't tell": the whole case goes to NEEDS_REVIEW whatever the
    # per-field choices say.
    cant_tell: bool = False
    # Per field, the value the reviewer says a side reads ("the shipper
    # confirmed the BL consignee is EAST BRIGHT FZ-LLC"): {"consignee":
    # {"bl": "EAST BRIGHT FZ-LLC"}}. The corrected pair is compared again by
    # the pipeline's own comparison (review_outcome.py) and the outcome
    # follows; the run's own reading is kept beside it. When `decisions` or
    # `corrections` is sent, `status` / `defect_fields` are derived from
    # them and need not be given.
    corrections: Optional[dict[str, dict[str, str]]] = Field(
        default=None, description='Per field: {"si": text} and/or {"bl": text}'
    )
