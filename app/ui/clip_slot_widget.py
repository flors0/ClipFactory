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
        self.main_input.setPlaceholderText("Main clip URL oder lokale Datei...")

        self.caption_input = QLineEdit()
        self.caption_input.setPlaceholderText("Caption, z. B. small spoder")

        self.after_input = QLineEdit()
        self.after_input.setPlaceholderText("After-clip/Meme URL oder lokale Datei...")

        self.main_browse_button = QPushButton("Datei")
        self.after_browse_button = QPushButton("Datei")

        layout = QGridLayout(self)
        layout.addWidget(self.index_label, 0, 0)
        layout.addWidget(QLabel("Main Clip"), 0, 1)
        layout.addWidget(self.main_input, 0, 2)
        layout.addWidget(self.main_browse_button, 0, 3)

        layout.addWidget(QLabel("Caption"), 1, 1)
        layout.addWidget(self.caption_input, 1, 2, 1, 2)

        layout.addWidget(QLabel("After Clip"), 2, 1)
        layout.addWidget(self.after_input, 2, 2)
        layout.addWidget(self.after_browse_button, 2, 3)

        self.main_input.textChanged.connect(self._emit_changed)
        self.caption_input.textChanged.connect(self._emit_changed)
        self.after_input.textChanged.connect(self._emit_changed)

        self.main_browse_button.clicked.connect(self._browse_main)
        self.after_browse_button.clicked.connect(self._browse_after)

    def _emit_changed(self, *_args) -> None:
        self.changed.emit()

    def _browse_main(self) -> None:
        path = self._pick_video_file()
        if path:
            self.main_input.setText(path)

    def _browse_after(self) -> None:
        path = self._pick_video_file()
        if path:
            self.after_input.setText(path)

    def _pick_video_file(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Video auswählen",
            str(Path.home()),
            "Videos (*.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )
        return file_path

    def has_main_value(self) -> bool:
        return bool(self.main_input.text().strip())

    def get_values(self) -> dict:
        return {
            "index": self.index,
            "main": self.main_input.text().strip(),
            "caption": self.caption_input.text().strip(),
            "after": self.after_input.text().strip(),
        }