from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from app.core.preset_config import PresetConfig


class SegmentType(str, Enum):
    MAIN_CLIP = "main_clip"
    INTERSTITIAL_CLIP = "interstitial_clip"
    PRESET_INTERSTITIAL = "preset_interstitial"


class RenderSegment(BaseModel):
    segment_type: SegmentType
    path: Path
    additional_audio_path: Optional[Path] = None
    rank_index: Optional[int] = None
    caption: str = ""
    show_ranking_overlay: bool = False


class RenderPlan(BaseModel):
    project_name: str
    preset_id: str
    preset_config: PresetConfig
    output_path: Path
    segments: list[RenderSegment]