from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    URL = "url"
    LOCAL_FILE = "local_file"
    EMPTY = "empty"


class SourceInput(BaseModel):
    """
    Represents what the user entered into a slot.

    It can be:
    - a URL
    - a local file path
    - empty
    """

    raw_value: str = ""
    source_type: SourceType = SourceType.EMPTY
    resolved_path: Optional[Path] = None

    @staticmethod
    def from_raw(raw_value: str) -> "SourceInput":
        value = raw_value.strip()

        if not value:
            return SourceInput(raw_value="", source_type=SourceType.EMPTY)

        if value.startswith("http://") or value.startswith("https://"):
            return SourceInput(raw_value=value, source_type=SourceType.URL)

        return SourceInput(raw_value=value, source_type=SourceType.LOCAL_FILE)


class ClipSlot(BaseModel):
    """
    One ranking slot.

    main_source:
        The main animal clip.

    caption:
        The ranking caption shown when this main clip starts.

    after_source:
        Optional meme/intercut clip that plays after this main clip.
    """

    index: int
    main_source: SourceInput = Field(default_factory=SourceInput)
    caption: str = ""
    after_source: SourceInput = Field(default_factory=SourceInput)

    @property
    def has_main_clip(self) -> bool:
        return self.main_source.source_type != SourceType.EMPTY


class ProjectData(BaseModel):
    project_name: str = "clipfactory_project"
    preset_id: str = "youtube_ranking"
    slots: list[ClipSlot] = Field(default_factory=list)

    def active_slots(self) -> list[ClipSlot]:
        return [slot for slot in self.slots if slot.has_main_clip]