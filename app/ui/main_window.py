from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
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

CORE_PRESET_IDS = {
    "youtube_ranking",
    "tiktok_meme",
}

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("ClipFactory")
        self.resize(1250, 900)

        self.slot_widgets: list[ClipSlotWidget] = []

        self.project_name_input = QLineEdit("animal_ranking_001")

        self.preset_select = QComboBox()

        self.add_preset_button = QPushButton("Add New Preset")
        self.add_preset_button.clicked.connect(self._add_new_preset)

        self.delete_preset_button = QPushButton("Delete Preset")
        self.delete_preset_button.clicked.connect(self._delete_current_preset)

        self.render_video_button = QPushButton("Video rendern")
        self.render_video_button.clicked.connect(self._render_video)

        self.render_all_button = QPushButton("Alle Presets rendern")
        self.render_all_button.clicked.connect(self._render_all_presets)

        self.open_output_button = QPushButton("Output-Ordner öffnen")
        self.open_output_button.clicked.connect(self._open_output_folder)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Projektname"))
        top_layout.addWidget(self.project_name_input)
        top_layout.addWidget(QLabel("Preset"))
        top_layout.addWidget(self.preset_select)
        top_layout.addWidget(self.add_preset_button)
        top_layout.addWidget(self.delete_preset_button)
        top_layout.addWidget(self.render_video_button)
        top_layout.addWidget(self.render_all_button)
        top_layout.addWidget(self.open_output_button)

        self.interstitial_enabled_checkbox = QCheckBox("Preset-Transition zwischen Main-Clips")
        self.interstitial_path_input = QLineEdit()
        self.interstitial_path_input.setPlaceholderText(
            "Transition-Clip auswählen, z. B. assets/transitions/static_noise.mp4"
        )

        self.interstitial_browse_button = QPushButton("Transition Datei")
        self.interstitial_browse_button.clicked.connect(self._browse_transition_file)

        self.save_preset_button = QPushButton("Preset speichern")
        self.save_preset_button.clicked.connect(self._save_current_preset_settings)

        transition_layout = QHBoxLayout()
        transition_layout.addWidget(self.interstitial_enabled_checkbox)
        transition_layout.addWidget(QLabel("Clip"))
        transition_layout.addWidget(self.interstitial_path_input)
        transition_layout.addWidget(self.interstitial_browse_button)
        transition_layout.addWidget(self.save_preset_button)

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
        main_layout.addLayout(transition_layout)
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(QLabel("Logs"))
        main_layout.addWidget(self.log_view)

        root = QWidget()
        root.setLayout(main_layout)

        self.setCentralWidget(root)

        self._load_presets_into_dropdown(select_preset_id="youtube_ranking")
        self.preset_select.currentIndexChanged.connect(self._load_current_preset_settings)

        self._add_slot()
        self._log("ClipFactory gestartet.")
        self._load_current_preset_settings()

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

    def _current_preset_id(self) -> str:
        preset_id = self.preset_select.currentData()

        if preset_id is None:
            return ""

        return str(preset_id)

    def _available_preset_ids(self) -> list[str]:
        preset_ids: list[str] = []

        for index in range(self.preset_select.count()):
            preset_id = self.preset_select.itemData(index)

            if preset_id:
                preset_ids.append(str(preset_id))

        return preset_ids

    def _preset_path(self, preset_id: str) -> Path:
        return Path("app/presets") / f"{preset_id}.json"

    def _load_presets_into_dropdown(self, select_preset_id: str | None = None) -> None:
        presets_dir = Path("app/presets")
        presets_dir.mkdir(parents=True, exist_ok=True)

        current_id = select_preset_id or self._current_preset_id()

        self.preset_select.blockSignals(True)
        self.preset_select.clear()

        preset_files = sorted(presets_dir.glob("*.json"))

        for preset_file in preset_files:
            try:
                data = json.loads(preset_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue

            preset_id = str(data.get("id", preset_file.stem))
            preset_name = str(data.get("name", preset_id))

            self.preset_select.addItem(preset_name, preset_id)

        selected_index = 0

        for index in range(self.preset_select.count()):
            if self.preset_select.itemData(index) == current_id:
                selected_index = index
                break

        if self.preset_select.count() > 0:
            self.preset_select.setCurrentIndex(selected_index)

        self.preset_select.blockSignals(False)

    def _load_preset_json(self, preset_id: str) -> dict | None:
        if not preset_id:
            self._log("Kein Preset ausgewählt.")
            return None

        preset_path = self._preset_path(preset_id)

        if not preset_path.exists():
            self._log(f"Preset-Datei nicht gefunden: {preset_path}")
            return None

        try:
            return json.loads(preset_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            self._log(f"Preset JSON konnte nicht gelesen werden: {error}")
            return None

    def _write_preset_json(self, preset_id: str, data: dict) -> bool:
        preset_path = self._preset_path(preset_id)

        try:
            preset_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as error:
            self._log(f"Preset konnte nicht gespeichert werden: {error}")
            return False

        return True

    def _load_current_preset_settings(self) -> None:
        preset_id = self._current_preset_id()

        if not preset_id:
            return

        data = self._load_preset_json(preset_id)

        if data is None:
            return

        interstitial = data.get("preset_interstitial", {})

        enabled = bool(interstitial.get("enabled", False))
        path = str(interstitial.get("path", ""))

        self.interstitial_enabled_checkbox.blockSignals(True)
        self.interstitial_path_input.blockSignals(True)

        self.interstitial_enabled_checkbox.setChecked(enabled)
        self.interstitial_path_input.setText(path)

        self.interstitial_enabled_checkbox.blockSignals(False)
        self.interstitial_path_input.blockSignals(False)

        self._log(f"Preset geladen: {preset_id}")

    def _add_new_preset(self) -> None:
        current_preset_id = self._current_preset_id()

        if not current_preset_id:
            self._log("Kein Basis-Preset ausgewählt.")
            return

        preset_name, accepted = QInputDialog.getText(
            self,
            "Add New Preset",
            "Name für neues Preset:",
        )

        if not accepted:
            return

        preset_name = preset_name.strip()

        if not preset_name:
            self._log("Preset wurde nicht erstellt: Name ist leer.")
            return

        base_data = self._load_preset_json(current_preset_id)

        if base_data is None:
            return

        if not self._apply_current_ui_settings_to_preset_data(base_data):
            return

        new_preset_id = self._create_unique_preset_id(preset_name)

        base_data["id"] = new_preset_id
        base_data["name"] = preset_name

        if not self._write_preset_json(new_preset_id, base_data):
            return

        self._load_presets_into_dropdown(select_preset_id=new_preset_id)
        self._load_current_preset_settings()

        self._log(f"Neues Preset erstellt: {preset_name} ({new_preset_id})")

    def _delete_current_preset(self) -> None:
        preset_id = self._current_preset_id()

        if not preset_id:
            self._log("Kein Preset ausgewählt.")
            return

        if preset_id in CORE_PRESET_IDS:
            self._log(f"Core-Preset kann nicht gelöscht werden: {preset_id}")
            return

        data = self._load_preset_json(preset_id)
        preset_name = preset_id

        if data is not None:
            preset_name = str(data.get("name", preset_id))

        answer = QMessageBox.question(
            self,
            "Preset löschen",
            f"Preset wirklich löschen?\n\n{preset_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        preset_path = self._preset_path(preset_id)

        try:
            preset_path.unlink()
        except OSError as error:
            self._log(f"Preset konnte nicht gelöscht werden: {error}")
            return

        self._log(f"Preset gelöscht: {preset_name} ({preset_id})")

        self._load_presets_into_dropdown(select_preset_id="youtube_ranking")
        self._load_current_preset_settings()

    def _create_unique_preset_id(self, preset_name: str) -> str:
        base_id = self._slugify_preset_name(preset_name)

        if not base_id:
            base_id = "custom_preset"

        candidate = base_id
        counter = 1

        while self._preset_path(candidate).exists():
            candidate = f"{base_id}_{counter:02d}"
            counter += 1

        return candidate

    def _slugify_preset_name(self, value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = cleaned.strip("_")
        return cleaned

    def _browse_transition_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Transition-Clip auswählen",
            str(Path("assets/transitions").resolve()),
            "Videos (*.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )

        if not file_path:
            return

        self.interstitial_path_input.setText(self._make_path_project_relative(file_path))

    def _make_path_project_relative(self, raw_path: str) -> str:
        path = Path(raw_path).expanduser()

        try:
            return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def _apply_current_ui_settings_to_preset_data(self, data: dict) -> bool:
        enabled = self.interstitial_enabled_checkbox.isChecked()
        transition_path_raw = self.interstitial_path_input.text().strip()

        if enabled:
            if not transition_path_raw:
                self._log("Transition ist aktiviert, aber kein Clip-Pfad ist gesetzt.")
                return False

            transition_path = Path(transition_path_raw)

            if not transition_path.exists():
                self._log(f"Transition-Clip existiert nicht: {transition_path}")
                return False

        data["preset_interstitial"] = {
            "enabled": enabled,
            "path": transition_path_raw,
            "insert_between_main_clips": True,
        }

        return True

    def _save_current_preset_settings(self, silent: bool = False) -> bool:
        preset_id = self._current_preset_id()
        data = self._load_preset_json(preset_id)

        if data is None:
            return False

        if not self._apply_current_ui_settings_to_preset_data(data):
            return False

        if not self._write_preset_json(preset_id, data):
            return False

        if not silent:
            self._log(f"Preset gespeichert: {preset_id}")

        return True

    def _open_output_folder(self) -> None:
        output_dir = Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(output_dir.resolve()))
        )

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

        selected_preset_id = preset_id or self._current_preset_id()

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
        self.save_preset_button.setEnabled(enabled)
        self.add_preset_button.setEnabled(enabled)
        self.delete_preset_button.setEnabled(enabled)

    def _render_video(self) -> None:
        if not self._save_current_preset_settings(silent=True):
            return

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
        if not self._save_current_preset_settings(silent=True):
            return

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