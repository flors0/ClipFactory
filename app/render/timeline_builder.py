from __future__ import annotations

import re
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
            output_path=self._build_safe_output_path(
                project_name=project.project_name,
                preset_id=project.preset_id,
            ),
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

    def _build_safe_output_path(
        self,
        project_name: str,
        preset_id: str,
    ) -> Path:
        output_dir = Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_project_name = self._safe_filename_part(project_name) or "clipfactory_project"
        safe_preset_id = self._safe_filename_part(preset_id) or "preset"

        base_name = f"{safe_project_name}_{safe_preset_id}"
        candidate = output_dir / f"{base_name}.mp4"

        if not candidate.exists():
            return candidate

        for counter in range(1, 10_000):
            numbered_candidate = output_dir / f"{base_name}_{counter:03d}.mp4"

            if not numbered_candidate.exists():
                return numbered_candidate

        raise RuntimeError("Konnte keinen freien Output-Dateinamen erzeugen.")

    def _safe_filename_part(self, value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9_-]+", "_", cleaned)
        cleaned = cleaned.strip("_")
        return cleaned