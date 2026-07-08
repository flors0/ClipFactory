from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.models import ClipSlot, ProjectData, SourceInput
from app.download.source_resolver import SourceResolveError, SourceResolver
from app.render.ffmpeg_renderer import FFmpegRenderer, FFmpegRenderError
from app.render.timeline_builder import TimelineBuilder
from app.ui.clip_slot_widget import ClipSlotWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("ClipFactory")
        self.resize(1100, 850)

        self.slot_widgets: list[ClipSlotWidget] = []

        self.project_name_input = QLineEdit("animal_ranking_001")

        self.preset_select = QComboBox()
        self.preset_select.addItem("YouTube Ranking", "youtube_ranking")
        self.preset_select.addItem("TikTok Meme", "tiktok_meme")

        self.render_video_button = QPushButton("Video rendern")
        self.render_video_button.clicked.connect(self._render_video)

        self.render_all_button = QPushButton("Alle Presets rendern")
        self.render_all_button.clicked.connect(self._render_all_presets)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Projektname"))
        top_layout.addWidget(self.project_name_input)
        top_layout.addWidget(QLabel("Preset"))
        top_layout.addWidget(self.preset_select)
        top_layout.addWidget(self.render_video_button)
        top_layout.addWidget(self.render_all_button)

        self.slots_layout = QVBoxLayout()
        self.slots_layout.addStretch()

        scroll_content = QWidget()
        scroll_content.setLayout(self.slots_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        self.log_view.setPlaceholderText("Logs erscheinen hier...")

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(QLabel("Logs"))
        main_layout.addWidget(self.log_view)

        root = QWidget()
        root.setLayout(main_layout)

        self.setCentralWidget(root)

        self._add_slot()
        self._log("ClipFactory gestartet.")

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)
        QApplication.processEvents()

    def _add_slot(self) -> None:
        index = len(self.slot_widgets) + 1
        widget = ClipSlotWidget(index=index)
        widget.changed.connect(self._on_slot_changed)

        self.slots_layout.insertWidget(self.slots_layout.count() - 1, widget)
        self.slot_widgets.append(widget)

    def _on_slot_changed(self) -> None:
        if not self.slot_widgets:
            return

        last_slot = self.slot_widgets[-1]

        if last_slot.has_main_value():
            self._add_slot()
            self._log(f"Slot {len(self.slot_widgets)} hinzugefügt.")

    def _available_preset_ids(self) -> list[str]:
        preset_ids: list[str] = []

        for index in range(self.preset_select.count()):
            preset_id = self.preset_select.itemData(index)

            if preset_id:
                preset_ids.append(str(preset_id))

        return preset_ids

    def _collect_project_data(self, preset_id: str | None = None) -> ProjectData:
        slots: list[ClipSlot] = []

        for widget in self.slot_widgets:
            values = widget.get_values()

            main_source = SourceInput.from_raw(values["main"])
            after_source = SourceInput.from_raw(values["after"])

            slot = ClipSlot(
                index=values["index"],
                main_source=main_source,
                caption=values["caption"],
                after_source=after_source,
            )

            slots.append(slot)

        selected_preset_id = preset_id or str(self.preset_select.currentData())

        return ProjectData(
            project_name=self.project_name_input.text().strip() or "clipfactory_project",
            preset_id=selected_preset_id,
            slots=slots,
        )

    def _resolve_project_sources(self, project: ProjectData) -> ProjectData:
        resolver = SourceResolver(
            download_dir=Path("data/downloads"),
            log_callback=self._log,
        )

        for slot in project.active_slots():
            self._log(f"Quelle wird vorbereitet: Slot {slot.index} Main Clip")

            slot.main_source = resolver.resolve(
                slot.main_source,
                name_hint=f"slot_{slot.index:02d}_main",
            )

            if slot.after_source.raw_value.strip():
                self._log(f"Quelle wird vorbereitet: Slot {slot.index} After Clip")

                slot.after_source = resolver.resolve(
                    slot.after_source,
                    name_hint=f"slot_{slot.index:02d}_after",
                )

        return project

    def _build_render_plan(self, preset_id: str | None = None):
        project = self._collect_project_data(preset_id=preset_id)

        if not project.active_slots():
            raise ValueError("Bitte mindestens einen Main Clip einfügen.")

        self._log(f"Preset: {project.preset_id}")
        self._log("Quellen werden aufgelöst...")

        project = self._resolve_project_sources(project)

        self._log("RenderPlan wird gebaut.")
        return TimelineBuilder().build(project)

    def _set_render_buttons_enabled(self, enabled: bool) -> None:
        self.render_video_button.setEnabled(enabled)
        self.render_all_button.setEnabled(enabled)

    def _render_video(self) -> None:
        self._set_render_buttons_enabled(False)
        self.render_video_button.setText("Rendert...")
        self._log("Render gestartet.")

        try:
            render_plan = self._build_render_plan()

            output_path = FFmpegRenderer(
                log_callback=self._log,
            ).render(render_plan)

        except SourceResolveError as error:
            self._log(f"Source Fehler: {error}")
            return

        except FFmpegRenderError as error:
            self._log(f"Render Fehler: {error}")
            return

        except Exception as error:
            self._log(f"Fehler: {error}")
            return

        finally:
            self._set_render_buttons_enabled(True)
            self.render_video_button.setText("Video rendern")

        self._log(f"Render fertig: {output_path}")

    def _render_all_presets(self) -> None:
        self._set_render_buttons_enabled(False)
        self.render_all_button.setText("Rendert alle...")
        self._log("Render All Presets gestartet.")

        try:
            for preset_id in self._available_preset_ids():
                self._log(f"--- Preset Render Start: {preset_id} ---")

                render_plan = self._build_render_plan(preset_id=preset_id)

                output_path = FFmpegRenderer(
                    log_callback=self._log,
                ).render(render_plan)

                self._log(f"Preset fertig: {preset_id} -> {output_path}")

            self._log("Render All Presets fertig.")

        except SourceResolveError as error:
            self._log(f"Source Fehler: {error}")
            return

        except FFmpegRenderError as error:
            self._log(f"Render Fehler: {error}")
            return

        except Exception as error:
            self._log(f"Fehler: {error}")
            return

        finally:
            self._set_render_buttons_enabled(True)
            self.render_all_button.setText("Alle Presets rendern")