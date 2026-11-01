"""Turns key events into moves. No devices, no network: a `Backend` does the I/O.

`handle()` gets every key event that arrived since the last call. Presses that
pile up while the previous move is running become one move, so the axis stops
when the user stops turning instead of working off a queue.

An axis key held for `hold_delay` keeps its axis moving until it is released:
`tick()` reads how much the firmware has queued and tops it up with a short move,
never to more than it needs to run smoothly, since a queued move cannot be taken
back.
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

# Klipper macro behind the on/off switch in Mainsail and Fluidd, see klipper/jogpad.cfg
# next to this module.
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

# Klipper takes a move into its queue 0.1 s after it arrives and starts it no
# sooner than 0.25 s after that.
KLIPPER_START_S = 0.35
# Klipper answers a status query at its next status update, every 0.25 s. At each
# answer a held key tops the queue up to this: enough to last until the next answer
# and still start the move queued then on time. The axis runs on for up to this
# long after the key is released.
HOLD_QUEUE_S = 0.65
# Not sooner than this after a move, so the queue read shows it.
HOLD_POLL_S = 0.15
HOLD_MIN_MOVE_S = 0.05
# Silence between two beeps, so they can be counted.
BEEP_PAUSE = "G4 P150"


class BackendError(Exception):
    pass


class Backend(Protocol):
    """What the core needs from a firmware. Calls block until the firmware is done."""

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]: ...

    def move(self, axis: str, distance: float, feed: float) -> None: ...

    def queue_move(self, axis: str, distance: float, feed: float) -> None:
        """Like `move`, but returns once the firmware has the move, not when it is done."""
        ...

    def motion_left(self) -> float:
        """Seconds until the firmware has worked off the moves it has queued.

        May take a while: Klipper answers at its next status update.
        """
        ...

    def home(self, axes: list[str]) -> None: ...

    def emergency_stop(self) -> None: ...

    def notify(self, message: str) -> None: ...

    def gcode(self, script: str) -> None: ...


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


@dataclass
class _Hold:
    """An axis key from its press to its release."""

    code: int
    axis: str
    sign: int
    # When to start moving, then when to top up the firmware's queue next.
    due: float
    # The locks were checked for the press's own step.
    is_checked: bool = False
    is_moving: bool = False
    is_stopped: bool = False
    moved: float = 0.0


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
        self._hold: _Hold | None = None
        # Read once for the presses in one call of handle().
        self._status: dict[str, dict[str, Any]] | None = None

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
        return _switch_in(status)

    def switch_state(self) -> bool | None:
        """Whether jogpad is on; None if the switch cannot be read.

        Without the macro in Klipper there is no switch, and jogpad is always on.
        """
        switch = self.switch()
        return None if switch is Switch.UNREADABLE else switch is not Switch.OFF

    def handle(self, events: list[tuple[int, int]], now: float) -> None:
        is_allowed = True
        if any(value == KEY_PRESS for _, value in events):
            # Switch and locks in one query: Klipper answers it only at its next status
            # update, up to 0.25 s later.
            objects = self._lock_objects()
            objects.setdefault(SWITCH, []).append("value")
            try:
                self._status = self.backend.query(objects)
            except BackendError as exc:
                log.warning("status not readable: %s", exc)
            if self._status is None:
                self._last_refusal = t("status.unreadable", self.language)
                self._notify("refused", reason=self._last_refusal)
                self._beep_refusal()
                is_allowed = False
            elif _switch_in(self._status) is Switch.OFF:
                # Switched off means off: no moves, no console messages. The refusal
                # sound stays, or a key would seem dead to someone not looking.
                self._last_refusal = t("switch.off", self.language)
                self._beep_refusal()
                is_allowed = False
        moves: list[list[Any]] = []
        for code, value in events:
            # Releases count even when presses are refused: one may end a held key.
            if value == KEY_RELEASE and self._hold is not None and self._hold.code == code:
                self._end_hold()
            action = self.actions.get(code)
            # Held keys repeat in the kernel; the press and the release time a hold.
            if action is None or value != KEY_PRESS or not is_allowed:
                continue
            if self._hold is not None:
                self._end_hold()
            if self._home_axes is not None:
                self._handle_home_key(action)
                continue
            if action in AXIS_ACTIONS:
                axis, sign = AXIS_ACTIONS[action]
                self._add_move(moves, axis, sign * self.step)
                self._hold = _Hold(code, axis, sign, due=now + self.config.jog.hold_delay)
            elif action in (Action.SELECTED_PLUS, Action.SELECTED_MINUS):
                sign = 1 if action is Action.SELECTED_PLUS else -1
                self._add_move(moves, self._selected, sign * self.step)
                self._hold = _Hold(code, self._selected, sign, due=now + self.config.jog.hold_delay)
            elif action is Action.SELECT_NEXT:
                self._flush(moves)
                axes = self.config.jog.select_axes
                self._selected = axes[(axes.index(self._selected) + 1) % len(axes)]
                self._notify("axis.selected", axis=self._selected)
            elif action is Action.STEP:
                self._flush(moves)
                self._step_index = (self._step_index + 1) % len(self.config.jog.steps)
                self._notify("step.changed", step=f"{self.step:g}")
                self._beep_step()
            elif action is Action.HOME:
                self._flush(moves)
                self._home_axes = []
                self._home_deadline = now + self.config.jog.home_timeout
                self._notify("home.select")
        self._flush(moves)
        # The status belongs to these presses; a hold that starts later reads its own.
        self._status = None

    def tick(self, now: float) -> None:
        if self._home_axes is not None and now >= self._home_deadline:
            self._home_axes = None
            self._notify("home.cancelled")
        hold = self._hold
        if hold is not None and not hold.is_stopped and now >= hold.due:
            self._keep_moving(hold, now)

    def next_deadline(self) -> float | None:
        deadlines = []
        if self._home_axes is not None:
            deadlines.append(self._home_deadline)
        if self._hold is not None and not self._hold.is_stopped:
            deadlines.append(self._hold.due)
        return min(deadlines, default=None)

    # -- internals ----------------------------------------------------------

    def _keep_moving(self, hold: _Hold, now: float) -> None:
        hold.due = now + HOLD_POLL_S
        if hold.is_moving:
            try:
                left = self.backend.motion_left()
            except BackendError as exc:
                log.warning("queue not readable, held key stopped: %s", exc)
                hold.is_stopped = True
                return
        else:
            # Presses that cancelled out moved nothing, so nothing was checked.
            if not hold.is_checked and self._refused():
                hold.is_stopped = True
                return
            hold.is_moving = True
            # The press's own step was waited for, so nothing is queued.
            left = 0.0
        duration = HOLD_QUEUE_S - max(left, KLIPPER_START_S)
        if duration < HOLD_MIN_MOVE_S:
            return
        jog = self.config.jog
        speeds = {
            "X": jog.hold_speeds_xy,
            "Y": jog.hold_speeds_xy,
            "Z": jog.hold_speeds_z,
            "E": jog.hold_speeds_e,
        }
        speed = speeds[hold.axis][self._step_index]
        sign = -hold.sign if hold.axis in jog.invert else hold.sign
        distance = round(sign * speed * duration, 3)
        if not self._call(self.backend.queue_move, hold.axis, distance, speed * 60):
            self._beep_refusal()
            hold.is_stopped = True
            return
        hold.moved += distance

    def _end_hold(self) -> None:
        assert self._hold is not None
        hold, self._hold = self._hold, None
        if hold.moved and self.config.jog.announce_moves:
            self._notify("moved", axis=hold.axis, distance=f"{round(hold.moved, 3):+g}")

    def _beep_step(self) -> None:
        # Once for the smallest step, twice for the next: the step size without a look.
        beep = self.config.input.step_beep
        if beep:
            script = f"\n{BEEP_PAUSE}\n".join([beep] * (self._step_index + 1))
            self._call(self.backend.gcode, script)

    def _beep_refusal(self) -> None:
        beep = self.config.input.refusal_beep
        if beep:
            self._call(self.backend.gcode, beep)

    def _handle_home_key(self, action: Action) -> None:
        assert self._home_axes is not None
        if action in AXIS_ACTIONS and AXIS_ACTIONS[action][0] != "E":
            axis = AXIS_ACTIONS[action][0]
            if axis in self._home_axes:
                self._home_axes.remove(axis)
            else:
                self._home_axes.append(axis)
            if self._home_axes:
                self._notify("home.selected", axes=" ".join(sorted(self._home_axes)))
            else:
                self._notify("home.select")
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
        if not self._call(self.backend.home, axes):
            self._beep_refusal()

    @staticmethod
    def _add_move(moves: list[list[Any]], axis: str, distance: float) -> None:
        if moves and moves[-1][0] == axis:
            moves[-1][1] += distance
        else:
            moves.append([axis, distance])

    def _flush(self, moves: list[list[Any]]) -> None:
        pending = [(axis, distance) for axis, distance in moves if abs(distance) > 1e-9]
        moves.clear()
        if not pending:
            return
        # A held key goes on from its press's step, so it shares that step's check.
        if self._refused():
            if self._hold is not None:
                self._hold.is_stopped = True
            return
        if self._hold is not None:
            self._hold.is_checked = True
        jog = self.config.jog
        feeds = {"X": jog.feed_xy, "Y": jog.feed_xy, "Z": jog.feed_z, "E": jog.feed_e}
        for axis, distance in pending:
            distance = round(-distance if axis in jog.invert else distance, 6)
            if not self._call(self.backend.move, axis, distance, feeds[axis]):
                self._beep_refusal()
                break
            if jog.announce_moves:
                self._notify("moved", axis=axis, distance=f"{distance:+g}")

    def _refused(self) -> bool:
        reason = self._lock_reason()
        self._last_refusal = reason
        if reason is not None:
            self._notify("refused", reason=reason)
            self._beep_refusal()
        return reason is not None

    def _lock_objects(self) -> dict[str, list[str]]:
        objects: dict[str, list[str]] = {}
        for lock in self.config.machine.locks:
            objects.setdefault(lock.object, []).append(lock.field)
        return objects

    def _lock_reason(self) -> str | None:
        status = self._status
        if status is None:
            objects = self._lock_objects()
            try:
                status = self.backend.query(objects) if objects else {}
            except BackendError as exc:
                log.warning("status not readable: %s", exc)
                return t("status.unreadable", self.language)
        for lock in self.config.machine.locks:
            value = status.get(lock.object, {}).get(lock.field)
            # Klipper answers for an object or field that does not exist with null.
            # A typo in a laser lock must not quietly switch it off.
            if value is None:
                return t("lock.missing", self.language, object=lock.object, field=lock.field)
            if _is_locked(lock, value):
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


def _switch_in(status: dict[str, dict[str, Any]]) -> Switch:
    # Klipper answers for a macro that does not exist with value null.
    value = status.get(SWITCH, {}).get("value")
    if value is None:
        return Switch.MISSING
    return Switch.ON if value else Switch.OFF


def _is_locked(lock: Lock, value: Any) -> bool:
    if lock.equals is None:
        return bool(value)
    return value in lock.equals
