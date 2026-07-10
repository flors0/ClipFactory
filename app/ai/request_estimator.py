from __future__ import annotations

import math

from pydantic import BaseModel

from app.ai.budget_models import AIRequestEstimate
from app.ai.gemini_config import (
    GeminiConfig,
    GeminiMediaResolution,
    GeminiOperationConfig,
)
from app.ai.usage_models import AIOperationType


class GeminiRequestEstimateBreakdown(BaseModel):
    """
    Detailed local estimate generated before contacting Gemini.
    """

    provider_identity: str
    operation_type: AIOperationType

    job_id: str = ""
    request_label: str = ""

    prompt_text_tokens: int = 0
    video_tokens: int = 0
    audio_tokens: int = 0

    reserved_output_tokens: int = 0
    reserved_thinking_tokens: int = 0

    estimated_text_video_input_cost_usd: float = 0.0
    estimated_audio_input_cost_usd: float = 0.0
    estimated_output_cost_usd: float = 0.0
    estimated_total_cost_usd: float = 0.0

    video_seconds: float = 0.0
    audio_seconds: float = 0.0

    media_resolution: GeminiMediaResolution
    safety_multiplier: float = 1.0

    budget_estimate: AIRequestEstimate

    @property
    def total_input_tokens(self) -> int:
        return (
            self.prompt_text_tokens
            + self.video_tokens
            + self.audio_tokens
        )

    @property
    def total_reserved_tokens(self) -> int:
        return (
            self.total_input_tokens
            + self.reserved_output_tokens
            + self.reserved_thinking_tokens
        )

    def to_log_lines(self) -> list[str]:
        return [
            "Gemini request estimate:",
            f"Provider: {self.provider_identity}",
            f"Operation: {self.operation_type.value}",
            f"Request: {self.request_label or 'unnamed'}",
            f"Media resolution: {self.media_resolution.value}",
            f"Safety multiplier: {self.safety_multiplier:.2f}",
            f"Prompt text tokens: {self.prompt_text_tokens:,}",
            f"Video tokens: {self.video_tokens:,}",
            f"Audio tokens: {self.audio_tokens:,}",
            f"Total input tokens: {self.total_input_tokens:,}",
            f"Reserved output tokens: {self.reserved_output_tokens:,}",
            f"Reserved thinking tokens: {self.reserved_thinking_tokens:,}",
            f"Total reserved tokens: {self.total_reserved_tokens:,}",
            (
                "Estimated text/video input cost: "
                f"${self.estimated_text_video_input_cost_usd:.6f}"
            ),
            (
                "Estimated audio input cost: "
                f"${self.estimated_audio_input_cost_usd:.6f}"
            ),
            (
                "Estimated output/thinking cost: "
                f"${self.estimated_output_cost_usd:.6f}"
            ),
            f"Estimated total cost: ${self.estimated_total_cost_usd:.6f}",
        ]


