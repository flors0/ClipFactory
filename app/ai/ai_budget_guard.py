from __future__ import annotations

import json
from pathlib import Path

from app.ai.ai_usage_ledger import AIUsageLedger
from app.ai.budget_models import (
    AIBudgetConfig,
    AIBudgetDecision,
    AIRequestEstimate,
)
from app.ai.usage_models import AIUsageSummary


class AIBudgetExceededError(Exception):
    def __init__(
        self,
        decision: AIBudgetDecision,
    ) -> None:
        self.decision = decision

        message = "\n".join(decision.to_log_lines())
        super().__init__(message)


class AIBudgetGuard:
    """
    Checks estimated request usage against configured limits.

    The guard does not contact an AI provider and does not record usage.
    It only decides whether a future request is allowed.

    Actual usage is written to AIUsageLedger after a successful provider
    response.
    """

    def __init__(
        self,
        config: AIBudgetConfig,
        ledger: AIUsageLedger | None = None,
    ) -> None:
        self.config = config
        self.ledger = ledger or AIUsageLedger()

    @classmethod
    def from_config_file(
        cls,
        config_path: Path = Path("config/ai_budget.json"),
        ledger: AIUsageLedger | None = None,
    ) -> "AIBudgetGuard":
        config = cls.load_config(config_path)

        return cls(
            config=config,
            ledger=ledger,
        )

    @staticmethod
    def load_config(
        config_path: Path,
    ) -> AIBudgetConfig:
        if not config_path.exists():
            raise FileNotFoundError(
                f"AI budget config was not found: {config_path}"
            )

        try:
            data = json.loads(
                config_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"AI budget config contains invalid JSON: {config_path}"
            ) from error

        return AIBudgetConfig.model_validate(data)

    def check(
        self,
        estimate: AIRequestEstimate,
    ) -> AIBudgetDecision:
        if not self.config.enabled:
            return AIBudgetDecision(
                allowed=True,
                limit_exceeded=False,
                provider_identity=estimate.provider_identity,
                operation_type=estimate.operation_type,
                job_id=estimate.job_id,
                request_label=estimate.request_label,
                request_estimated_cost_usd=estimate.estimated_cost_usd,
                warnings=[
                    "AI budget protection is disabled."
                ],
            )

        daily_summary = self.ledger.current_day_summary()
        monthly_summary = self.ledger.current_month_summary()

        if estimate.job_id.strip():
            job_summary = self.ledger.summary_for_job(
                estimate.job_id.strip()
            )
        else:
            job_summary = AIUsageSummary()

        current_job_cost = job_summary.billable_cost_usd
        current_daily_cost = daily_summary.billable_cost_usd
        current_monthly_cost = monthly_summary.billable_cost_usd

        projected_job_cost = (
            current_job_cost
            + estimate.estimated_cost_usd
        )
        projected_daily_cost = (
            current_daily_cost
            + estimate.estimated_cost_usd
        )
        projected_monthly_cost = (
            current_monthly_cost
            + estimate.estimated_cost_usd
        )

        reasons: list[str] = []
        warnings: list[str] = []

        self._check_request_limits(
            estimate=estimate,
            reasons=reasons,
        )

        self._check_cost_limit(
            label="job",
            current_value=current_job_cost,
            projected_value=projected_job_cost,
            limit=self.config.max_estimated_cost_per_job_usd,
            reasons=reasons,
            warnings=warnings,
        )

        self._check_cost_limit(
            label="daily",
            current_value=current_daily_cost,
            projected_value=projected_daily_cost,
            limit=self.config.max_daily_cost_usd,
            reasons=reasons,
            warnings=warnings,
        )

        self._check_cost_limit(
            label="monthly",
            current_value=current_monthly_cost,
            projected_value=projected_monthly_cost,
            limit=self.config.max_monthly_cost_usd,
            reasons=reasons,
            warnings=warnings,
        )

        if (
            self.config.max_estimated_cost_per_job_usd is not None
            and not estimate.job_id.strip()
        ):
            warnings.append(
                "No job ID was provided, so the per-job budget "
                "cannot be tracked correctly."
            )

        limit_exceeded = bool(reasons)

        if limit_exceeded and not self.config.stop_on_limit:
            warnings.append(
                "A budget limit was exceeded, but stop_on_limit "
                "is disabled."
            )

            for reason in reasons:
                warnings.append(reason)

            reasons = []

        allowed = not reasons

        return AIBudgetDecision(
            allowed=allowed,
            limit_exceeded=limit_exceeded,
            provider_identity=estimate.provider_identity,
            operation_type=estimate.operation_type,
            job_id=estimate.job_id,
            request_label=estimate.request_label,
            request_estimated_cost_usd=estimate.estimated_cost_usd,
            current_job_cost_usd=current_job_cost,
            projected_job_cost_usd=projected_job_cost,
            current_daily_cost_usd=current_daily_cost,
            projected_daily_cost_usd=projected_daily_cost,
            current_monthly_cost_usd=current_monthly_cost,
            projected_monthly_cost_usd=projected_monthly_cost,
            reasons=reasons,
            warnings=warnings,
        )

    def ensure_allowed(
        self,
        estimate: AIRequestEstimate,
    ) -> AIBudgetDecision:
        decision = self.check(estimate)

        if not decision.allowed:
            raise AIBudgetExceededError(decision)

        return decision

    def _check_request_limits(
        self,
        estimate: AIRequestEstimate,
        reasons: list[str],
    ) -> None:
        request_cost_limit = (
            self.config.max_estimated_cost_per_request_usd
        )

        if (
            request_cost_limit is not None
            and estimate.estimated_cost_usd > request_cost_limit
        ):
            reasons.append(
                "Estimated request cost exceeds the per-request limit "
                f"(${estimate.estimated_cost_usd:.4f} > "
                f"${request_cost_limit:.4f})."
            )

        token_limit = self.config.max_total_tokens_per_request

        if (
            token_limit is not None
            and estimate.total_tokens > token_limit
        ):
            reasons.append(
                "Estimated request token count exceeds the limit "
                f"({estimate.total_tokens:,} > {token_limit:,})."
            )

        video_limit = self.config.max_video_seconds_per_request

        if (
            video_limit is not None
            and estimate.video_seconds > video_limit
        ):
            reasons.append(
                "Video duration exceeds the per-request limit "
                f"({estimate.video_seconds:.2f}s > "
                f"{video_limit:.2f}s)."
            )

        audio_limit = self.config.max_audio_seconds_per_request

        if (
            audio_limit is not None
            and estimate.audio_seconds > audio_limit
        ):
            reasons.append(
                "Audio duration exceeds the per-request limit "
                f"({estimate.audio_seconds:.2f}s > "
                f"{audio_limit:.2f}s)."
            )

    def _check_cost_limit(
        self,
        label: str,
        current_value: float,
        projected_value: float,
        limit: float | None,
        reasons: list[str],
        warnings: list[str],
    ) -> None:
        if limit is None:
            return

        if projected_value > limit:
            reasons.append(
                f"Projected {label} AI cost exceeds the limit "
                f"(${projected_value:.4f} > ${limit:.4f})."
            )
            return

        warning_threshold = (
            limit
            * self.config.warning_threshold_ratio
        )

        if projected_value >= warning_threshold:
            percentage = (
                projected_value / limit * 100
                if limit > 0
                else 100
            )

            warnings.append(
                f"Projected {label} AI cost has reached "
                f"{percentage:.1f}% of its limit "
                f"(${projected_value:.4f} / ${limit:.4f})."
            )