from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.ai.analysis_models import (
    AIFieldPermissions,
    ClipAnalysisRequest,
    TargetPlatform,
    VideoFormat,
)
from app.analyze.media_probe import MediaProbe
from app.sources.source_models import (
    SourceCandidate,
    SourceProfile,
)


class ClipAnalysisPresetContext(BaseModel):
    """
    AI-relevant settings derived from the selected ClipFactory preset.

    The final UI only needs to select a preset. ClipFactory converts that
    preset into this provider-independent analysis context.
    """

    preset_id: str = Field(min_length=1)
    target_platform: TargetPlatform
    video_format: VideoFormat
    desired_caption_style: str = ""

    permissions: AIFieldPermissions = Field(
        default_factory=AIFieldPermissions
    )

    @classmethod
    def from_preset_id(
        cls,
        preset_id: str,
    ) -> "ClipAnalysisPresetContext":
        normalized_preset_id = preset_id.strip().lower()

        if not normalized_preset_id:
            raise ValueError(
                "Preset ID must not be empty."
            )

        if "tiktok" in normalized_preset_id:
            target_platform = TargetPlatform.TIKTOK
        else:
            target_platform = TargetPlatform.YOUTUBE_SHORTS

        if "meme" in normalized_preset_id:
            video_format = VideoFormat.MEME
            caption_style = "short punchline"

        elif "compilation" in normalized_preset_id:
            video_format = VideoFormat.COMPILATION
            caption_style = "short descriptive lowercase caption"

        else:
            video_format = VideoFormat.RANKING
            caption_style = "short lowercase reaction"

        return cls(
            preset_id=preset_id.strip(),
            target_platform=target_platform,
            video_format=video_format,
            desired_caption_style=caption_style,
        )


class ClipAnalysisRequestFactory:
    """
    Builds complete ClipAnalysisRequest objects automatically.

    Responsibilities:
    - validate the resolved local media path
    - probe duration, resolution, FPS, codecs, and audio
    - preserve source metadata from the SourceCandidate
    - derive a theme from the source profile when no project theme exists
    - derive AI behavior from the selected preset
    """

    def __init__(
        self,
        media_probe: MediaProbe | None = None,
    ) -> None:
        self.media_probe = media_probe or MediaProbe()

    def create(
        self,
        candidate: SourceCandidate,
        source_profile: SourceProfile,
        local_path: Path,
        preset_context: ClipAnalysisPresetContext,
        project_theme: str = "",
    ) -> ClipAnalysisRequest:
        resolved_path = local_path.expanduser().resolve()

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"Resolved clip was not found: {resolved_path}"
            )

        if not resolved_path.is_file():
            raise ValueError(
                f"Resolved clip path is not a file: {resolved_path}"
            )

        media_info = self.media_probe.probe(
            resolved_path
        )

        if not media_info.has_video:
            raise ValueError(
                f"Resolved media contains no video stream: "
                f"{resolved_path.name}"
            )

        clip_id = self._resolve_clip_id(
            candidate=candidate,
            local_path=resolved_path,
        )

        theme = self._resolve_theme(
            source_profile=source_profile,
            project_theme=project_theme,
        )

        return ClipAnalysisRequest(
            clip_id=clip_id,
            local_path=resolved_path,
            candidate=candidate,
            media_info=media_info,
            preset_id=preset_context.preset_id,
            target_platform=preset_context.target_platform,
            video_format=preset_context.video_format,
            theme=theme,
            desired_caption_style=(
                preset_context.desired_caption_style
            ),
            permissions=preset_context.permissions,
        )

    def _resolve_clip_id(
        self,
        candidate: SourceCandidate,
        local_path: Path,
    ) -> str:
        candidate_id = str(
            getattr(
                candidate,
                "candidate_id",
                "",
            )
            or ""
        ).strip()

        if candidate_id:
            return candidate_id

        external_post_id = str(
            getattr(
                candidate,
                "external_post_id",
                "",
            )
            or ""
        ).strip()

        if external_post_id:
            return external_post_id

        normalized_stem = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            local_path.stem,
        ).strip("_")

        return normalized_stem or "resolved_clip"

    def _resolve_theme(
        self,
        source_profile: SourceProfile,
        project_theme: str,
    ) -> str:
        normalized_project_theme = (
            project_theme.strip()
        )

        if normalized_project_theme:
            return normalized_project_theme

        theme_hint = str(
            getattr(
                source_profile,
                "theme_hint",
                "",
            )
            or ""
        ).strip()

        if theme_hint:
            return theme_hint

        community = str(
            getattr(
                source_profile,
                "community",
                "",
            )
            or ""
        ).strip()

        humanized_community = self._humanize_identifier(
            community
        )

        if humanized_community:
            return humanized_community

        return "general short-form clips"

    def _humanize_identifier(
        self,
        value: str,
    ) -> str:
        without_prefix = re.sub(
            r"^r/",
            "",
            value.strip(),
            flags=re.IGNORECASE,
        )

        separated_camel_case = re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])",
            " ",
            without_prefix,
        )

        separated_words = re.sub(
            r"[_\-]+",
            " ",
            separated_camel_case,
        )

        return re.sub(
            r"\s+",
            " ",
            separated_words,
        ).strip().lower()