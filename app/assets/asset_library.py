from __future__ import annotations

import json
from pathlib import Path

from app.assets.asset_models import AssetLibrary
from app.assets.asset_scanner import AssetScanner


class AssetLibraryManager:
    def __init__(
        self,
        library_path: Path = Path("data/asset_library.json"),
        scanner: AssetScanner | None = None,
    ) -> None:
        self.library_path = library_path
        self.scanner = scanner or AssetScanner()

    def refresh(self) -> AssetLibrary:
        library = self.scanner.scan()
        self.save(library)
        return library

    def load(self) -> AssetLibrary:
        if not self.library_path.exists():
            return AssetLibrary()

        try:
            data = json.loads(self.library_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AssetLibrary()

        try:
            return AssetLibrary(**data)
        except Exception:
            return AssetLibrary()

    def save(self, library: AssetLibrary) -> None:
        self.library_path.parent.mkdir(parents=True, exist_ok=True)

        self.library_path.write_text(
            json.dumps(
                self._model_to_json_dict(library),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _model_to_json_dict(self, model) -> dict:
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")

        return json.loads(model.json())