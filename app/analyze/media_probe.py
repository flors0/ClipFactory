from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.analyze.analysis_models import MediaInfo


class MediaProbeError(Exception):
    pass


class MediaProbe:
    def probe(self, path: Path) -> MediaInfo:
        if not path.exists():
            return MediaInfo(
                path=path,
                exists=False,
                warnings=[f"File does not exist: {path}"],
            )

        command = [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=False,
            )
        except FileNotFoundError as error:
            raise MediaProbeError(
                "ffprobe was not found. Make sure ffprobe is installed and available in PATH."
            ) from error

        if result.returncode != 0:
            return MediaInfo(
                path=path,
                exists=True,
                warnings=[
                    f"ffprobe failed for {path.name}",
                    result.stderr.strip(),
                ],
            )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return MediaInfo(
                path=path,
                exists=True,
                warnings=[f"Could not parse ffprobe output for {path.name}"],
            )

        streams = data.get("streams", [])
        format_data = data.get("format", {})

        video_stream = self._first_stream_of_type(streams, "video")
        audio_stream = self._first_stream_of_type(streams, "audio")

        duration = self._parse_duration(format_data, video_stream, audio_stream)

        width = None
        height = None
        fps = None
        video_codec = ""

        if video_stream is not None:
            width = self._safe_int(video_stream.get("width"))
            height = self._safe_int(video_stream.get("height"))
            fps = self._parse_fps(
                video_stream.get("avg_frame_rate")
                or video_stream.get("r_frame_rate")
            )
            video_codec = str(video_stream.get("codec_name", ""))

        audio_codec = ""

        if audio_stream is not None:
            audio_codec = str(audio_stream.get("codec_name", ""))

        return MediaInfo(
            path=path,
            exists=True,
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            has_video=video_stream is not None,
            has_audio=audio_stream is not None,
            video_codec=video_codec,
            audio_codec=audio_codec,
        )

    def _first_stream_of_type(
        self,
        streams: list[dict],
        codec_type: str,
    ) -> dict | None:
        for stream in streams:
            if stream.get("codec_type") == codec_type:
                return stream

        return None

    def _parse_duration(
        self,
        format_data: dict,
        video_stream: dict | None,
        audio_stream: dict | None,
    ) -> float | None:
        candidates = [
            format_data.get("duration"),
        ]

        if video_stream is not None:
            candidates.append(video_stream.get("duration"))

        if audio_stream is not None:
            candidates.append(audio_stream.get("duration"))

        for candidate in candidates:
            duration = self._safe_float(candidate)

            if duration is not None and duration > 0:
                return duration

        return None

    def _parse_fps(self, raw_value: str | None) -> float | None:
        if not raw_value:
            return None

        if "/" not in raw_value:
            return self._safe_float(raw_value)

        numerator_raw, denominator_raw = raw_value.split("/", 1)

        numerator = self._safe_float(numerator_raw)
        denominator = self._safe_float(denominator_raw)

        if numerator is None or denominator is None or denominator == 0:
            return None

        return numerator / denominator

    def _safe_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _safe_float(self, value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None