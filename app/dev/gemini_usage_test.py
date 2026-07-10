from __future__ import annotations

from app.ai.gemini_config import load_gemini_config
from app.ai.gemini_usage import (
    GeminiUsageSnapshot,
    calculate_gemini_usage_cost,
)


def main() -> None:
    config = load_gemini_config()

    interaction_data = {
        "usage": {
            "input_tokens_by_modality": [
                {
                    "modality": "text",
                    "tokens": 693,
                },
                {
                    "modality": "video",
                    "tokens": 1093,
                },
            ],
            "total_cached_tokens": 0,
            "total_input_tokens": 1786,
            "total_output_tokens": 176,
            "total_thought_tokens": 0,
            "total_tokens": 1962,
            "total_tool_use_tokens": 0,
        }
    }

    usage = GeminiUsageSnapshot.from_interaction_data(
        interaction_data
    )

    cost = calculate_gemini_usage_cost(
        usage=usage,
        config=config,
        embedded_audio_seconds=12.0,
        has_embedded_audio=True,
    )

    for line in usage.to_log_lines():
        print(line)

    print()

    for line in cost.to_log_lines():
        print(line)

    expected_audio_tokens = 384
    expected_cost = 0.00080650

    if (
        cost.priced_audio_input_tokens
        != expected_audio_tokens
    ):
        raise AssertionError(
            "Unexpected embedded-audio token estimate: "
            f"{cost.priced_audio_input_tokens}"
        )

    if abs(cost.total_cost_usd - expected_cost) > 0.00000001:
        raise AssertionError(
            "Unexpected calculated cost: "
            f"{cost.total_cost_usd:.8f}"
        )

    print()
    print("Embedded video-audio cost test passed.")
    print("No API request was made.")


if __name__ == "__main__":
    main()