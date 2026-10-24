"""Configuration schema.

The reference page `docs/reference/config.md` is generated from these models,
so every field needs a `description`. CI fails when the page is out of date.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class MachineConfig(_Section):
    backend: Literal["moonraker"] = Field(
        "moonraker", description="Firmware interface. Only Moonraker (Klipper) for now."
    )
    url: str = Field(
        "http://127.0.0.1:7125", description="Base URL of the firmware's HTTP interface."
    )


class JogConfig(_Section):
    steps: list[float] = Field(
        [0.01, 0.1, 1.0],
        description="Step sizes in mm. The step key cycles through them; jogpad starts "
        "with the first.",
    )
    feed_xy: float = Field(3000, gt=0, description="Feed rate for X and Y in mm/min.")
    feed_z: float = Field(600, gt=0, description="Feed rate for Z in mm/min.")
    select_axes: list[Literal["X", "Y", "Z"]] = Field(
        ["X", "Y"], description="Axes that `select_next` cycles through for a knob."
    )
    home_timeout: float = Field(
        5, gt=0, description="Seconds after which an unfinished HOME selection is dropped."
    )


class InputConfig(_Section):
    devices: list[str] = Field(
        [],
        description="Input devices to read, e.g. `/dev/input/by-id/usb-...-event-kbd`. "
        "jogpad grabs them exclusively.",
    )
    keys: dict[Action, list[str]] = Field(
        DEFAULT_KEYS,
        description="Key names per action, as in `linux/input-event-codes.h`. "
        "Defaults to a numeric keypad.",
    )


class ServerConfig(_Section):
    host: str = Field("127.0.0.1", description="Address the web interface and API listen on.")
    port: int = Field(7150, ge=1, le=65535, description="Port of the web interface and API.")
    language: Literal["en", "de"] = Field("en", description="Language of messages.")


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
