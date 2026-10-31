"""Physical layouts of pads: which controls exist and where they sit.

A layout is drawn by the web page and tells which key code belongs to which
control. Positions and sizes are in key units (1 = one standard key). Layouts
live as JSON files next to this module; adding a pad means adding a file.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jogpad.keys import parse_key

LAYOUTS_DIR = Path(__file__).parent / "layouts"
NO_LAYOUT = "none"

Part = Literal["press", "cw", "ccw"]


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["key", "knob"]
    x: float
    y: float
    w: float = 1
    h: float = 1
    label: str = ""
    keys: dict[Part, str] = Field(
        {}, description="Key sent per part: `press` for keys, `cw`/`ccw`/`press` for knobs."
    )
    slot: int | None = Field(
        None,
        ge=0,
        description="Number of this key or knob in the pad's own firmware, from 0; "
        "only for pads that `jogpad program-pad` programs.",
    )

    @field_validator("keys")
    @classmethod
    def _known_keys(cls, value: dict[Part, str]) -> dict[Part, str]:
        for name in value.values():
            parse_key(name)
        return value


class Outline(BaseModel):
    """The pad's real shape, in key units like the controls."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    w: float
    h: float
    path: str = Field(description="SVG path of the outline, within the box x, y, w, h.")


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    note: str = ""
    translations: dict[str, dict[Literal["name", "note"], str]] = Field(
        {}, description="Name and note per language; English is `name` and `note`."
    )
    controls: list[Control]
    outline: Outline | None = Field(
        None, description="The pad's shape; without it a rounded rectangle around the controls."
    )

    def localized(self, language: str) -> Layout:
        texts = self.translations.get(language, {})
        return self.model_copy(
            update={"name": texts.get("name", self.name), "note": texts.get("note", self.note)}
        )

    def parts_by_code(self) -> dict[int, tuple[str, Part]]:
        return {
            parse_key(name): (control.id, part)
            for control in self.controls
            for part, name in control.keys.items()
        }


def layout_ids() -> list[str]:
    return sorted(path.stem for path in LAYOUTS_DIR.glob("*.json"))


@cache
def load_layout(layout_id: str) -> Layout:
    path = LAYOUTS_DIR / f"{layout_id}.json"
    if layout_id not in layout_ids():
        raise ValueError(f"unknown layout {layout_id!r}, known: {', '.join(layout_ids())}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Layout.model_validate({"id": layout_id, **data})
