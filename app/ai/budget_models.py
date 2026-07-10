from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.usage_models import AIOperationType


class AIBudgetConfig(BaseModel):
    """
    Provider-independent AI budget limits.

    A value of None disables the corresponding limit.
    Monetary limits use USD because AI providers normally report API
    pricing and usage in USD.
    """

    enabled: bool = True
    stop_on_limit: bool = True

    max_estimated_cost_per_request_usd: float | None = Field(
        default=0.25,
        gt=0,
    )
    max_estimated_cost_per_job_usd: float | None = Field(
        default=2.00,
        gt=0,
    )
    max_daily_cost_usd: float | None = Field(
        default=2.00,
        gt=0,
    )
    max_monthly_cost_usd: float | None = Field(
        default=20.00,
        gt=0,
    )

    max_total_tokens_per_request: int | None = Field(
        default=500_000,
        gt=0,
    )
    max_video_seconds_per_request: float | None = Field(
        default=180.0,
        gt=0,
    )
    max_audio_seconds_per_request: float | None = Field(
        default=180.0,
        gt=0,
    )

    warning_threshold_ratio: float = Field(
        default=0.80,
        ge=0,
        le=1,
    )


class AIRequestEstimate(BaseModel):
    """
    Estimated usage for one future AI request.

    This object is checked before the provider is contacted.
    """

    provider_identity: str
    operation_type: AIOperationType

    job_id: str = ""
    request_label: str = ""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    thinking_tokens: int = Field(default=0, ge=0)

    video_seconds: float = Field(default=0.0, ge=0)
    audio_seconds: float = Field(default=0.0, ge=0)

    estimated_cost_usd: float = Field(default=0.0, ge=0)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.thinking_tokens
        )


class AIBudgetDecision(BaseModel):
    allowed: bool
    limit_exceeded: bool = False

    provider_identity: str
    operation_type: AIOperationType

    job_id: str = ""
    request_label: str = ""

    request_estimated_cost_usd: float = 0.0

    current_job_cost_usd: float = 0.0
    projected_job_cost_usd: float = 0.0

    current_daily_cost_usd: float = 0.0
    projected_daily_cost_usd: float = 0.0

    current_monthly_cost_usd: float = 0.0
    projected_monthly_cost_usd: float = 0.0

    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_log_lines(self) -> list[str]:
        lines = [
            "AI budget decision:",
            f"Allowed: {'yes' if self.allowed else 'no'}",
            f"Provider: {self.provider_identity}",
            f"Operation: {self.operation_type.value}",
        ]

        if self.job_id:
            lines.append(f"Job: {self.job_id}")

        if self.request_label:
            lines.append(f"Request: {self.request_label}")

        lines.extend(
            [
                (
                    "Request estimated cost: "
                    f"${self.request_estimated_cost_usd:.4f}"
                ),
                (
                    "Projected job cost: "
                    f"${self.projected_job_cost_usd:.4f}"
                ),
                (
                    "Projected daily cost: "
                    f"${self.projected_daily_cost_usd:.4f}"
                ),
                (
                    "Projected monthly cost: "
                    f"${self.projected_monthly_cost_usd:.4f}"
                ),
            ]
        )

        for warning in self.warnings:
            lines.append(f"Warning: {warning}")

        for reason in self.reasons:
            lines.append(f"Blocked: {reason}")

        return lines