from __future__ import annotations

from pathlib import Path

from app.ai.ai_budget_guard import AIBudgetGuard
from app.ai.ai_usage_ledger import AIUsageLedger
from app.ai.gemini_config import (
    GeminiMediaResolution,
    load_gemini_config,
)
from app.ai.request_estimator import GeminiRequestEstimator
from app.ai.usage_models import AIOperationType


def print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def main() -> None:
    config = load_gemini_config()

    print("Gemini config loaded.")
    print(f"Enabled: {config.enabled}")
    print(f"Model: {config.model}")
    print(f"Provider identity: {config.provider_identity}")
    print(f"Media resolution: {config.media_resolution.value}")
    print()

    estimator = GeminiRequestEstimator(config)

    clip_prompt = """
Analyze this clip for a short-form ranking video.

Theme: silly cats
Target platform: TikTok and YouTube Shorts

Determine whether the clip matches the theme, assess its hook and quality,
and generate a short lowercase ranking caption.
""".strip()

    medium_estimate = estimator.estimate_request(
        operation_type=AIOperationType.CLIP_ANALYSIS,
        text_content=clip_prompt,
        job_id="silly_cats_job_001",
        request_label="clip_001_analysis_medium",
        video_seconds=10.0,
        audio_seconds=10.0,
        has_video=True,
        has_audio=True,
        media_resolution=GeminiMediaResolution.MEDIUM,
    )

    print_lines(medium_estimate.to_log_lines())

    test_ledger_path = Path(
        "data/ai/dev_request_estimator_ledger.json"
    )
    test_ledger_path.unlink(missing_ok=True)

    ledger = AIUsageLedger(
        ledger_path=test_ledger_path
    )

    budget_guard = AIBudgetGuard.from_config_file(
        ledger=ledger
    )

    decision = budget_guard.check(
        medium_estimate.budget_estimate
    )

    print()

    for line in decision.to_log_lines():
        print(line)

    print()
    print("--- High-resolution comparison ---")

    high_estimate = estimator.estimate_request(
        operation_type=AIOperationType.CLIP_ANALYSIS,
        text_content=clip_prompt,
        job_id="silly_cats_job_001",
        request_label="clip_001_analysis_high",
        video_seconds=10.0,
        audio_seconds=10.0,
        has_video=True,
        has_audio=True,
        media_resolution=GeminiMediaResolution.HIGH,
    )

    print_lines(high_estimate.to_log_lines())

    if high_estimate.video_tokens <= medium_estimate.video_tokens:
        raise AssertionError(
            "High-resolution video estimate should exceed "
            "the medium-resolution estimate."
        )

    print()
    print("Resolution comparison passed.")
    print("No API request was made.")


if __name__ == "__main__":
    main()