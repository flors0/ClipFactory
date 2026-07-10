from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from app.ai.gemini_config import GeminiConfig


class GeminiUsageSnapshot(BaseModel):
    """
    Normalized token usage extracted from a Gemini response.

    Gemini may report an uploaded video's embedded audio as part of the
    video modality instead of returning a separate audio modality entry.
    The raw reported values are preserved here.
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
    Cost calculated locally from Gemini's actual token totals.

    When Gemini groups embedded video audio into the video modality, the
    audio share is estimated from media duration and moved from the
    non-audio price bucket into the audio price bucket.
    """

    non_audio_input_tokens: int = Field(default=0, ge=0)
    priced_audio_input_tokens: int = Field(default=0, ge=0)

    reported_audio_input_tokens: int = Field(default=0, ge=0)
    estimated_embedded_audio_tokens: int = Field(default=0, ge=0)

    output_and_thinking_tokens: int = Field(default=0, ge=0)

    audio_token_source: str = "none"

    non_audio_input_cost_usd: float = Field(default=0.0, ge=0)
    audio_input_cost_usd: float = Field(default=0.0, ge=0)
    output_and_thinking_cost_usd: float = Field(default=0.0, ge=0)

    total_cost_usd: float = Field(default=0.0, ge=0)

    def to_log_lines(self) -> list[str]:
        return [
            "Gemini token-derived cost:",
            (
                "Audio token pricing source: "
                f"{self.audio_token_source}"
            ),
            (
                "Priced non-audio input tokens: "
                f"{self.non_audio_input_tokens:,}"
            ),
            (
                "Priced audio input tokens: "
                f"{self.priced_audio_input_tokens:,}"
            ),
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
    embedded_audio_seconds: float = 0.0,
    has_embedded_audio: bool = False,
) -> GeminiUsageCostBreakdown:
    """
    Calculates cost from Gemini's returned token totals.

    Preferred audio-token source:
    1. Explicit audio modality returned by Gemini.
    2. Duration-based estimate when audio is embedded in a video but Gemini
       reports the complete file under the video modality.
    3. Zero when the request contained no audio.

    Estimated embedded-audio tokens are subtracted from the non-audio input
    bucket, so they are not counted twice.
    """

    tokens_per_million = 1_000_000

    reported_audio_tokens = min(
        usage.audio_input_tokens,
        usage.total_input_tokens,
    )

    estimated_embedded_audio_tokens = 0
    priced_audio_tokens = 0
    audio_token_source = "none"

    if reported_audio_tokens > 0:
        priced_audio_tokens = reported_audio_tokens
        audio_token_source = "reported_audio_modality"

    elif (
        has_embedded_audio
        and embedded_audio_seconds > 0
        and usage.video_input_tokens > 0
    ):
        estimated_embedded_audio_tokens = math.ceil(
            embedded_audio_seconds
            * config.token_estimation.audio_tokens_per_second
        )

        priced_audio_tokens = min(
            estimated_embedded_audio_tokens,
            usage.video_input_tokens,
            usage.total_input_tokens,
        )

        audio_token_source = (
            "estimated_from_embedded_video_audio"
        )

    non_audio_input_tokens = max(
        0,
        usage.total_input_tokens - priced_audio_tokens,
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
        priced_audio_tokens
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
        priced_audio_input_tokens=priced_audio_tokens,
        reported_audio_input_tokens=reported_audio_tokens,
        estimated_embedded_audio_tokens=(
            estimated_embedded_audio_tokens
        ),
        output_and_thinking_tokens=(
            output_and_thinking_tokens
        ),
        audio_token_source=audio_token_source,
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