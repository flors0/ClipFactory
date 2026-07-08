from __future__ import annotations

from pathlib import Path

from app.core.models import ProjectData
from app.core.preset_config import PresetConfig, load_preset_config
from app.core.render_plan import RenderPlan, RenderSegment, SegmentType


class TimelineBuilder:
    def build(self, project: ProjectData) -> RenderPlan:
        preset_config = load_preset_config(project.preset_id)

        active_slots = project.active_slots()
        segments: list[RenderSegment] = []

        show_ranking_overlay = preset_config.ranking_overlay.enabled

        for slot_index, slot in enumerate(active_slots):
            if slot.main_source.resolved_path is None:
                raise ValueError(f"Main clip in slot {slot.index} is not resolved.")

            segments.append(
                RenderSegment(
                    segment_type=SegmentType.MAIN_CLIP,
                    path=slot.main_source.resolved_path,
                    rank_index=slot.index,
                    caption=slot.caption,
                    show_ranking_overlay=show_ranking_overlay,
                )
            )

            if slot.after_source.resolved_path is not None:
                segments.append(
                    RenderSegment(
                        segment_type=SegmentType.AFTER_CLIP,
                        path=slot.after_source.resolved_path,
                        rank_index=None,
                        caption="",
                        show_ranking_overlay=False,
                    )
                )

            is_last_main_slot = slot_index == len(active_slots) - 1

            if not is_last_main_slot:
                interstitial_segment = self._build_preset_interstitial_segment(
                    preset_config=preset_config,
                )

                if interstitial_segment is not None:
                    segments.append(interstitial_segment)

        return RenderPlan(
            project_name=project.project_name,
            preset_id=project.preset_id,
            preset_config=preset_config,
            output_path=Path("data/output") / f"{project.project_name}_{project.preset_id}.mp4",
            segments=segments,
        )

    def _build_preset_interstitial_segment(
        self,
        preset_config: PresetConfig,
    ) -> RenderSegment | None:
        interstitial = preset_config.preset_interstitial

        if not interstitial.enabled:
            return None

        if not interstitial.insert_between_main_clips:
            return None

        if not interstitial.path.strip():
            raise ValueError(
                f"Preset '{preset_config.id}' hat preset_interstitial aktiviert, "
                "aber keinen Pfad gesetzt."
            )

        interstitial_path = Path(interstitial.path)

        if not interstitial_path.exists():
            raise ValueError(
                f"Preset-Interstitial wurde nicht gefunden: {interstitial_path}"
            )

        return RenderSegment(
            segment_type=SegmentType.PRESET_INTERSTITIAL,
            path=interstitial_path,
            rank_index=None,
            caption="",
            show_ranking_overlay=False,
        )