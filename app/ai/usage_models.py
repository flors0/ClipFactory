from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AIOperationType(str, Enum):
    CLIP_ANALYSIS = "clip_analysis"
    PROJECT_CREATIVE = "project_creative"
    FINAL_VIDEO_REVIEW = "final_video_review"
    OTHER = "other"


class AIUsageRecord(BaseModel):
    """
    Records the token and cost usage of one AI provider request.

    The record is provider-independent and can later be used for Gemini,
    Twelve Labs, or another AI service.
    """

    record_id: str = Field(
        default_factory=lambda: str(uuid4())
    )
    created_at_utc: datetime = Field(
        default_factory=utc_now
    )

    provider_identity: str
    operation_type: AIOperationType

    job_id: str = ""
    request_id: str = ""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    thinking_tokens: int = Field(default=0, ge=0)

    video_seconds: float = Field(default=0.0, ge=0)
    audio_seconds: float = Field(default=0.0, ge=0)

    estimated_cost_usd: float = Field(default=0.0, ge=0)
    actual_cost_usd: float | None = Field(default=None, ge=0)

    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.thinking_tokens
        )

    @property
    def billable_cost_usd(self) -> float:
        if self.actual_cost_usd is not None:
            return self.actual_cost_usd

        return self.estimated_cost_usd


class AIUsageSummary(BaseModel):
    records_count: int = 0

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    video_seconds: float = 0.0
    audio_seconds: float = 0.0

    estimated_cost_usd: float = 0.0
    known_actual_cost_usd: float = 0.0
    billable_cost_usd: float = 0.0

    records_with_actual_cost: int = 0

    def to_log_lines(
        self,
        title: str = "AI usage summary",
    ) -> list[str]:
        return [
            f"{title}:",
            f"Requests: {self.records_count}",
            f"Input tokens: {self.input_tokens:,}",
            f"Output tokens: {self.output_tokens:,}",
            f"Thinking tokens: {self.thinking_tokens:,}",
            f"Total tokens: {self.total_tokens:,}",
            f"Cached input tokens: {self.cached_input_tokens:,}",
            f"Video analyzed: {self.video_seconds:.2f}s",
            f"Audio analyzed: {self.audio_seconds:.2f}s",
            f"Estimated cost: ${self.estimated_cost_usd:.4f}",
            (
                "Known actual cost: "
                f"${self.known_actual_cost_usd:.4f} "
                f"({self.records_with_actual_cost} records)"
            ),
            f"Budget-accounted cost: ${self.billable_cost_usd:.4f}",
        ]