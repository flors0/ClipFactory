from __future__ import annotations

from pathlib import Path

from app.ai.ai_usage_ledger import AIUsageLedger
from app.ai.usage_models import (
    AIOperationType,
    AIUsageRecord,
)


def print_summary(
    title: str,
    lines: list[str],
) -> None:
    print()

    for line in lines:
        print(line)


def main() -> None:
    test_ledger_path = Path(
        "data/ai/dev_usage_ledger.json"
    )

    test_ledger_path.unlink(missing_ok=True)

    ledger = AIUsageLedger(
        ledger_path=test_ledger_path
    )

    job_id = "mock_silly_cats_job_001"

    records = [
        AIUsageRecord(
            provider_identity="gemini:test-model:v1",
            operation_type=AIOperationType.CLIP_ANALYSIS,
            job_id=job_id,
            request_id="request_001",
            input_tokens=12_500,
            output_tokens=420,
            cached_input_tokens=0,
            thinking_tokens=180,
            video_seconds=8.5,
            audio_seconds=8.5,
            estimated_cost_usd=0.0085,
        ),
        AIUsageRecord(
            provider_identity="gemini:test-model:v1",
            operation_type=AIOperationType.CLIP_ANALYSIS,
            job_id=job_id,
            request_id="request_002",
            input_tokens=15_200,
            output_tokens=510,
            cached_input_tokens=2_000,
            thinking_tokens=210,
            video_seconds=10.2,
            audio_seconds=10.2,
            estimated_cost_usd=0.0101,
            actual_cost_usd=0.0098,
        ),
        AIUsageRecord(
            provider_identity="gemini:test-model:v1",
            operation_type=AIOperationType.PROJECT_CREATIVE,
            job_id=job_id,
            request_id="request_003",
            input_tokens=3_100,
            output_tokens=650,
            cached_input_tokens=0,
            thinking_tokens=120,
            estimated_cost_usd=0.0034,
        ),
    ]

    for record in records:
        saved_record = ledger.record_usage(record)

        print(
            "Usage recorded: "
            f"{saved_record.operation_type.value} "
            f"({saved_record.record_id})"
        )

    print_summary(
        title="Current day",
        lines=ledger.current_day_summary().to_log_lines(
            "Current day AI usage"
        ),
    )

    print_summary(
        title="Current month",
        lines=ledger.current_month_summary().to_log_lines(
            "Current month AI usage"
        ),
    )

    print_summary(
        title="Current job",
        lines=ledger.summary_for_job(job_id).to_log_lines(
            f"Job AI usage: {job_id}"
        ),
    )

    print()
    print(f"Ledger entries: {ledger.entry_count()}")
    print(f"Ledger path: {test_ledger_path}")


if __name__ == "__main__":
    main()