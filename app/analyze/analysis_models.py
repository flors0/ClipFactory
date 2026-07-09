from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class MediaInfo(BaseModel):
    path: Path
    exists: bool = True

    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None

    has_video: bool = False
    has_audio: bool = False

    video_codec: str = ""
    audio_codec: str = ""

    warnings: list[str] = Field(default_factory=list)

    def duration_label(self) -> str:
        if self.duration_seconds is None:
            return "unknown"

        return f"{self.duration_seconds:.2f}s"

    def resolution_label(self) -> str:
        if self.width is None or self.height is None:
            return "unknown"

        return f"{self.width}x{self.height}"

    def fps_label(self) -> str:
        if self.fps is None:
            return "unknown"

        return f"{self.fps:.2f}"


class SegmentAnalysis(BaseModel):
    index: int
    segment_type: str
    path: Path

    rank_index: Optional[int] = None
    caption: str = ""
    show_ranking_overlay: bool = False

    media_info: MediaInfo
    additional_audio_info: Optional[MediaInfo] = None

    @property
    def duration_seconds(self) -> float:
        return self.media_info.duration_seconds or 0.0


class RenderPlanAnalysis(BaseModel):
    project_name: str
    preset_id: str

    segments: list[SegmentAnalysis] = Field(default_factory=list)
    estimated_duration_seconds: float = 0.0

    target_duration_seconds: float = 60.0
    min_duration_seconds: float = 55.0
    max_duration_seconds: float = 75.0
    duration_enforcement: str = "warn"

    should_block_render: bool = False

    warnings: list[str] = Field(default_factory=list)

    def estimated_duration_label(self) -> str:
        return self._duration_label(self.estimated_duration_seconds)

    def _duration_label(self, value: float) -> str:
        minutes = int(value // 60)
        seconds = value % 60

        if minutes <= 0:
            return f"{seconds:.2f}s"

        return f"{minutes}m {seconds:.2f}s"

    def to_log_lines(self) -> list[str]:
        lines: list[str] = []

        lines.append("Render plan summary:")
        lines.append(f"Project: {self.project_name}")
        lines.append(f"Preset: {self.preset_id}")
        lines.append(f"Segments: {len(self.segments)}")

        lines.append(
            "Duration rules: "
            f"target {self._duration_label(self.target_duration_seconds)}, "
            f"min {self._duration_label(self.min_duration_seconds)}, "
            f"max {self._duration_label(self.max_duration_seconds)}, "
            f"enforcement: {self.duration_enforcement}"
        )

        for segment in self.segments:
            media = segment.media_info

            caption_part = ""
            if segment.caption.strip():
                caption_part = f" - Caption: {segment.caption.strip()}"

            rank_part = ""
            if segment.show_ranking_overlay and segment.rank_index is not None:
                rank_part = f" - Rank: {segment.rank_index}"

            additional_audio_part = ""
            if segment.additional_audio_info is not None:
                additional_audio = segment.additional_audio_info
                additional_audio_part = (
                    f" - Additional audio: yes "
                    f"({additional_audio.duration_label()})"
                )

            lines.append(
                f"{segment.index}. {segment.segment_type} - "
                f"{media.duration_label()} - "
                f"{media.resolution_label()} - "
                f"FPS: {media.fps_label()} - "
                f"Audio: {'yes' if media.has_audio else 'no'}"
                f"{rank_part}"
                f"{caption_part}"
                f"{additional_audio_part}"
            )

        lines.append(f"Estimated final duration: {self.estimated_duration_label()}")

        for warning in self.warnings:
            lines.append(f"Warning: {warning}")

        if self.should_block_render:
            lines.append("Render blocked by platform rules.")

        return lines