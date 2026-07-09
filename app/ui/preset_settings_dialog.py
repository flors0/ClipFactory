from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class PresetSettingsDialog(QDialog):
    def __init__(
        self,
        preset_data: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Preset Settings")
        self.resize(760, 620)

        self.preset_data = deepcopy(preset_data)

        self.tabs = QTabWidget()

        self.general_tab = QWidget()
        self.header_tab = QWidget()
        self.ranking_tab = QWidget()
        self.transition_tab = QWidget()

        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.header_tab, "Header")
        self.tabs.addTab(self.ranking_tab, "Ranking")
        self.tabs.addTab(self.transition_tab, "Transitions")

        self._build_general_tab()
        self._build_header_tab()
        self._build_ranking_tab()
        self._build_transition_tab()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(button_box)

    def get_preset_data(self) -> dict:
        data = deepcopy(self.preset_data)

        data["name"] = self.preset_name_input.text().strip() or data.get("name", "Preset")

        data["resolution"] = [
            self.width_input.value(),
            self.height_input.value(),
        ]
        data["fps"] = self.fps_input.value()

        data["header_overlay"] = self._collect_header_overlay()
        data["ranking_overlay"] = self._collect_ranking_overlay()
        data["preset_interstitial"] = self._collect_preset_interstitial()

        return data

    def _build_general_tab(self) -> None:
        resolution = self.preset_data.get("resolution", [1080, 1920])

        self.preset_name_input = QLineEdit(str(self.preset_data.get("name", "")))

        self.width_input = QSpinBox()
        self.width_input.setRange(100, 7680)
        self.width_input.setValue(int(resolution[0]) if len(resolution) > 0 else 1080)

        self.height_input = QSpinBox()
        self.height_input.setRange(100, 7680)
        self.height_input.setValue(int(resolution[1]) if len(resolution) > 1 else 1920)

        self.fps_input = QSpinBox()
        self.fps_input.setRange(1, 240)
        self.fps_input.setValue(int(self.preset_data.get("fps", 30)))

        layout = QFormLayout(self.general_tab)
        layout.addRow("Preset Name", self.preset_name_input)
        layout.addRow("Width", self.width_input)
        layout.addRow("Height", self.height_input)
        layout.addRow("FPS", self.fps_input)

    def _build_header_tab(self) -> None:
        header = self.preset_data.get("header_overlay", {})

        self.header_enabled_input = QCheckBox("Enable header overlay")
        self.header_enabled_input.setChecked(bool(header.get("enabled", False)))

        self.header_text_input = QLineEdit(str(header.get("text", "")))
        self.header_text_input.setPlaceholderText("The Cutest Cats To Brighten Your Day")

        self.header_bar_height_input = QSpinBox()
        self.header_bar_height_input.setRange(0, 1000)
        self.header_bar_height_input.setValue(int(header.get("bar_height", 220)))

        self.header_background_color_input = QLineEdit(str(header.get("background_color", "#000000")))
        self.header_background_opacity_input = QSpinBox()
        self.header_background_opacity_input.setRange(0, 255)
        self.header_background_opacity_input.setValue(int(header.get("background_opacity", 255)))

        self.header_font_path_input = QLineEdit(str(header.get("font_path", "")))
        self.header_font_button = QPushButton("Browse Font")
        self.header_font_button.clicked.connect(self._browse_header_font)

        font_layout = QHBoxLayout()
        font_layout.addWidget(self.header_font_path_input)
        font_layout.addWidget(self.header_font_button)

        self.header_font_size_input = QSpinBox()
        self.header_font_size_input.setRange(1, 300)
        self.header_font_size_input.setValue(int(header.get("font_size", 64)))

        self.header_bold_input = QCheckBox("Bold")
        self.header_bold_input.setChecked(bool(header.get("bold", True)))

        self.header_default_word_color_input = QLineEdit(
            str(header.get("default_word_color", "#FFFFFF"))
        )

        self.header_stroke_color_input = QLineEdit(str(header.get("stroke_color", "#000000")))

        self.header_stroke_width_input = QSpinBox()
        self.header_stroke_width_input.setRange(0, 20)
        self.header_stroke_width_input.setValue(int(header.get("stroke_width", 0)))

        self.header_y_offset_input = QSpinBox()
        self.header_y_offset_input.setRange(0, 1000)
        self.header_y_offset_input.setValue(int(header.get("y_offset", 26)))

        self.header_horizontal_padding_input = QSpinBox()
        self.header_horizontal_padding_input.setRange(0, 500)
        self.header_horizontal_padding_input.setValue(int(header.get("horizontal_padding", 50)))

        self.header_line_spacing_input = QSpinBox()
        self.header_line_spacing_input.setRange(0, 200)
        self.header_line_spacing_input.setValue(int(header.get("line_spacing", 4)))

        self.header_align_input = QLineEdit(str(header.get("align", "center")))
        self.header_align_input.setPlaceholderText("left, center, or right")

        self.header_word_colors_input = QPlainTextEdit()
        self.header_word_colors_input.setPlaceholderText(
            "One per line, zero-based word index:\n"
            "1=#FF4FD8\n"
            "2=#00E5FF"
        )
        self.header_word_colors_input.setPlainText(
            self._word_colors_dict_to_text(header.get("word_colors", {}))
        )

        layout = QFormLayout(self.header_tab)
        layout.addRow(self.header_enabled_input)
        layout.addRow("Header Text", self.header_text_input)
        layout.addRow("Bar Height", self.header_bar_height_input)
        layout.addRow("Background Color", self.header_background_color_input)
        layout.addRow("Background Opacity", self.header_background_opacity_input)
        layout.addRow("Font Path", font_layout)
        layout.addRow("Font Size", self.header_font_size_input)
        layout.addRow(self.header_bold_input)
        layout.addRow("Default Word Color", self.header_default_word_color_input)
        layout.addRow("Word Colors", self.header_word_colors_input)
        layout.addRow("Stroke Color", self.header_stroke_color_input)
        layout.addRow("Stroke Width", self.header_stroke_width_input)
        layout.addRow("Y Offset", self.header_y_offset_input)
        layout.addRow("Horizontal Padding", self.header_horizontal_padding_input)
        layout.addRow("Line Spacing", self.header_line_spacing_input)
        layout.addRow("Align", self.header_align_input)

    def _build_ranking_tab(self) -> None:
        ranking = self.preset_data.get("ranking_overlay", {})

        self.ranking_enabled_input = QCheckBox("Enable ranking overlay")
        self.ranking_enabled_input.setChecked(bool(ranking.get("enabled", False)))

        self.ranking_mode_input = QLineEdit(str(ranking.get("mode", "progressive_reveal")))

        self.ranking_x_number_input = QSpinBox()
        self.ranking_x_number_input.setRange(0, 3000)
        self.ranking_x_number_input.setValue(int(ranking.get("x_number", 60)))

        self.ranking_x_caption_input = QSpinBox()
        self.ranking_x_caption_input.setRange(0, 3000)
        self.ranking_x_caption_input.setValue(int(ranking.get("x_caption", 185)))

        self.ranking_y_start_input = QSpinBox()
        self.ranking_y_start_input.setRange(0, 3000)
        self.ranking_y_start_input.setValue(int(ranking.get("y_start", 170)))

        self.ranking_line_height_input = QSpinBox()
        self.ranking_line_height_input.setRange(1, 500)
        self.ranking_line_height_input.setValue(int(ranking.get("line_height", 92)))

        self.ranking_number_font_size_input = QSpinBox()
        self.ranking_number_font_size_input.setRange(1, 300)
        self.ranking_number_font_size_input.setValue(int(ranking.get("number_font_size", 76)))

        self.ranking_caption_font_size_input = QSpinBox()
        self.ranking_caption_font_size_input.setRange(1, 300)
        self.ranking_caption_font_size_input.setValue(int(ranking.get("caption_font_size", 56)))

        self.ranking_number_font_path_input = QLineEdit(str(ranking.get("number_font_path", "")))
        self.ranking_caption_font_path_input = QLineEdit(str(ranking.get("caption_font_path", "")))

        self.ranking_number_font_button = QPushButton("Browse")
        self.ranking_caption_font_button = QPushButton("Browse")

        self.ranking_number_font_button.clicked.connect(self._browse_ranking_number_font)
        self.ranking_caption_font_button.clicked.connect(self._browse_ranking_caption_font)

        number_font_layout = QHBoxLayout()
        number_font_layout.addWidget(self.ranking_number_font_path_input)
        number_font_layout.addWidget(self.ranking_number_font_button)

        caption_font_layout = QHBoxLayout()
        caption_font_layout.addWidget(self.ranking_caption_font_path_input)
        caption_font_layout.addWidget(self.ranking_caption_font_button)

        number_colors = ranking.get("number_colors", {})
        self.ranking_number_default_color_input = QLineEdit(
            str(number_colors.get("default", "#FFD700"))
        )

        self.ranking_caption_color_input = QLineEdit(str(ranking.get("caption_color", "#FFFFFF")))
        self.ranking_stroke_color_input = QLineEdit(str(ranking.get("stroke_color", "#000000")))
        self.ranking_shadow_color_input = QLineEdit(str(ranking.get("shadow_color", "#000000")))

        self.ranking_number_stroke_width_input = QSpinBox()
        self.ranking_number_stroke_width_input.setRange(0, 20)
        self.ranking_number_stroke_width_input.setValue(
            int(ranking.get("number_stroke_width", 4))
        )

        self.ranking_caption_stroke_width_input = QSpinBox()
        self.ranking_caption_stroke_width_input.setRange(0, 20)
        self.ranking_caption_stroke_width_input.setValue(
            int(ranking.get("caption_stroke_width", 2))
        )

        self.ranking_shadow_offset_x_input = QSpinBox()
        self.ranking_shadow_offset_x_input.setRange(-100, 100)
        self.ranking_shadow_offset_x_input.setValue(int(ranking.get("shadow_offset_x", 3)))

        self.ranking_shadow_offset_y_input = QSpinBox()
        self.ranking_shadow_offset_y_input.setRange(-100, 100)
        self.ranking_shadow_offset_y_input.setValue(int(ranking.get("shadow_offset_y", 3)))

        layout = QFormLayout(self.ranking_tab)
        layout.addRow(self.ranking_enabled_input)
        layout.addRow("Mode", self.ranking_mode_input)
        layout.addRow("Number X", self.ranking_x_number_input)
        layout.addRow("Caption X", self.ranking_x_caption_input)
        layout.addRow("Y Start", self.ranking_y_start_input)
        layout.addRow("Line Height", self.ranking_line_height_input)
        layout.addRow("Number Font Size", self.ranking_number_font_size_input)
        layout.addRow("Caption Font Size", self.ranking_caption_font_size_input)
        layout.addRow("Number Font Path", number_font_layout)
        layout.addRow("Caption Font Path", caption_font_layout)
        layout.addRow("Default Number Color", self.ranking_number_default_color_input)
        layout.addRow("Caption Color", self.ranking_caption_color_input)
        layout.addRow("Stroke Color", self.ranking_stroke_color_input)
        layout.addRow("Shadow Color", self.ranking_shadow_color_input)
        layout.addRow("Number Stroke Width", self.ranking_number_stroke_width_input)
        layout.addRow("Caption Stroke Width", self.ranking_caption_stroke_width_input)
        layout.addRow("Shadow Offset X", self.ranking_shadow_offset_x_input)
        layout.addRow("Shadow Offset Y", self.ranking_shadow_offset_y_input)

    def _build_transition_tab(self) -> None:
        interstitial = self.preset_data.get("preset_interstitial", {})

        self.transition_enabled_input = QCheckBox("Enable preset transition")
        self.transition_enabled_input.setChecked(bool(interstitial.get("enabled", False)))

        self.transition_insert_between_input = QCheckBox("Insert between main clips")
        self.transition_insert_between_input.setChecked(
            bool(interstitial.get("insert_between_main_clips", True))
        )

        self.transition_path_input = QLineEdit(str(interstitial.get("path", "")))
        self.transition_path_input.setPlaceholderText("assets/transitions/static_noise.mp4")

        self.transition_browse_button = QPushButton("Browse Transition")
        self.transition_browse_button.clicked.connect(self._browse_transition_file)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.transition_path_input)
        path_layout.addWidget(self.transition_browse_button)

        layout = QFormLayout(self.transition_tab)
        layout.addRow(self.transition_enabled_input)
        layout.addRow(self.transition_insert_between_input)
        layout.addRow("Transition Clip", path_layout)

    def _collect_header_overlay(self) -> dict:
        return {
            "enabled": self.header_enabled_input.isChecked(),
            "text": self.header_text_input.text().strip(),
            "bar_height": self.header_bar_height_input.value(),
            "background_color": self.header_background_color_input.text().strip() or "#000000",
            "background_opacity": self.header_background_opacity_input.value(),
            "font_path": self.header_font_path_input.text().strip(),
            "font_size": self.header_font_size_input.value(),
            "bold": self.header_bold_input.isChecked(),
            "default_word_color": self.header_default_word_color_input.text().strip() or "#FFFFFF",
            "word_colors": self._word_colors_text_to_dict(
                self.header_word_colors_input.toPlainText()
            ),
            "stroke_color": self.header_stroke_color_input.text().strip() or "#000000",
            "stroke_width": self.header_stroke_width_input.value(),
            "y_offset": self.header_y_offset_input.value(),
            "horizontal_padding": self.header_horizontal_padding_input.value(),
            "line_spacing": self.header_line_spacing_input.value(),
            "align": self.header_align_input.text().strip() or "center",
        }

    def _collect_ranking_overlay(self) -> dict:
        return {
            "enabled": self.ranking_enabled_input.isChecked(),
            "mode": self.ranking_mode_input.text().strip() or "progressive_reveal",
            "x_number": self.ranking_x_number_input.value(),
            "x_caption": self.ranking_x_caption_input.value(),
            "y_start": self.ranking_y_start_input.value(),
            "line_height": self.ranking_line_height_input.value(),
            "number_font_size": self.ranking_number_font_size_input.value(),
            "caption_font_size": self.ranking_caption_font_size_input.value(),
            "number_font_path": self.ranking_number_font_path_input.text().strip(),
            "caption_font_path": self.ranking_caption_font_path_input.text().strip(),
            "number_colors": {
                "default": self.ranking_number_default_color_input.text().strip() or "#FFD700"
            },
            "caption_color": self.ranking_caption_color_input.text().strip() or "#FFFFFF",
            "stroke_color": self.ranking_stroke_color_input.text().strip() or "#000000",
            "shadow_color": self.ranking_shadow_color_input.text().strip() or "#000000",
            "number_stroke_width": self.ranking_number_stroke_width_input.value(),
            "caption_stroke_width": self.ranking_caption_stroke_width_input.value(),
            "shadow_offset_x": self.ranking_shadow_offset_x_input.value(),
            "shadow_offset_y": self.ranking_shadow_offset_y_input.value(),
        }

    def _collect_preset_interstitial(self) -> dict:
        return {
            "enabled": self.transition_enabled_input.isChecked(),
            "path": self.transition_path_input.text().strip(),
            "insert_between_main_clips": self.transition_insert_between_input.isChecked(),
        }

    def _browse_header_font(self) -> None:
        path = self._pick_font_file()
        if path:
            self.header_font_path_input.setText(path)

    def _browse_ranking_number_font(self) -> None:
        path = self._pick_font_file()
        if path:
            self.ranking_number_font_path_input.setText(path)

    def _browse_ranking_caption_font(self) -> None:
        path = self._pick_font_file()
        if path:
            self.ranking_caption_font_path_input.setText(path)

    def _pick_font_file(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select font",
            str(Path("assets/fonts").resolve()),
            "Fonts (*.ttf *.otf);;All Files (*)",
        )

        if not file_path:
            return ""

        return self._make_path_project_relative(file_path)

    def _browse_transition_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select transition clip",
            str(Path("assets/transitions").resolve()),
            "Videos (*.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )

        if not file_path:
            return

        self.transition_path_input.setText(self._make_path_project_relative(file_path))

    def _make_path_project_relative(self, raw_path: str) -> str:
        path = Path(raw_path).expanduser()

        try:
            return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def _word_colors_dict_to_text(self, word_colors: dict) -> str:
        lines: list[str] = []

        for key, value in word_colors.items():
            lines.append(f"{key}={value}")

        return "\n".join(lines)

    def _word_colors_text_to_dict(self, raw_text: str) -> dict[str, str]:
        result: dict[str, str] = {}

        for raw_line in raw_text.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key or not value:
                continue

            result[key] = value

        return result