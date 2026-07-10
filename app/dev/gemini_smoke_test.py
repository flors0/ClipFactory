from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google import genai
from pydantic import BaseModel, Field

from app.ai.ai_budget_guard import AIBudgetGuard
from app.ai.ai_usage_ledger import AIUsageLedger
from app.ai.gemini_config import load_gemini_config
from app.ai.gemini_usage import (
    GeminiUsageSnapshot,
    calculate_gemini_usage_cost,
)
from app.ai.request_estimator import GeminiRequestEstimator
from app.ai.usage_models import (
    AIOperationType,
    AIUsageRecord,
)


class GeminiSmokeResult(BaseModel):
    status: str = Field(
        description="Return exactly 'ok' when the request succeeded."
    )
    message: str = Field(
        description="A short confirmation message."
    )
    model_purpose: str = Field(
        description="A short description of what the model was asked to do."
    )


def print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def find_usage_fields(
    value: Any,
    path: str = "",
) -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []

    if isinstance(value, dict):
        for key, child_value in value.items():
            child_path = f"{path}.{key}" if path else key
            normalized_key = key.lower()

            if "usage" in normalized_key or "token" in normalized_key:
                matches.append(
                    (
                        child_path,
                        child_value,
                    )
                )

            matches.extend(
                find_usage_fields(
                    value=child_value,
                    path=child_path,
                )
            )

    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            child_path = f"{path}[{index}]"

            matches.extend(
                find_usage_fields(
                    value=child_value,
                    path=child_path,
                )
            )

    return matches


def main() -> None:
    config = load_gemini_config()

    if not config.enabled:
        raise RuntimeError(
            "Gemini is disabled in config/gemini.json. "
            "Set 'enabled' to true before running this real API test."
        )

    environment_variable = (
        config.api_key_environment_variable.strip()
        or "GEMINI_API_KEY"
    )

    api_key = os.getenv(environment_variable)

    if not api_key:
        raise RuntimeError(
            f"Environment variable '{environment_variable}' is not set."
        )

    operation_type = AIOperationType.PROJECT_CREATIVE
    job_id = "gemini_smoke_test"
    request_label = "structured_output_smoke_test"

    prompt = (
        "This is a minimal ClipFactory API connection test. "
        "Return status 'ok', a brief confirmation message, and explain "
        "that the purpose was to verify structured JSON output."
    )

    estimator = GeminiRequestEstimator(config)

    estimate = estimator.estimate_request(
        operation_type=operation_type,
        text_content=prompt,
        job_id=job_id,
        request_label=request_label,
        has_video=False,
        has_audio=False,
    )

    print_lines(estimate.to_log_lines())
    print()

    ledger_path = Path(
        "data/ai/dev_gemini_smoke_ledger.json"
    )

    ledger = AIUsageLedger(
        ledger_path=ledger_path
    )

    budget_guard = AIBudgetGuard.from_config_file(
        ledger=ledger
    )

    decision = budget_guard.ensure_allowed(
        estimate.budget_estimate
    )

    print_lines(decision.to_log_lines())
    print()

    client = genai.Client(api_key=api_key)

    try:
        interaction = client.interactions.create(
            model=config.model,
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": GeminiSmokeResult.model_json_schema(),
            },
            store=config.store_interactions,
            timeout=config.request_timeout_seconds,
        )

        if not interaction.output_text:
            raise RuntimeError(
                "Gemini returned no output text."
            )

        result = GeminiSmokeResult.model_validate_json(
            interaction.output_text
        )

        print("Structured result:")
        print(result.model_dump_json(indent=2))

        interaction_data = interaction.model_dump(
            mode="json",
            exclude_none=True,
        )

        usage = GeminiUsageSnapshot.from_interaction_data(
            interaction_data
        )

        usage_cost = calculate_gemini_usage_cost(
            usage=usage,
            config=config,
        )

        print()
        print_lines(usage.to_log_lines())

        print()
        print_lines(usage_cost.to_log_lines())

        request_id = str(
            interaction_data.get("id", "")
        )

        usage_record = AIUsageRecord(
            provider_identity=config.provider_identity,
            operation_type=operation_type,
            job_id=job_id,
            request_id=request_id,
            input_tokens=usage.total_input_tokens,
            output_tokens=usage.total_output_tokens,
            cached_input_tokens=usage.total_cached_tokens,
            thinking_tokens=usage.total_thought_tokens,
            estimated_cost_usd=(
                estimate.estimated_total_cost_usd
            ),
            actual_cost_usd=usage_cost.total_cost_usd,
            metadata={
                "request_label": request_label,
                "model": config.model,
                "text_input_tokens": (
                    usage.text_input_tokens
                ),
                "image_input_tokens": (
                    usage.image_input_tokens
                ),
                "video_input_tokens": (
                    usage.video_input_tokens
                ),
                "audio_input_tokens": (
                    usage.audio_input_tokens
                ),
                "other_input_tokens": (
                    usage.other_input_tokens
                ),
                "tool_use_tokens": (
                    usage.total_tool_use_tokens
                ),
                "cost_basis": (
                    "calculated_from_actual_usage_tokens"
                ),
            },
        )

        ledger.record_usage(usage_record)

        print()
        print("Usage was written to the AI ledger.")
        print(f"Ledger path: {ledger_path}")

        print()

        print_lines(
            ledger.summary_for_job(job_id).to_log_lines(
                f"Job AI usage: {job_id}"
            )
        )

        usage_fields = find_usage_fields(
            interaction_data
        )

        print()
        print("Detected raw usage/token fields:")

        if not usage_fields:
            print(
                "No usage fields were found in the interaction response."
            )
        else:
            for field_path, field_value in usage_fields:
                print(
                    f"{field_path}: "
                    f"{json.dumps(field_value, ensure_ascii=False)}"
                )

        debug_path = Path(
            "data/ai/dev_gemini_smoke_response.json"
        )

        debug_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        debug_path.write_text(
            json.dumps(
                interaction_data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print()
        print(f"Response debug file: {debug_path}")

    finally:
        client.close()


if __name__ == "__main__":
    main()