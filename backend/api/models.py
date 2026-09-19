"""Pydantic models — the API boundary only.

`backend/sdoc` stays plain dataclasses (see schema.py's own docstring); nothing
in there imports pydantic. These models exist to validate what crosses the
HTTP boundary, not to re-describe the pipeline's internal shapes.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    limit: Optional[int] = Field(default=None, description="Process only the first N emails")
    use_llm: bool = Field(default=True, description="Allow the model fallback when a key is configured")


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
