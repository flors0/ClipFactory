from __future__ import annotations

from pathlib import Path

from app.ai.ai_budget_guard import (
    AIBudgetExceededError,
    AIBudgetGuard,
)
from app.ai.ai_usage_ledger import AIUsageLedger
from app.ai.budget_models import (
    AIBudgetConfig,
    AIRequestEstimate,
)
from app.ai.usage_models import (
    AIOperationType,
    AIUsageRecord,
)


def print_decision(title: str, decision) -> None:
    print()
    print(f"--- {title} ---")

    for line in decision.to_log_lines():
        print(line)


def main() -> None:
    test_ledger_path = Path(
        "data/ai/dev_budget_guard_ledger.json"
    )

    test_ledger_path.unlink(missing_ok=True)

    ledger = AIUsageLedger(
        ledger_path=test_ledger_path
    )

    job_id = "mock_silly_cats_job_001"

    ledger.record_usage(
        AIUsageRecord(
            provider_identity="gemini:test-model:v1",
            operation_type=AIOperationType.CLIP_ANALYSIS,
            job_id=job_id,
            request_id="existing_request_001",
            input_tokens=25_000,
            output_tokens=1_000,
            thinking_tokens=300,
            video_seconds=20.0,
            audio_seconds=20.0,
            estimated_cost_usd=1.50,
        )
    )

    config = AIBudgetConfig(
        enabled=True,
        stop_on_limit=True,
        max_estimated_cost_per_request_usd=0.25,
        max_estimated_cost_per_job_usd=2.00,
        max_daily_cost_usd=2.00,
        max_monthly_cost_usd=20.00,
        max_total_tokens_per_request=500_000,
        max_video_seconds_per_request=180.0,
        max_audio_seconds_per_request=180.0,
        warning_threshold_ratio=0.80,
    )

    guard = AIBudgetGuard(
        config=config,
        ledger=ledger,
    )

    allowed_estimate = AIRequestEstimate(
        provider_identity="gemini:test-model:v1",
        operation_type=AIOperationType.CLIP_ANALYSIS,
        job_id=job_id,
        request_label="small_clip_analysis",
        input_tokens=18_000,
        output_tokens=800,
        thinking_tokens=200,
        video_seconds=12.0,
        audio_seconds=12.0,
        estimated_cost_usd=0.20,
    )

    allowed_decision = guard.check(
        allowed_estimate
    )

    print_decision(
        "Allowed request",
        allowed_decision,
    )

    blocked_estimate = AIRequestEstimate(
        provider_identity="gemini:test-model:v1",
        operation_type=AIOperationType.CLIP_ANALYSIS,
        job_id=job_id,
        request_label="oversized_clip_analysis",
        input_tokens=600_000,
        output_tokens=5_000,
        thinking_tokens=1_000,
        video_seconds=240.0,
        audio_seconds=240.0,
        estimated_cost_usd=0.60,
    )

    blocked_decision = guard.check(
        blocked_estimate
    )

    print_decision(
        "Blocked request",
        blocked_decision,
    )

    print()
    print("--- ensure_allowed test ---")

    try:
        guard.ensure_allowed(blocked_estimate)
    except AIBudgetExceededError as error:
        print("Budget guard correctly blocked the request.")
        print()
        print(error)

    print()
    print(f"Test ledger: {test_ledger_path}")


if __name__ == "__main__":
    main()