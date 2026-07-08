from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.core.render_plan import RenderPlan
from app.render.overlay_image_builder import OverlayImageBuilder


class FFmpegRenderError(Exception):
    pass


class FFmpegRenderer:
    """
    MVP renderer.

    - normalize every segment to preset resolution
    - guarantee every segment has an AAC audio track
    - optionally burn ranking overlay into main clips
    - concat all clips with concat filter instead of stream copy

    Why concat filter?
        The concat demuxer with "-c copy" can behave badly when some clips
        originally had audio and others did not. Re-encoding the final concat
        is more stable for weird downloaded/social-media MP4s.
    """

    def __init__(
        self,
        temp_dir: Path = Path("data/temp"),
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.temp_dir = temp_dir
        self.width = width
        self.height = height
        self.fps = fps
        self.log_callback = log_callback
        self.overlay_builder = OverlayImageBuilder(width=width, height=height)

        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def render(self, render_plan: RenderPlan) -> Path:
        self.width = render_plan.preset_config.width
        self.height = render_plan.preset_config.height
        self.fps = render_plan.preset_config.fps
        self.overlay_builder = OverlayImageBuilder(width=self.width, height=self.height)

        self._ensure_ffmpeg_available()

        project_temp_dir = self.temp_dir / f"{render_plan.project_name}_{render_plan.preset_id}"

        if project_temp_dir.exists():
            shutil.rmtree(project_temp_dir)

        project_temp_dir.mkdir(parents=True, exist_ok=True)

        ranked_segments = [
            segment
            for segment in render_plan.segments
            if segment.rank_index is not None
        ]

        overlay_style = render_plan.preset_config.ranking_overlay

        final_segment_paths: list[Path] = []
        total_segments = len(render_plan.segments)

        for index, segment in enumerate(render_plan.segments, start=1):
            self._log(f"[{index}/{total_segments}] Normalisiere: {segment.path.name}")

            normalized_path = project_temp_dir / f"normalized_{index:03d}.mp4"
            final_segment_path = project_temp_dir / f"segment_{index:03d}.mp4"

            self._normalize_clip(segment.path, normalized_path)

            if segment.show_ranking_overlay and overlay_style.enabled:
                self._log(f"[{index}/{total_segments}] Ranking-Overlay wird eingebrannt.")

                overlay_path = project_temp_dir / f"overlay_{index:03d}.png"
                self.overlay_builder.build_ranking_overlay(
                    output_path=overlay_path,
                    ranked_segments=ranked_segments,
                    style=overlay_style,
                    current_rank_index=segment.rank_index,
                )

                self._burn_overlay(
                    input_path=normalized_path,
                    overlay_path=overlay_path,
                    output_path=final_segment_path,
                )
            else:
                shutil.copy2(normalized_path, final_segment_path)

            final_segment_paths.append(final_segment_path)

        render_plan.output_path.parent.mkdir(parents=True, exist_ok=True)

        self._log("Finales Video wird stabil zusammengesetzt.")
        self._concat_clips_with_filter(final_segment_paths, render_plan.output_path)

        self._log(f"Fertig: {render_plan.output_path}")
        return render_plan.output_path

    def _log(self, message: str) -> None:
        if self.log_callback is not None:
            self.log_callback(message)

    def _ensure_ffmpeg_available(self) -> None:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            shell=False,
        )

        if result.returncode != 0:
            raise FFmpegRenderError(
                "FFmpeg wurde nicht gefunden. Prüfe, ob ffmpeg im PATH ist."
            )

    def _has_audio_stream(self, input_path: Path) -> bool:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            shell=False,
        )

        return bool(result.stdout.strip())

    def _get_video_duration_seconds(self, input_path: Path) -> float | None:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            shell=False,
        )

        raw_value = result.stdout.strip()

        if not raw_value or raw_value == "N/A":
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(input_path),
                ],
                capture_output=True,
                text=True,
                shell=False,
            )

            raw_value = result.stdout.strip()

        try:
            duration = float(raw_value)
        except ValueError:
            return None

        if duration <= 0:
            return None

        return duration

    def _normalize_clip(self, input_path: Path, output_path: Path) -> None:
        if not input_path.exists():
            raise FFmpegRenderError(f"Input-Datei existiert nicht: {input_path}")

        has_audio = self._has_audio_stream(input_path)
        duration = self._get_video_duration_seconds(input_path)

        video_filter = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
            f"crop={self.width}:{self.height},"
            f"setsar=1,"
            f"fps={self.fps},"
            f"format=yuv420p"
        )

        if has_audio:
            self._log(f"Audio erkannt: {input_path.name}")

            command = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-dn",
                "-sn",
                "-vf",
                video_filter,
                "-af",
                "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]

            if duration is not None:
                command.extend(["-t", f"{duration:.3f}"])

            command.extend(
                [
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )

        else:
            self._log(f"Kein Audio erkannt: Silent Audio wird erzeugt für {input_path.name}")

            command = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
            ]

            if duration is not None:
                command.extend(
                    [
                        "-f",
                        "lavfi",
                        "-t",
                        f"{duration:.3f}",
                        "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=48000",
                    ]
                )
            else:
                command.extend(
                    [
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=48000",
                    ]
                )

            command.extend(
                [
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-dn",
                    "-sn",
                    "-vf",
                    video_filter,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )

        self._run(command, label=f"Normalizing {input_path.name}")

    def _burn_overlay(
        self,
        input_path: Path,
        overlay_path: Path,
        output_path: Path,
    ) -> None:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-loop",
            "1",
            "-i",
            str(overlay_path),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
            "-map",
            "[v]",
            "-map",
            "0:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        self._run(command, label=f"Burning overlay into {input_path.name}")

    def _concat_clips_with_filter(self, paths: list[Path], output_path: Path) -> None:
        if not paths:
            raise FFmpegRenderError("Keine Segmente zum Zusammenfügen vorhanden.")

        command = ["ffmpeg", "-y"]

        for path in paths:
            command.extend(["-i", str(path)])

        filter_parts: list[str] = []

        for index in range(len(paths)):
            filter_parts.append(
                f"[{index}:v:0]setpts=PTS-STARTPTS,format=yuv420p[v{index}]"
            )
            filter_parts.append(
                f"[{index}:a:0]asetpts=PTS-STARTPTS,aresample=48000[a{index}]"
            )

        concat_inputs = "".join(
            f"[v{index}][a{index}]"
            for index in range(len(paths))
        )

        filter_parts.append(
            f"{concat_inputs}concat=n={len(paths)}:v=1:a=1[v][a]"
        )

        filter_complex = ";".join(filter_parts)

        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

        self._run(command, label="Concatenating final video with filter")

    def _run(self, command: list[str], label: str) -> None:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False,
        )

        if result.returncode != 0:
            raise FFmpegRenderError(
                f"{label} failed.\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )