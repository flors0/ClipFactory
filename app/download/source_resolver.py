from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.core.models import SourceInput, SourceType


class SourceResolveError(Exception):
    pass


class SourceResolver:
    """
    Converts user input into stable local files.

    URL:
        Downloads with yt-dlp into data/downloads.
        Uses a cache key based on the URL.

    Local file:
        Copies into data/downloads.
        Uses a cache key based on absolute path + size + modified timestamp.

    Why cache?
        The renderer should always work with local files, but we do not want to
        re-download or re-copy the same source on every render.
    """

    def __init__(
        self,
        download_dir: Path,
        cache_file: Path | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = cache_file or self.download_dir / "source_cache.json"
        self.log_callback = log_callback

        self.cache = self._load_cache()

    def resolve(self, source: SourceInput, name_hint: str) -> SourceInput:
        if source.source_type == SourceType.EMPTY:
            return source

        if source.source_type == SourceType.LOCAL_FILE:
            return self._resolve_local_file(source, name_hint)

        if source.source_type == SourceType.URL:
            return self._resolve_url(source, name_hint)

        raise SourceResolveError(f"Unsupported source type: {source.source_type}")

    def _resolve_local_file(self, source: SourceInput, name_hint: str) -> SourceInput:
        raw_path = self._clean_raw_value(source.raw_value)
        input_path = Path(raw_path).expanduser()

        if not input_path.exists():
            raise SourceResolveError(f"Lokale Datei existiert nicht: {input_path}")

        cache_key = self._build_local_cache_key(input_path)
        cached_path = self._get_cached_path(cache_key)

        if cached_path is not None:
            self._log(f"Local Cache Hit: {cached_path}")
            source.resolved_path = cached_path
            return source

        self._log(f"Local Cache Miss: {input_path.name} wird kopiert...")

        suffix = input_path.suffix or ".mp4"
        output_path = self.download_dir / f"local_{cache_key[:12]}{suffix}"

        shutil.copy2(input_path, output_path)

        self._write_cache_entry(
            cache_key=cache_key,
            raw_value=source.raw_value,
            source_type=source.source_type.value,
            resolved_path=output_path,
        )

        self._log(f"Lokale Datei gecached: {output_path}")

        source.resolved_path = output_path
        return source

    def _resolve_url(self, source: SourceInput, name_hint: str) -> SourceInput:
        url = self._clean_raw_value(source.raw_value)

        cache_key = self._build_url_cache_key(url)
        cached_path = self._get_cached_path(cache_key)

        if cached_path is not None:
            self._log(f"Download Cache Hit: {cached_path}")
            source.resolved_path = cached_path
            return source

        self._log(f"Download Cache Miss: URL wird geladen ({name_hint})...")

        file_prefix = f"url_{cache_key[:12]}"
        output_template = str(self.download_dir / f"{file_prefix}.%(ext)s")

        self._remove_old_partial_files(file_prefix=file_prefix)

        command = [
            "uv",
            "run",
            "python",
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "-f",
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best[ext=mp4]/best",
            "-o",
            output_template,
            url,
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False,
        )

        if result.returncode != 0:
            raise SourceResolveError(
                "yt-dlp konnte die URL nicht laden.\n\n"
                f"URL:\n{url}\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

        downloaded_path = self._find_downloaded_file(file_prefix=file_prefix)

        if downloaded_path is None:
            raise SourceResolveError(
                f"Download fertig, aber keine Datei gefunden für Prefix: {file_prefix}"
            )

        self._write_cache_entry(
            cache_key=cache_key,
            raw_value=source.raw_value,
            source_type=source.source_type.value,
            resolved_path=downloaded_path,
        )

        self._log(f"Download fertig: {downloaded_path}")

        source.resolved_path = downloaded_path
        return source

    def _load_cache(self) -> dict:
        if not self.cache_file.exists():
            return {}

        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_cache(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(
            json.dumps(self.cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_cache_entry(
        self,
        cache_key: str,
        raw_value: str,
        source_type: str,
        resolved_path: Path,
    ) -> None:
        self.cache[cache_key] = {
            "raw_value": raw_value,
            "source_type": source_type,
            "resolved_path": str(resolved_path),
        }

        self._save_cache()

    def _get_cached_path(self, cache_key: str) -> Path | None:
        entry = self.cache.get(cache_key)

        if not entry:
            return None

        resolved_path_raw = entry.get("resolved_path")

        if not resolved_path_raw:
            return None

        resolved_path = Path(resolved_path_raw)

        if not resolved_path.exists():
            return None

        return resolved_path

    def _build_url_cache_key(self, url: str) -> str:
        normalized = url.strip()
        return hashlib.sha256(f"url:{normalized}".encode("utf-8")).hexdigest()

    def _build_local_cache_key(self, input_path: Path) -> str:
        resolved_path = input_path.resolve()
        stat = resolved_path.stat()

        fingerprint = (
            f"local:{resolved_path.as_posix()}:"
            f"size={stat.st_size}:"
            f"mtime={stat.st_mtime_ns}"
        )

        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _find_downloaded_file(self, file_prefix: str) -> Path | None:
        candidates = [
            path
            for path in self.download_dir.glob(f"{file_prefix}.*")
            if path.is_file()
            and not path.name.endswith(".part")
            and not path.name.endswith(".ytdl")
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return candidates[0]

    def _remove_old_partial_files(self, file_prefix: str) -> None:
        for path in self.download_dir.glob(f"{file_prefix}.*"):
            if path.name.endswith(".part") or path.name.endswith(".ytdl"):
                path.unlink(missing_ok=True)

    def _clean_raw_value(self, value: str) -> str:
        return value.strip().strip('"').strip("'")

    def _log(self, message: str) -> None:
        if self.log_callback is not None:
            self.log_callback(message)