from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourcePlatform(str, Enum):
    REDDIT = "reddit"


class SourceSort(str, Enum):
    HOT = "hot"
    NEW = "new"
    TOP = "top"
    RISING = "rising"


class SourceTimeFilter(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL = "all"


class MediaKind(str, Enum):
    VIDEO = "video"
    GIF = "gif"
    IMAGE = "image"
    UNKNOWN = "unknown"


class RightsStatus(str, Enum):
    """
    Describes whether ClipFactory is allowed to use a candidate.

    UNKNOWN:
        No permission or license information is available.

    OWNED:
        The ClipFactory operator owns the content.

    PERMISSION_GRANTED:
        The creator explicitly granted permission.

    LICENSED:
        The content is covered by a suitable license.

    REJECTED:
        The content must not be used.
    """

    UNKNOWN = "unknown"
    OWNED = "owned"
    PERMISSION_GRANTED = "permission_granted"
    LICENSED = "licensed"
    REJECTED = "rejected"


class SourceProfile(BaseModel):
    """
    Reusable configuration describing where ClipFactory should search.

    Example:
        reddit_silly_cats
        reddit_fail_army
        reddit_funny_dogs
    """

    id: str
    name: str

    platform: SourcePlatform = SourcePlatform.REDDIT
    community: str

    theme_hint: str = ""
    content_language: str = "en"

    sort: SourceSort = SourceSort.TOP
    time_filter: SourceTimeFilter = SourceTimeFilter.WEEK

    candidate_limit: int = Field(default=50, ge=1, le=500)
    min_score: int = Field(default=0, ge=0)
    min_comment_count: int = Field(default=0, ge=0)

    max_post_age_hours: float | None = Field(default=None, gt=0)

    require_video: bool = True
    allow_gifs: bool = True
    allow_nsfw: bool = False
    allow_crossposts: bool = True

    allowed_flairs: list[str] = Field(default_factory=list)
    blocked_flairs: list[str] = Field(default_factory=list)

    @field_validator("community")
    @classmethod
    def normalize_community(cls, value: str) -> str:
        cleaned = value.strip()

        if cleaned.lower().startswith("r/"):
            cleaned = cleaned[2:]

        if not cleaned:
            raise ValueError("Community must not be empty.")

        return cleaned

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Source profile ID must not be empty.")

        return cleaned


class SourceCandidate(BaseModel):
    """
    A single post or media item discovered by a SourceProvider.
    """

    candidate_id: str
    source_profile_id: str

    platform: SourcePlatform
    community: str

    external_post_id: str
    title: str

    post_url: str
    media_url: str = ""

    media_kind: MediaKind = MediaKind.UNKNOWN
    thumbnail_url: str = ""

    author_name: str = ""
    created_utc: datetime | None = None

    score: int = 0
    comment_count: int = 0

    flair: str = ""
    is_nsfw: bool = False
    is_crosspost: bool = False

    rights_status: RightsStatus = RightsStatus.UNKNOWN
    permission_reference: str = ""
    credit_text: str = ""

    resolved_path: Path | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_approved_for_use(self) -> bool:
        return self.rights_status in {
            RightsStatus.OWNED,
            RightsStatus.PERMISSION_GRANTED,
            RightsStatus.LICENSED,
        }


class SourceCandidateBatch(BaseModel):
    source_profile: SourceProfile
    candidates: list[SourceCandidate] = Field(default_factory=list)

    scanned_count: int = 0
    filtered_count: int = 0

    warnings: list[str] = Field(default_factory=list)

    def to_log_lines(self) -> list[str]:
        lines = [
            "Source candidate summary:",
            f"Profile: {self.source_profile.name}",
            f"Platform: {self.source_profile.platform.value}",
            f"Community: r/{self.source_profile.community}",
            f"Posts scanned: {self.scanned_count}",
            f"Candidates accepted: {len(self.candidates)}",
            f"Candidates filtered: {self.filtered_count}",
        ]

        for warning in self.warnings:
            lines.append(f"Warning: {warning}")

        return lines