from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.ai.gemini_config import GeminiConfig


class GeminiUsageSnapshot(BaseModel):
    """
    Normalized token usage extracted from a Gemini response.

    The Gemini API may expose input usage both as a total and as a
    modality breakdown. ClipFactory stores both forms so video, audio,
    and text usage can be inspected separately.
    """

    text_input_tokens: int = Field(default=0, ge=0)
    image_input_tokens: int = Field(default=0, ge=0)
    video_input_tokens: int = Field(default=0, ge=0)
    audio_input_tokens: int = Field(default=0, ge=0)
    other_input_tokens: int = Field(default=0, ge=0)

    total_input_tokens: int = Field(default=0, ge=0)
    total_output_tokens: int = Field(default=0, ge=0)
    total_thought_tokens: int = Field(default=0, ge=0)
    total_cached_tokens: int = Field(default=0, ge=0)
    total_tool_use_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    @classmethod
    def from_interaction_data(
        cls,
        interaction_data: dict[str, Any],
    ) -> "GeminiUsageSnapshot":
        usage_data = interaction_data.get("usage")

        if not isinstance(usage_data, dict):
            raise ValueError(
                "Gemini response does not contain a valid usage object."
            )

        modality_totals = {
            "text": 0,
            "image": 0,
            "video": 0,
            "audio": 0,
            "other": 0,
        }

        raw_modalities = usage_data.get(
            "input_tokens_by_modality",
            [],
        )

        if isinstance(raw_modalities, list):
            for raw_modality in raw_modalities:
                if not isinstance(raw_modality, dict):
                    continue

                modality = str(
                    raw_modality.get("modality", "other")
                ).strip().lower()

                tokens = cls._safe_int(
                    raw_modality.get("tokens", 0)
                )

                if modality not in modality_totals:
                    modality = "other"

                modality_totals[modality] += tokens

        modality_input_total = sum(
            modality_totals.values()
        )

        total_input_tokens = cls._safe_int(
            usage_data.get("total_input_tokens", 0)
        )

        if total_input_tokens == 0:
            total_input_tokens = modality_input_total

        total_output_tokens = cls._safe_int(
            usage_data.get("total_output_tokens", 0)
        )

        total_thought_tokens = cls._safe_int(
            usage_data.get("total_thought_tokens", 0)
        )

        total_cached_tokens = cls._safe_int(
            usage_data.get("total_cached_tokens", 0)
        )

        total_tool_use_tokens = cls._safe_int(
            usage_data.get("total_tool_use_tokens", 0)
        )

        total_tokens = cls._safe_int(
            usage_data.get("total_tokens", 0)
        )

        if total_tokens == 0:
            total_tokens = (
                total_input_tokens
                + total_output_tokens
                + total_thought_tokens
                + total_tool_use_tokens
            )

        return cls(
            text_input_tokens=modality_totals["text"],
            image_input_tokens=modality_totals["image"],
            video_input_tokens=modality_totals["video"],
            audio_input_tokens=modality_totals["audio"],
            other_input_tokens=modality_totals["other"],
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_thought_tokens=total_thought_tokens,
            total_cached_tokens=total_cached_tokens,
            total_tool_use_tokens=total_tool_use_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    def to_log_lines(self) -> list[str]:
        return [
            "Gemini actual usage:",
            f"Text input tokens: {self.text_input_tokens:,}",
            f"Image input tokens: {self.image_input_tokens:,}",
            f"Video input tokens: {self.video_input_tokens:,}",
            f"Audio input tokens: {self.audio_input_tokens:,}",
            f"Other input tokens: {self.other_input_tokens:,}",
            f"Total input tokens: {self.total_input_tokens:,}",
            f"Output tokens: {self.total_output_tokens:,}",
            f"Thought tokens: {self.total_thought_tokens:,}",
            f"Cached tokens: {self.total_cached_tokens:,}",
            f"Tool-use tokens: {self.total_tool_use_tokens:,}",
            f"Total tokens: {self.total_tokens:,}",
        ]


class GeminiUsageCostBreakdown(BaseModel):
    """
    Cost calculated from actual Gemini token counts and configured prices.

    Google does not return a monetary amount with each response. Therefore,
    this is calculated locally from actual token usage and the configured
    pricing table.
    """

    non_audio_input_tokens: int = Field(default=0, ge=0)
    audio_input_tokens: int = Field(default=0, ge=0)
    output_and_thinking_tokens: int = Field(default=0, ge=0)

    non_audio_input_cost_usd: float = Field(default=0.0, ge=0)
    audio_input_cost_usd: float = Field(default=0.0, ge=0)
    output_and_thinking_cost_usd: float = Field(default=0.0, ge=0)

    total_cost_usd: float = Field(default=0.0, ge=0)

    def to_log_lines(self) -> list[str]:
        return [
            "Gemini token-derived cost:",
            (
                "Non-audio input cost: "
                f"${self.non_audio_input_cost_usd:.8f}"
            ),
            (
                "Audio input cost: "
                f"${self.audio_input_cost_usd:.8f}"
            ),
            (
                "Output/thinking cost: "
                f"${self.output_and_thinking_cost_usd:.8f}"
            ),
            f"Calculated total cost: ${self.total_cost_usd:.8f}",
        ]


def calculate_gemini_usage_cost(
    usage: GeminiUsageSnapshot,
    config: GeminiConfig,
) -> GeminiUsageCostBreakdown:
    """
    Calculates cost from actual tokens returned by Gemini.

    Cached input tokens are currently conservatively included at the normal
    input rate. ClipFactory does not yet use explicit context caching.
    """

    tokens_per_million = 1_000_000

    audio_input_tokens = min(
        usage.audio_input_tokens,
        usage.total_input_tokens,
    )

    non_audio_input_tokens = max(
        0,
        usage.total_input_tokens - audio_input_tokens,
    )

    output_and_thinking_tokens = (
        usage.total_output_tokens
        + usage.total_thought_tokens
    )

    pricing = config.pricing

    non_audio_input_cost = (
        non_audio_input_tokens
        / tokens_per_million
        * pricing.input_text_image_video_per_million_usd
    )

    audio_input_cost = (
        audio_input_tokens
        / tokens_per_million
        * pricing.input_audio_per_million_usd
    )

    output_and_thinking_cost = (
        output_and_thinking_tokens
        / tokens_per_million
        * pricing.output_including_thinking_per_million_usd
    )

    return GeminiUsageCostBreakdown(
        non_audio_input_tokens=non_audio_input_tokens,
        audio_input_tokens=audio_input_tokens,
        output_and_thinking_tokens=output_and_thinking_tokens,
        non_audio_input_cost_usd=non_audio_input_cost,
        audio_input_cost_usd=audio_input_cost,
        output_and_thinking_cost_usd=(
            output_and_thinking_cost
        ),
        total_cost_usd=(
            non_audio_input_cost
            + audio_input_cost
            + output_and_thinking_cost
        ),
    )