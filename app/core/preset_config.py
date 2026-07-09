from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class RankingOverlayConfig(BaseModel):
    enabled: bool = True
    mode: str = "progressive_reveal"

    x_number: int = 60
    x_caption: int = 185
    y_start: int = 170
    line_height: int = 88

    number_font_size: int = 76
    caption_font_size: int = 56

    number_font_path: str = ""
    caption_font_path: str = ""

    number_colors: dict[str, str] = Field(
        default_factory=lambda: {
            "default": "#FFD700"
        }
    )

    caption_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    shadow_color: str = "#000000"

    number_stroke_width: int = 4
    caption_stroke_width: int = 2

    shadow_offset_x: int = 3
    shadow_offset_y: int = 3


class PresetInterstitialConfig(BaseModel):
    enabled: bool = False
    path: str = ""
    insert_between_main_clips: bool = True


class PresetConfig(BaseModel):
    id: str
    name: str
    resolution: list[int] = Field(default_factory=lambda: [1080, 1920])
    fps: int = 30
    ranking_overlay: RankingOverlayConfig = Field(default_factory=RankingOverlayConfig)
    preset_interstitial: PresetInterstitialConfig = Field(default_factory=PresetInterstitialConfig)

    @property
    def width(self) -> int:
        return int(self.resolution[0])

    @property
    def height(self) -> int:
        return int(self.resolution[1])


def load_preset_config(
    preset_id: str,
    presets_dir: Path = Path("app/presets"),
) -> PresetConfig:
    preset_path = presets_dir / f"{preset_id}.json"

    if not preset_path.exists():
        raise FileNotFoundError(f"Preset not found: {preset_path}")

    data = json.loads(preset_path.read_text(encoding="utf-8"))
    return PresetConfig(**data)