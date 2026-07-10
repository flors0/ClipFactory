from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class GeminiMediaResolution(str, Enum):
    UNSPECIFIED = "unspecified"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GeminiPricingConfig(BaseModel):
    """
    Paid-tier prices in USD per one million tokens.

    These values live in configuration because provider pricing can change.
    """

    input_text_image_video_per_million_usd: float = Field(
        default=0.25,
        ge=0,
    )
    input_audio_per_million_usd: float = Field(
        default=0.50,
        ge=0,
    )
    output_including_thinking_per_million_usd: float = Field(
        default=1.50,
        ge=0,
    )

    last_verified_date: str = "2026-07-10"


class GeminiTokenEstimationConfig(BaseModel):
    """
    Conservative local estimates used before an API request.

    Gemini 3 general-video estimates:
    - unspecified: approximately 70 visual tokens per second
    - low: approximately 70 visual tokens per second
    - medium: approximately 70 visual tokens per second
    - high: approximately 280 visual tokens per second

    Audio is estimated separately.
    """

    text_characters_per_token: float = Field(
        default=4.0,
        gt=0,
    )

    unspecified_video_tokens_per_second: float = Field(
        default=70.0,
        ge=0,
    )
    low_video_tokens_per_second: float = Field(
        default=70.0,
        ge=0,
    )
    medium_video_tokens_per_second: float = Field(
        default=70.0,
        ge=0,
    )
    high_video_tokens_per_second: float = Field(
        default=280.0,
        ge=0,
    )

    audio_tokens_per_second: float = Field(
        default=32.0,
        ge=0,
    )

    estimate_safety_multiplier: float = Field(
        default=1.15,
        ge=1.0,
    )

    last_verified_date: str = "2026-07-10"


class GeminiOperationConfig(BaseModel):
    prompt_version: str

    output_token_reserve: int = Field(
        default=1_000,
        ge=0,
    )
    thinking_token_reserve: int = Field(
        default=500,
        ge=0,
    )


class GeminiConfig(BaseModel):
    enabled: bool = False

    model: str = "gemini-3.1-flash-lite"
    api_mode: str = "interactions"

    api_key_environment_variable: str = "GEMINI_API_KEY"

    store_interactions: bool = False

    media_resolution: GeminiMediaResolution = (
        GeminiMediaResolution.MEDIUM
    )

    request_timeout_seconds: float = Field(
        default=180.0,
        gt=0,
    )
    file_processing_timeout_seconds: float = Field(
        default=300.0,
        gt=0,
    )

    pricing: GeminiPricingConfig = Field(
        default_factory=GeminiPricingConfig
    )
    token_estimation: GeminiTokenEstimationConfig = Field(
        default_factory=GeminiTokenEstimationConfig
    )

    clip_analysis: GeminiOperationConfig = Field(
        default_factory=lambda: GeminiOperationConfig(
            prompt_version="clip-analysis-v1",
            output_token_reserve=1_200,
            thinking_token_reserve=800,
        )
    )

    project_creative: GeminiOperationConfig = Field(
        default_factory=lambda: GeminiOperationConfig(
            prompt_version="project-creative-v1",
            output_token_reserve=1_500,
            thinking_token_reserve=700,
        )
    )

    final_video_review: GeminiOperationConfig = Field(
        default_factory=lambda: GeminiOperationConfig(
            prompt_version="final-video-review-v1",
            output_token_reserve=1_200,
            thinking_token_reserve=800,
        )
    )

    def provider_identity_for_resolution(
            self,
            resolution: GeminiMediaResolution | None = None,
    ) -> str:
        selected_resolution = resolution or self.media_resolution

        return (
            f"gemini:{self.model}:"
            f"resolution-{selected_resolution.value}:"
            f"{self.clip_analysis.prompt_version}:"
            f"{self.project_creative.prompt_version}:"
            f"{self.final_video_review.prompt_version}"
        )

    @property
    def provider_identity(self) -> str:
        return self.provider_identity_for_resolution()


def load_gemini_config(
    config_path: Path = Path("config/gemini.json"),
) -> GeminiConfig:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Gemini config was not found: {config_path}"
        )

    try:
        raw_data = json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Gemini config contains invalid JSON: {config_path}"
        ) from error

    return GeminiConfig.model_validate(raw_data)