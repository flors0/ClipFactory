from __future__ import annotations

from app.analyze.analysis_models import RenderPlanAnalysis, SegmentAnalysis
from app.analyze.media_probe import MediaProbe
from app.core.render_plan import RenderPlan


class RenderPlanAnalyzer:
    def __init__(
        self,
        media_probe: MediaProbe | None = None,
    ) -> None:
        self.media_probe = media_probe or MediaProbe()

    def analyze(self, render_plan: RenderPlan) -> RenderPlanAnalysis:
        segments: list[SegmentAnalysis] = []
        warnings: list[str] = []

        estimated_duration_seconds = 0.0

        for index, segment in enumerate(render_plan.segments, start=1):
            media_info = self.media_probe.probe(segment.path)

            additional_audio_info = None

            if segment.additional_audio_path is not None:
                additional_audio_info = self.media_probe.probe(segment.additional_audio_path)

            segment_analysis = SegmentAnalysis(
                index=index,
                segment_type=self._human_segment_type(segment.segment_type.value),
                path=segment.path,
                rank_index=segment.rank_index,
                caption=segment.caption,
                show_ranking_overlay=segment.show_ranking_overlay,
                media_info=media_info,
                additional_audio_info=additional_audio_info,
            )

            segments.append(segment_analysis)

            if media_info.duration_seconds is not None:
                estimated_duration_seconds += media_info.duration_seconds
            else:
                warnings.append(
                    f"Could not determine duration for segment {index}: {segment.path.name}"
                )

            for media_warning in media_info.warnings:
                warnings.append(f"Segment {index}: {media_warning}")

            if additional_audio_info is not None:
                for audio_warning in additional_audio_info.warnings:
                    warnings.append(f"Segment {index} additional audio: {audio_warning}")

            if not media_info.has_audio and additional_audio_info is None:
                warnings.append(
                    f"Segment {index} has no audio. Renderer will create silent audio."
                )

            if media_info.duration_seconds is not None and media_info.duration_seconds < 0.5:
                warnings.append(
                    f"Segment {index} is very short ({media_info.duration_seconds:.2f}s)."
                )

        platform_rules = render_plan.preset_config.platform_rules

        target_duration_seconds = platform_rules.target_duration_seconds
        min_duration_seconds = platform_rules.min_duration_seconds
        max_duration_seconds = platform_rules.max_duration_seconds
        duration_enforcement = platform_rules.duration_enforcement.strip().lower()

        if duration_enforcement not in {"warn", "block", "auto_extend"}:
            warnings.append(
                f"Unknown duration enforcement mode '{duration_enforcement}'. Falling back to warn."
            )
            duration_enforcement = "warn"

        duration_too_short = estimated_duration_seconds < min_duration_seconds
        duration_too_long = estimated_duration_seconds > max_duration_seconds

        if duration_too_short:
            warnings.append(
                f"Final duration is below the minimum duration "
                f"({estimated_duration_seconds:.2f}s < {min_duration_seconds:.2f}s)."
            )

        if duration_too_long:
            warnings.append(
                f"Final duration is above the maximum duration "
                f"({estimated_duration_seconds:.2f}s > {max_duration_seconds:.2f}s)."
            )

        if duration_enforcement == "auto_extend" and (duration_too_short or duration_too_long):
            warnings.append(
                "Duration enforcement is set to auto_extend, but auto_extend is not implemented yet. "
                "For now this behaves like warn."
            )

        should_block_render = (
            duration_enforcement == "block"
            and (duration_too_short or duration_too_long)
        )

        return RenderPlanAnalysis(
            project_name=render_plan.project_name,
            preset_id=render_plan.preset_id,
            segments=segments,
            estimated_duration_seconds=estimated_duration_seconds,
            target_duration_seconds=target_duration_seconds,
            min_duration_seconds=min_duration_seconds,
            max_duration_seconds=max_duration_seconds,
            duration_enforcement=duration_enforcement,
            should_block_render=should_block_render,
            warnings=warnings,
        )

    def _human_segment_type(self, raw_type: str) -> str:
        mapping = {
            "main_clip": "Main Clip",
            "interstitial_clip": "Manual Interstitial",
            "preset_interstitial": "Preset Interstitial",
        }

        return mapping.get(raw_type, raw_type)