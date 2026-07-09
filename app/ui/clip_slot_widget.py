from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class ClipSlotWidget(QWidget):
    changed = Signal()

    def __init__(self, index: int) -> None:
        super().__init__()

        self.index = index

        self.index_label = QLabel(f"{index}.")

        self.main_input = QLineEdit()
        self.main_input.setPlaceholderText("Main clip URL or local file...")

        self.main_audio_input = QLineEdit()
        self.main_audio_input.setPlaceholderText("Optional audio for main clip...")

        self.caption_input = QLineEdit()
        self.caption_input.setPlaceholderText("Caption...")

        self.interstitial_input = QLineEdit()
        self.interstitial_input.setPlaceholderText("Manual interstitial URL or local file...")

        self.interstitial_audio_input = QLineEdit()
        self.interstitial_audio_input.setPlaceholderText("Optional audio for manual interstitial...")

        self.main_browse_button = QPushButton("File")
        self.main_audio_browse_button = QPushButton("Audio")
        self.interstitial_browse_button = QPushButton("File")
        self.interstitial_audio_browse_button = QPushButton("Audio")

        layout = QGridLayout(self)

        layout.addWidget(self.index_label, 0, 0)

        layout.addWidget(QLabel("Main Clip"), 0, 1)
        layout.addWidget(self.main_input, 0, 2)
        layout.addWidget(self.main_browse_button, 0, 3)

        layout.addWidget(QLabel("Main Audio"), 1, 1)
        layout.addWidget(self.main_audio_input, 1, 2)
        layout.addWidget(self.main_audio_browse_button, 1, 3)

        layout.addWidget(QLabel("Caption"), 2, 1)
        layout.addWidget(self.caption_input, 2, 2, 1, 2)

        layout.addWidget(QLabel("Manual Interstitial"), 3, 1)
        layout.addWidget(self.interstitial_input, 3, 2)
        layout.addWidget(self.interstitial_browse_button, 3, 3)

        layout.addWidget(QLabel("Interstitial Audio"), 4, 1)
        layout.addWidget(self.interstitial_audio_input, 4, 2)
        layout.addWidget(self.interstitial_audio_browse_button, 4, 3)

        self.main_input.textChanged.connect(self._emit_changed)
        self.main_audio_input.textChanged.connect(self._emit_changed)
        self.caption_input.textChanged.connect(self._emit_changed)
        self.interstitial_input.textChanged.connect(self._emit_changed)
        self.interstitial_audio_input.textChanged.connect(self._emit_changed)

        self.main_browse_button.clicked.connect(self._browse_main)
        self.main_audio_browse_button.clicked.connect(self._browse_main_audio)
        self.interstitial_browse_button.clicked.connect(self._browse_interstitial)
        self.interstitial_audio_browse_button.clicked.connect(self._browse_interstitial_audio)

    def _emit_changed(self, *_args) -> None:
        self.changed.emit()

    def _browse_main(self) -> None:
        path = self._pick_video_file()
        if path:
            self.main_input.setText(path)

    def _browse_interstitial(self) -> None:
        path = self._pick_video_file()
        if path:
            self.interstitial_input.setText(path)

    def _browse_main_audio(self) -> None:
        path = self._pick_audio_file()
        if path:
            self.main_audio_input.setText(path)

    def _browse_interstitial_audio(self) -> None:
        path = self._pick_audio_file()
        if path:
            self.interstitial_audio_input.setText(path)

    def _pick_video_file(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select video",
            str(Path.home()),
            "Videos (*.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )
        return file_path

    def _pick_audio_file(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio",
            str(Path.home()),
            "Audio (*.mp3 *.wav *.m4a *.aac *.ogg *.flac *.mp4 *.mov *.webm);;All Files (*)",
        )
        return file_path

    def has_main_value(self) -> bool:
        return bool(self.main_input.text().strip())

    def get_values(self) -> dict:
        return {
            "index": self.index,
            "main": self.main_input.text().strip(),
            "main_audio": self.main_audio_input.text().strip(),
            "caption": self.caption_input.text().strip(),
            "interstitial": self.interstitial_input.text().strip(),
            "interstitial_audio": self.interstitial_audio_input.text().strip(),
        }