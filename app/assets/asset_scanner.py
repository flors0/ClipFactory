from __future__ import annotations

import re
from pathlib import Path

from app.analyze.media_probe import MediaProbe
from app.assets.asset_models import AssetInfo, AssetLibrary, AssetType


class AssetScanner:
    VIDEO_EXTENSIONS = {
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
    }

    AUDIO_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".flac",
    }

    FONT_EXTENSIONS = {
        ".ttf",
        ".otf",
    }

    ASSET_FOLDERS = {
        AssetType.TRANSITION: Path("assets/transitions"),
        AssetType.INTERSTITIAL: Path("assets/interstitials"),
        AssetType.SOUND: Path("assets/sounds"),
        AssetType.MUSIC: Path("assets/music"),
        AssetType.FONT: Path("assets/fonts"),
        AssetType.MEME: Path("assets/memes"),
    }

    def __init__(
        self,
        media_probe: MediaProbe | None = None,
    ) -> None:
        self.media_probe = media_probe or MediaProbe()

    def scan(self) -> AssetLibrary:
        assets: list[AssetInfo] = []
        used_ids: set[str] = set()

        for asset_type, folder in self.ASSET_FOLDERS.items():
            folder.mkdir(parents=True, exist_ok=True)

            for path in sorted(folder.rglob("*")):
                if not path.is_file():
                    continue

                if not self._is_supported_file(path):
                    continue

                asset = self._build_asset_info(
                    path=path,
                    asset_type=asset_type,
                    used_ids=used_ids,
                )

                used_ids.add(asset.id)
                assets.append(asset)

        return AssetLibrary(assets=assets)

    def _build_asset_info(
        self,
        path: Path,
        asset_type: AssetType,
        used_ids: set[str],
    ) -> AssetInfo:
        suffix = path.suffix.lower()
        asset_id = self._create_asset_id(
            path=path,
            asset_type=asset_type,
            used_ids=used_ids,
        )

        tags = self._build_tags(path=path, asset_type=asset_type)

        if suffix in self.FONT_EXTENSIONS:
            return AssetInfo(
                id=asset_id,
                asset_type=asset_type,
                path=self._project_relative_path(path),
                filename=path.name,
                suffix=suffix,
                tags=tags,
                has_video=False,
                has_audio=False,
                is_valid=True,
            )

        media_info = self.media_probe.probe(path)

        warnings = list(media_info.warnings)
        is_valid = media_info.exists

        if suffix in self.VIDEO_EXTENSIONS and not media_info.has_video:
            is_valid = False
            warnings.append("Expected a video file, but no video stream was found.")

        if suffix in self.AUDIO_EXTENSIONS and not media_info.has_audio:
            is_valid = False
            warnings.append("Expected an audio file, but no audio stream was found.")

        return AssetInfo(
            id=asset_id,
            asset_type=asset_type,
            path=self._project_relative_path(path),
            filename=path.name,
            suffix=suffix,
            tags=tags,
            duration_seconds=media_info.duration_seconds,
            width=media_info.width,
            height=media_info.height,
            fps=media_info.fps,
            has_video=media_info.has_video,
            has_audio=media_info.has_audio,
            video_codec=media_info.video_codec,
            audio_codec=media_info.audio_codec,
            is_valid=is_valid,
            warnings=warnings,
        )

    def _is_supported_file(self, path: Path) -> bool:
        suffix = path.suffix.lower()

        return (
            suffix in self.VIDEO_EXTENSIONS
            or suffix in self.AUDIO_EXTENSIONS
            or suffix in self.FONT_EXTENSIONS
        )

    def _create_asset_id(
        self,
        path: Path,
        asset_type: AssetType,
        used_ids: set[str],
    ) -> str:
        base_slug = self._slugify(path.stem)

        if not base_slug:
            base_slug = "asset"

        base_id = f"{asset_type.value}_{base_slug}"
        candidate = base_id
        counter = 2

        while candidate in used_ids:
            candidate = f"{base_id}_{counter:02d}"
            counter += 1

        return candidate

    def _build_tags(
        self,
        path: Path,
        asset_type: AssetType,
    ) -> list[str]:
        tags: set[str] = set()

        tags.add(asset_type.value)

        relative_parts = list(path.parts)

        for part in relative_parts:
            if part.lower() in {"assets", path.name.lower()}:
                continue

            for token in self._tokenize(part):
                tags.add(token)

        for token in self._tokenize(path.stem):
            tags.add(token)

        return sorted(tags)

    def _tokenize(self, value: str) -> list[str]:
        cleaned = value.lower()
        parts = re.split(r"[^a-z0-9]+", cleaned)

        return [
            part
            for part in parts
            if part
        ]

    def _slugify(self, value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = cleaned.strip("_")

        return cleaned

    def _project_relative_path(self, path: Path) -> Path:
        try:
            return path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            return path.resolve()