from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from app.analyze.analysis_models import MediaInfo
from app.sources.source_models import SourceCandidate


class TargetPlatform(str, Enum):
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"


class VideoFormat(str, Enum):
    RANKING = "ranking"
    MEME = "meme"
    COMPILATION = "compilation"


class AIFieldPermissions(BaseModel):
    """
    Explicitly defines what an AI provider is allowed to influence.

    Preset styling remains locked unless a field is explicitly enabled.
    """

    allow_header_text: bool = True
    allow_ranking_captions: bool = True

    allow_clip_reordering: bool = False
    allow_trim_suggestions: bool = True

    allow_transition_selection: bool = False
    allow_style_changes: bool = False
    allow_duration_rule_changes: bool = False


class ClipAnalysisRequest(BaseModel):
    clip_id: str
    local_path: Path

    candidate: SourceCandidate
    media_info: MediaInfo

    preset_id: str
    target_platform: TargetPlatform
    video_format: VideoFormat

    theme: str
    desired_caption_style: str = ""

    permissions: AIFieldPermissions = Field(
        default_factory=AIFieldPermissions
    )


class ClipAnalysisResult(BaseModel):
    clip_id: str

    summary: str = ""
    detected_theme: str = ""

    usable: bool = False

    topic_match_score: int = Field(default=0, ge=0, le=10)
    quality_score: int = Field(default=0, ge=0, le=10)
    hook_score: int = Field(default=0, ge=0, le=10)

    ranking_caption: str = ""

    suggested_trim_start_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    suggested_trim_end_seconds: float | None = Field(
        default=None,
        ge=0,
    )

    contains_watermark: bool = False
    contains_embedded_text: bool = False
    contains_sensitive_content: bool = False

    rejection_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ProjectCreativeRequest(BaseModel):
    project_name: str
    preset_id: str

    target_platform: TargetPlatform
    video_format: VideoFormat

    source_profile_id: str
    community: str
    theme: str

    target_duration_seconds: float = 65.0
    min_duration_seconds: float = 60.0
    max_duration_seconds: float = 90.0

    clip_analyses: list[ClipAnalysisResult] = Field(default_factory=list)

    permissions: AIFieldPermissions = Field(
        default_factory=AIFieldPermissions
    )


class ProjectCreativeResult(BaseModel):
    header_text: str = ""

    ranking_captions: dict[str, str] = Field(default_factory=dict)

    recommended_clip_order: list[str] = Field(default_factory=list)

    overall_theme: str = ""
    warnings: list[str] = Field(default_factory=list)


class FinalVideoReviewRequest(BaseModel):
    project_name: str
    preset_id: str

    video_path: Path
    media_info: MediaInfo

    expected_header_text: str = ""
    expected_ranking_captions: list[str] = Field(default_factory=list)

    target_platform: TargetPlatform
    theme: str


class FinalVideoReviewResult(BaseModel):
    approved_for_upload: bool = False

    overall_quality_score: int = Field(default=0, ge=0, le=10)
    hook_score: int = Field(default=0, ge=0, le=10)
    pacing_score: int = Field(default=0, ge=0, le=10)

    header_matches_content: bool = False
    captions_match_clips: bool = False
    visual_quality_ok: bool = False
    audio_quality_ok: bool = False

    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)