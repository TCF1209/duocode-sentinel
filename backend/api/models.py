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
