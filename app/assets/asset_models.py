from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    TRANSITION = "transition"
    INTERSTITIAL = "interstitial"
    SOUND = "sound"
    MUSIC = "music"
    FONT = "font"
    MEME = "meme"
    UNKNOWN = "unknown"


class AssetInfo(BaseModel):
    id: str
    asset_type: AssetType

    path: Path
    filename: str
    suffix: str

    tags: list[str] = Field(default_factory=list)

    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None

    has_video: bool = False
    has_audio: bool = False

    video_codec: str = ""
    audio_codec: str = ""

    is_valid: bool = True
    warnings: list[str] = Field(default_factory=list)

    def duration_label(self) -> str:
        if self.duration_seconds is None:
            return "unknown"

        return f"{self.duration_seconds:.2f}s"

    def resolution_label(self) -> str:
        if self.width is None or self.height is None:
            return "unknown"

        return f"{self.width}x{self.height}"


class AssetLibrary(BaseModel):
    assets: list[AssetInfo] = Field(default_factory=list)

    def count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}

        for asset in self.assets:
            key = asset.asset_type.value
            counts[key] = counts.get(key, 0) + 1

        return counts

    def assets_by_type(self, asset_type: AssetType) -> list[AssetInfo]:
        return [
            asset
            for asset in self.assets
            if asset.asset_type == asset_type
        ]

    def to_log_lines(self) -> list[str]:
        lines: list[str] = []

        lines.append("Asset library summary:")
        lines.append(f"Assets found: {len(self.assets)}")

        counts = self.count_by_type()

        if not counts:
            lines.append("No assets found.")
            return lines

        for asset_type, count in sorted(counts.items()):
            lines.append(f"- {asset_type}: {count}")

        invalid_assets = [
            asset
            for asset in self.assets
            if not asset.is_valid
        ]

        if invalid_assets:
            lines.append(f"Invalid assets: {len(invalid_assets)}")

            for asset in invalid_assets[:10]:
                lines.append(f"Warning: Invalid asset: {asset.path}")

        return lines