class GeminiRequestEstimator:
    """
    Produces conservative request estimates before an API call.

    Actual token usage returned by Gemini is written to the AIUsageLedger
    after the provider request succeeds.
    """

    TOKENS_PER_MILLION = 1_000_000

    def __init__(
        self,
        config: GeminiConfig,
    ) -> None:
        self.config = config

    def estimate_request(
        self,
        operation_type: AIOperationType,
        text_content: str,
        job_id: str = "",
        request_label: str = "",
        video_seconds: float = 0.0,
        audio_seconds: float = 0.0,
        has_video: bool = False,
        has_audio: bool = False,
        media_resolution: GeminiMediaResolution | None = None,
    ) -> GeminiRequestEstimateBreakdown:
        operation_config = self._operation_config(
            operation_type
        )

        selected_resolution = (
            media_resolution
            or self.config.media_resolution
        )

        provider_identity = (
            self.config.provider_identity_for_resolution(
                selected_resolution
            )
        )

        safe_video_seconds = max(0.0, video_seconds)
        safe_audio_seconds = max(0.0, audio_seconds)

        token_config = self.config.token_estimation
        safety_multiplier = (
            token_config.estimate_safety_multiplier
        )

        prompt_text_tokens = self._estimate_text_tokens(
            text_content
        )

        video_tokens = 0

        if has_video:
            video_tokens = math.ceil(
                safe_video_seconds
                * self._video_tokens_per_second(
                    selected_resolution
                )
                * safety_multiplier
            )

        audio_tokens = 0

        if has_audio:
            audio_tokens = math.ceil(
                safe_audio_seconds
                * token_config.audio_tokens_per_second
                * safety_multiplier
            )

        text_video_input_tokens = (
            prompt_text_tokens
            + video_tokens
        )

        output_and_thinking_tokens = (
            operation_config.output_token_reserve
            + operation_config.thinking_token_reserve
        )

        pricing = self.config.pricing

        text_video_input_cost = (
            text_video_input_tokens
            / self.TOKENS_PER_MILLION
            * pricing.input_text_image_video_per_million_usd
        )

        audio_input_cost = (
            audio_tokens
            / self.TOKENS_PER_MILLION
            * pricing.input_audio_per_million_usd
        )

        output_cost = (
            output_and_thinking_tokens
            / self.TOKENS_PER_MILLION
            * pricing.output_including_thinking_per_million_usd
        )

        total_cost = (
            text_video_input_cost
            + audio_input_cost
            + output_cost
        )

        total_input_tokens = (
            text_video_input_tokens
            + audio_tokens
        )

        budget_estimate = AIRequestEstimate(
            provider_identity=provider_identity,
            operation_type=operation_type,
            job_id=job_id,
            request_label=request_label,
            input_tokens=total_input_tokens,
            output_tokens=operation_config.output_token_reserve,
            thinking_tokens=operation_config.thinking_token_reserve,
            video_seconds=(
                safe_video_seconds
                if has_video
                else 0.0
            ),
            audio_seconds=(
                safe_audio_seconds
                if has_audio
                else 0.0
            ),
            estimated_cost_usd=total_cost,
        )

        return GeminiRequestEstimateBreakdown(
            provider_identity=provider_identity,
            operation_type=operation_type,
            job_id=job_id,
            request_label=request_label,
            prompt_text_tokens=prompt_text_tokens,
            video_tokens=video_tokens,
            audio_tokens=audio_tokens,
            reserved_output_tokens=(
                operation_config.output_token_reserve
            ),
            reserved_thinking_tokens=(
                operation_config.thinking_token_reserve
            ),
            estimated_text_video_input_cost_usd=(
                text_video_input_cost
            ),
            estimated_audio_input_cost_usd=audio_input_cost,
            estimated_output_cost_usd=output_cost,
            estimated_total_cost_usd=total_cost,
            video_seconds=(
                safe_video_seconds
                if has_video
                else 0.0
            ),
            audio_seconds=(
                safe_audio_seconds
                if has_audio
                else 0.0
            ),
            media_resolution=selected_resolution,
            safety_multiplier=safety_multiplier,
            budget_estimate=budget_estimate,
        )

    def _estimate_text_tokens(
        self,
        text_content: str,
    ) -> int:
        if not text_content:
            return 0

        characters_per_token = (
            self.config
            .token_estimation
            .text_characters_per_token
        )

        return math.ceil(
            len(text_content) / characters_per_token
        )

    def _video_tokens_per_second(
        self,
        resolution: GeminiMediaResolution,
    ) -> float:
        token_config = self.config.token_estimation

        if resolution == GeminiMediaResolution.LOW:
            return token_config.low_video_tokens_per_second

        if resolution == GeminiMediaResolution.MEDIUM:
            return token_config.medium_video_tokens_per_second

        if resolution == GeminiMediaResolution.HIGH:
            return token_config.high_video_tokens_per_second

        return (
            token_config
            .unspecified_video_tokens_per_second
        )

    def _operation_config(
        self,
        operation_type: AIOperationType,
    ) -> GeminiOperationConfig:
        if operation_type == AIOperationType.CLIP_ANALYSIS:
            return self.config.clip_analysis

        if operation_type == AIOperationType.PROJECT_CREATIVE:
            return self.config.project_creative

        if operation_type == AIOperationType.FINAL_VIDEO_REVIEW:
            return self.config.final_video_review

        raise ValueError(
            "No Gemini estimation configuration exists for "
            f"operation type: {operation_type.value}"
        )