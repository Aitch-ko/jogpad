"""Turns key events into moves. No devices, no network: a `Backend` does the I/O.

`handle()` gets every key event that arrived since the last call. Presses that
pile up while the previous move is running become one move, so the axis stops
when the user stops turning instead of working off a queue.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from jogpad.config import Action, Config, Lock
from jogpad.i18n import t

log = logging.getLogger(__name__)

KEY_RELEASE, KEY_PRESS, KEY_AUTOREPEAT = 0, 1, 2

# Klipper macro behind the on/off switch in Mainsail and Fluidd, see klipper/jogpad.cfg.
SWITCH = "gcode_macro _JOGPAD"

AXIS_ACTIONS: dict[Action, tuple[str, int]] = {
    Action.X_PLUS: ("X", 1),
    Action.X_MINUS: ("X", -1),
    Action.Y_PLUS: ("Y", 1),
    Action.Y_MINUS: ("Y", -1),
    Action.Z_PLUS: ("Z", 1),
    Action.Z_MINUS: ("Z", -1),
    Action.E_PLUS: ("E", 1),
    Action.E_MINUS: ("E", -1),
}


class BackendError(Exception):
    pass


class Backend(Protocol):
    """What the core needs from a firmware. Calls block until the firmware is done."""

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]: ...

    def move(self, axis: str, distance: float, feed: float) -> None: ...

    def home(self, axes: list[str]) -> None: ...

    def emergency_stop(self) -> None: ...

    def notify(self, message: str) -> None: ...


class Switch(Enum):
    ON = "on"
    OFF = "off"
    MISSING = "missing"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class State:
    step: float
    selected_axis: str
    home_selection: list[str] | None
    last_refusal: str | None


class Jogger:
    def __init__(self, config: Config, backend: Backend) -> None:
        self.config = config
        self.backend = backend
        self.actions = config.input.actions_by_code()
        self.language = config.server.language
        self._step_index = 0
        self._selected = config.jog.select_axes[0]
        self._home_axes: list[str] | None = None
        self._home_deadline = 0.0
        self._last_refusal: str | None = None

    @property
    def step(self) -> float:
        return self.config.jog.steps[self._step_index]

    def state(self) -> State:
        home = None if self._home_axes is None else sorted(self._home_axes)
        return State(self.step, self._selected, home, self._last_refusal)

    def reconfigure(self, config: Config) -> None:
        """Take over a changed configuration, keeping step size and axis where possible."""
        self.config = config
        self.actions = config.input.actions_by_code()
        self.language = config.server.language
        self._step_index = min(self._step_index, len(config.jog.steps) - 1)
        if self._selected not in config.jog.select_axes:
            self._selected = config.jog.select_axes[0]

    def is_stop(self, code: int) -> bool:
        return self.actions.get(code) is Action.STOP

    def switch(self) -> Switch:
        """The switch in Mainsail or Fluidd, read from its macro in Klipper."""
        try:
            status = self.backend.query({SWITCH: ["value"]})
        except BackendError as exc:
            log.warning("switch not readable: %s", exc)
            return Switch.UNREADABLE
        # Klipper answers for a macro that does not exist with value null.
        value = status.get(SWITCH, {}).get("value")
        if value is None:
            return Switch.MISSING
        return Switch.ON if value else Switch.OFF

    def switch_state(self) -> bool | None:
        """Whether jogpad is on; None if the switch cannot be read.

        Without the macro in Klipper there is no switch, and jogpad is always on.
        """
        switch = self.switch()
        return None if switch is Switch.UNREADABLE else switch is not Switch.OFF

    def handle(self, events: list[tuple[int, int]], now: float) -> None:
        if any(value == KEY_PRESS for _, value in events):
            switch = self.switch_state()
            if switch is False:
                # Switched off means off: no moves, no console messages.
                self._last_refusal = t("switch.off", self.language)
                return
            if switch is None:
                self._last_refusal = t("status.unreadable", self.language)
                self._notify("refused", reason=self._last_refusal)
                return
        moves: list[list[Any]] = []
        for code, value in events:
            action = self.actions.get(code)
            # Held keys repeat in the kernel; one press is one step, nothing more.
            if action is None or value != KEY_PRESS:
                continue
            if self._home_axes is not None:
                self._handle_home_key(action)
                continue
            if action in AXIS_ACTIONS:
                axis, sign = AXIS_ACTIONS[action]
                self._add_move(moves, axis, sign * self.step)
            elif action in (Action.SELECTED_PLUS, Action.SELECTED_MINUS):
                sign = 1 if action is Action.SELECTED_PLUS else -1
                self._add_move(moves, self._selected, sign * self.step)
            elif action is Action.SELECT_NEXT:
                self._flush(moves)
                axes = self.config.jog.select_axes
                self._selected = axes[(axes.index(self._selected) + 1) % len(axes)]
                self._notify("axis.selected", axis=self._selected)
            elif action is Action.STEP:
                self._flush(moves)
                self._step_index = (self._step_index + 1) % len(self.config.jog.steps)
                self._notify("step.changed", step=f"{self.step:g}")
            elif action is Action.HOME:
                self._flush(moves)
                self._home_axes = []
                self._home_deadline = now + self.config.jog.home_timeout
                self._notify("home.select")
        self._flush(moves)

    def tick(self, now: float) -> None:
        if self._home_axes is not None and now >= self._home_deadline:
            self._home_axes = None
            self._notify("home.cancelled")

    def next_deadline(self) -> float | None:
        return self._home_deadline if self._home_axes is not None else None

    # -- internals ----------------------------------------------------------

    def _handle_home_key(self, action: Action) -> None:
        assert self._home_axes is not None
        if action in AXIS_ACTIONS and AXIS_ACTIONS[action][0] != "E":
            axis = AXIS_ACTIONS[action][0]
            if axis in self._home_axes:
                self._home_axes.remove(axis)
            else:
                self._home_axes.append(axis)
            label = " ".join(sorted(self._home_axes)) or t("home.all", self.language)
            self._notify("home.selected", axes=label)
            return
        axes, self._home_axes = sorted(self._home_axes), None
        if action is not Action.HOME:
            self._notify("home.cancelled")
            return
        if self._refused():
            return
        # Announced before, because homing can take a minute without any feedback.
        if self.config.jog.announce_moves:
            label = " ".join(axes) or t("home.all", self.language)
            self._notify("home.started", axes=label)
        self._call(self.backend.home, axes)

    @staticmethod
    def _add_move(moves: list[list[Any]], axis: str, distance: float) -> None:
        if moves and moves[-1][0] == axis:
            moves[-1][1] += distance
        else:
            moves.append([axis, distance])

    def _flush(self, moves: list[list[Any]]) -> None:
        pending = [(axis, distance) for axis, distance in moves if abs(distance) > 1e-9]
        moves.clear()
        if not pending or self._refused():
            return
        jog = self.config.jog
        feeds = {"X": jog.feed_xy, "Y": jog.feed_xy, "Z": jog.feed_z, "E": jog.feed_e}
        for axis, distance in pending:
            distance = round(-distance if axis in jog.invert else distance, 6)
            if not self._call(self.backend.move, axis, distance, feeds[axis]):
                break
            if jog.announce_moves:
                self._notify("moved", axis=axis, distance=f"{distance:+g}")

    def _refused(self) -> bool:
        reason = self._lock_reason()
        self._last_refusal = reason
        if reason is not None:
            self._notify("refused", reason=reason)
        return reason is not None

    def _lock_reason(self) -> str | None:
        locks = self.config.machine.locks
        objects: dict[str, list[str]] = {}
        for lock in locks:
            objects.setdefault(lock.object, []).append(lock.field)
        try:
            status = self.backend.query(objects) if objects else {}
        except BackendError as exc:
            log.warning("status not readable: %s", exc)
            return t("status.unreadable", self.language)
        for lock in locks:
            if _is_locked(lock, status.get(lock.object, {}).get(lock.field)):
                return lock.reason
        return None

    def _call(self, fn: Any, *args: Any) -> bool:
        try:
            fn(*args)
            return True
        except BackendError as exc:
            log.warning("%s%r refused: %s", fn.__name__, args, exc)
            return False

    def _notify(self, key: str, **values: object) -> None:
        message = t(key, self.language, **values)
        log.info(message)
        with contextlib.suppress(BackendError):
            self.backend.notify(message)


def _is_locked(lock: Lock, value: Any) -> bool:
    if lock.equals is None:
        return bool(value)
    return value in lock.equals
