"""Configuration schema.

The reference page `docs/reference/config.md` is generated from these models,
so every field needs a `description`. CI fails when the page is out of date.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jogpad.keys import parse_key
from jogpad.layouts import NO_LAYOUT, load_layout

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class Action(str, Enum):
    X_PLUS = "x_plus"
    X_MINUS = "x_minus"
    Y_PLUS = "y_plus"
    Y_MINUS = "y_minus"
    Z_PLUS = "z_plus"
    Z_MINUS = "z_minus"
    E_PLUS = "e_plus"
    E_MINUS = "e_minus"
    SELECTED_PLUS = "selected_plus"
    SELECTED_MINUS = "selected_minus"
    SELECT_NEXT = "select_next"
    STEP = "step"
    HOME = "home"
    STOP = "stop"


DEFAULT_KEYS: dict[Action, list[str]] = {
    Action.X_PLUS: ["KEY_KP6"],
    Action.X_MINUS: ["KEY_KP4"],
    Action.Y_PLUS: ["KEY_KP8"],
    Action.Y_MINUS: ["KEY_KP2"],
    Action.Z_PLUS: ["KEY_KPPLUS"],
    Action.Z_MINUS: ["KEY_KPMINUS"],
    Action.STEP: ["KEY_KPASTERISK"],
    Action.HOME: ["KEY_KPENTER"],
    Action.STOP: ["KEY_KP0"],
}


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Lock(_Section):
    object: str = Field(description="Firmware status object, e.g. `print_stats`.")
    field: str = Field(description="Field of that object, e.g. `state`.")
    equals: list[str | float | bool] | None = Field(
        None,
        description="Lock when the field has one of these values. "
        "Without it, lock when the field is true or non-zero.",
    )
    reason: str = Field(description="Shown when a key press is refused.")


DEFAULT_LOCKS = [
    Lock(object="print_stats", field="state", equals=["printing", "paused"], reason="job running")
]


class MachineConfig(_Section):
    backend: Literal["moonraker"] = Field(
        "moonraker", description="Firmware interface. Only Moonraker (Klipper) for now."
    )
    url: str = Field(
        "http://127.0.0.1:7125", description="Base URL of the firmware's HTTP interface."
    )
    locks: list[Lock] = Field(
        DEFAULT_LOCKS,
        description="Conditions under which jogpad refuses to move or home. "
        "STOP always works. If the status cannot be read, jogpad refuses as well.",
    )


class JogConfig(_Section):
    steps: list[float] = Field(
        [0.01, 0.1, 1.0],
        description="Step sizes in mm. The step key cycles through them; jogpad starts "
        "with the first.",
    )
    feed_xy: float = Field(3000, gt=0, description="Feed rate for X and Y in mm/min.")
    feed_z: float = Field(600, gt=0, description="Feed rate for Z in mm/min.")
    feed_e: float = Field(300, gt=0, description="Feed rate for the extruder in mm/min.")
    select_axes: list[Literal["X", "Y", "Z"]] = Field(
        ["X", "Y"], description="Axes that `select_next` cycles through for a knob."
    )
    home_timeout: float = Field(
        5, gt=0, description="Seconds after which an unfinished HOME selection is dropped."
    )
    announce_moves: bool = Field(
        True,
        description="Report every move and homing in the firmware console, so others "
        "can see who moved the machine.",
    )
    invert: list[Literal["X", "Y", "Z", "E"]] = Field(
        [],
        description="Axes whose keys move the other way, e.g. when the bed moves instead "
        "of the tool. Klipper's coordinates stay as they are.",
    )


class InputConfig(_Section):
    devices: list[str] = Field(
        [],
        description="Input devices to read, e.g. `/dev/input/by-id/usb-...-event-kbd`. "
        "jogpad grabs them exclusively.",
    )
    keys: dict[Action, list[str]] = Field(
        DEFAULT_KEYS,
        description="Key names or numbers per action, as in `linux/input-event-codes.h`. "
        "Merged over the numeric keypad defaults; `[]` switches an action off.",
    )
    layout: str = Field(
        "numpad",
        description="Pad drawn on the web page: `numpad`, `ch57x-9k3`, or `none` to "
        "list pressed keys only.",
    )

    @field_validator("layout")
    @classmethod
    def _layout_exists(cls, value: str) -> str:
        if value != NO_LAYOUT:
            load_layout(value)
        return value

    @field_validator("keys", mode="before")
    @classmethod
    def _merge_defaults(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {**{a.value: k for a, k in DEFAULT_KEYS.items()}, **value}
        return value

    @field_validator("keys")
    @classmethod
    def _keys_unique(cls, value: dict[Action, list[str]]) -> dict[Action, list[str]]:
        seen: dict[int, Action] = {}
        for action, names in value.items():
            for name in names:
                code = parse_key(name)
                if code in seen:
                    raise ValueError(
                        f"{name} is used for both {seen[code].value} and {action.value}"
                    )
                seen[code] = action
        return value

    def actions_by_code(self) -> dict[int, Action]:
        return {parse_key(name): action for action, names in self.keys.items() for name in names}


class ServerConfig(_Section):
    host: str = Field("127.0.0.1", description="Address the web interface and API listen on.")
    port: int = Field(7150, ge=1, le=65535, description="Port of the web interface and API.")
    language: Literal["en", "de"] = Field("en", description="Language of messages.")
    allow_remote_changes: bool = Field(
        False,
        description="Let other computers change the configuration through the web page. "
        "Without it only the machine itself may, e.g. through an SSH tunnel.",
    )


class Config(_Section):
    machine: MachineConfig = Field(default_factory=MachineConfig)
    jog: JogConfig = Field(default_factory=JogConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def load_config(path: Path | None) -> Config:
    if path is None:
        return Config()
    with path.open("rb") as f:
        return Config.model_validate(tomllib.load(f))
