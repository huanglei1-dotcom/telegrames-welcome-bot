from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SubmissionReviewInput(BaseModel):
    action: Literal["approved", "rejected", "pending"] = Field(..., description="New review status.")
    note: Optional[str] = Field(default=None, max_length=2000)
