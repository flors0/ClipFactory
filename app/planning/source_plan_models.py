from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.ai.analysis_models import (
    TargetPlatform,
    VideoFormat,
)


class ThemeDerivationMethod(str, Enum):
    EXPLICIT_HINT = "explicit_hint"
    COMMUNITY_NAME = "community_name"
    COMMUNITY_AND_TITLES = "community_and_titles"
    CANDIDATE_TITLES = "candidate_titles"
    FALLBACK = "fallback"


class SourceProjectPlan(BaseModel):
    """
    Internal plan created from a source profile, candidate metadata,
    and the selected preset.

    This is not the final rendered-video plan. It describes what kind of
    content ClipFactory should analyze and assemble.
    """

    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)

    source_profile_id: str = Field(min_length=1)
    source_community: str = Field(min_length=1)

    preset_id: str = Field(min_length=1)
    target_platform: TargetPlatform
    video_format: VideoFormat

    theme: str = Field(min_length=1)
    theme_derivation: ThemeDerivationMethod
    theme_keywords: list[str] = Field(
        default_factory=list
    )

    candidate_ids: list[str] = Field(
        default_factory=list
    )
    candidate_count: int = Field(
        default=0,
        ge=0,
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    def to_log_lines(self) -> list[str]:
        lines = [
            "Source project plan:",
            f"Project ID: {self.project_id}",
            f"Project name: {self.project_name}",
            f"Community: r/{self.source_community}",
            f"Preset: {self.preset_id}",
            f"Target platform: {self.target_platform.value}",
            f"Video format: {self.video_format.value}",
            f"Theme: {self.theme}",
            (
                "Theme derivation: "
                f"{self.theme_derivation.value}"
            ),
            f"Candidates: {self.candidate_count}",
        ]

        if self.theme_keywords:
            lines.append(
                "Theme keywords: "
                + ", ".join(self.theme_keywords)
            )

        for warning in self.warnings:
            lines.append(f"Warning: {warning}")

        return lines