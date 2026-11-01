"""Service threads with a fake firmware. Waits on results, never on fixed sleeps."""

from __future__ import annotations

import itertools
import queue
import threading
import types
from collections.abc import Callable
from typing import Any

import pytest

from jogpad import ch57x
from jogpad import service as service_module
from jogpad.config import Config
from jogpad.core import KEY_PRESS, KEY_RELEASE, SWITCH, BackendError, Jogger
from jogpad.service import Service

KP6, KP8, KP0 = 77, 72, 82


class FakeBackend:
    def __init__(self, status: dict[str, dict[str, Any]] | None = None) -> None:
        # A printer at rest, so the default print lock finds its object.
        self.status = {"print_stats": {"state": "standby"}, **(status or {})}
        self.fail_query = False
        self.calls: list[tuple[Any, ...]] = []
        self.called = threading.Event()
        self.queued = threading.Event()
        self.notes: queue.Queue[str] = queue.Queue()

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        if self.fail_query:
            raise BackendError("down")
        return self.status

    def move(self, axis: str, distance: float, feed: float) -> None:
        self.calls.append(("move", axis))
        self.called.set()

    def queue_move(self, axis: str, distance: float, feed: float) -> None:
        self.calls.append(("queue", axis))
        self.queued.set()

    def motion_left(self) -> float:
        return 0.0

    def home(self, axes: list[str]) -> None:
        self.calls.append(("home",))

    def emergency_stop(self) -> None:
        self.calls.append(("stop",))

    def notify(self, message: str) -> None:
        self.notes.put(message)

    def gcode(self, script: str) -> None:
        self.calls.append(("gcode",))


def started(
    config: Config | None = None, backend: FakeBackend | None = None
) -> tuple[Service, FakeBackend]:
    backend = backend or FakeBackend()
    service = Service(Jogger(config or Config(), backend), backend, devices=[])
    service.start()
    return service, backend


def tap(service: Service, code: int) -> None:
    service.on_key(code, KEY_PRESS)
    service.on_key(code, KEY_RELEASE)


def test_keys_while_learning_move_nothing() -> None:
    service, backend = started()
    service.learn(30)
    tap(service, KP6)
    service.learn(0)
    tap(service, KP8)
    backend.called.wait(2)
    service.stop()
    assert backend.calls == [("move", "Y")]


def test_release_while_learning_stops_a_held_key() -> None:
    service, backend = started(Config.model_validate({"jog": {"hold_delay": 0.05}}))
    service.on_key(KP6, KEY_PRESS)
    backend.queued.wait(2)
    service.learn(30)
    service.on_key(KP6, KEY_RELEASE)
    # The first note is the step of the press, the second the end of the hold.
    notes = [backend.notes.get(timeout=2), backend.notes.get(timeout=2)]
    service.stop()
    assert notes[1].startswith("X +")


class SlowBackend(FakeBackend):
    """Holds a move of X until the test lets it finish."""

    def __init__(self) -> None:
        super().__init__()
        self.moving_x = threading.Event()
        self.finish_x = threading.Event()
        self.moved_y = threading.Event()

    def move(self, axis: str, distance: float, feed: float) -> None:
        super().move(axis, distance, feed)
        if axis == "X":
            self.moving_x.set()
            self.finish_x.wait(2)
        else:
            self.moved_y.set()


def test_key_let_go_during_its_step_moves_only_that_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every look at the clock is a second later, so a hold is due once the step is done.
    seconds = itertools.count(1000.0)
    monkeypatch.setattr(
        service_module, "time", types.SimpleNamespace(monotonic=lambda: next(seconds))
    )
    backend = SlowBackend()
    service, _ = started(backend=backend)
    service.on_key(KP6, KEY_PRESS)
    backend.moving_x.wait(2)
    service.on_key(KP6, KEY_RELEASE)
    backend.finish_x.set()
    tap(service, KP8)
    backend.moved_y.wait(2)
    service.stop()
    assert backend.calls == [("move", "X"), ("move", "Y")]


def test_stop_works_while_learning() -> None:
    service, backend = started()
    service.learn(30)
    tap(service, KP0)
    service.stop()
    assert backend.calls == [("stop",)]


def test_stop_does_nothing_while_switched_off() -> None:
    service, backend = started(backend=FakeBackend({SWITCH: {"value": 0}}))
    tap(service, KP0)
    service.stop()
    assert backend.calls == []


def test_stop_works_while_the_switch_is_unreadable() -> None:
    backend = FakeBackend()
    backend.fail_query = True
    service, _ = started(backend=backend)
    tap(service, KP0)
    service.stop()
    assert backend.calls == [("stop",)]


def test_reload_applies_new_keys() -> None:
    service, backend = started()
    service.reload(
        Config.model_validate({"input": {"keys": {"x_plus": [], "y_plus": ["KEY_KP6"]}}})
    )
    tap(service, KP6)
    backend.called.wait(2)
    service.stop()
    assert backend.calls == [("move", "Y")]


KP_ASTERISK = 55


def lit(backend: FakeBackend, light: Callable[[int], None]) -> Service:
    service = Service(Jogger(Config(), backend), backend, devices=[], light=light)
    service.start()
    return service


def test_pad_is_lit_in_the_colour_of_the_first_step() -> None:
    colours: queue.Queue[int] = queue.Queue()
    service = lit(FakeBackend(), colours.put)
    colour = colours.get(timeout=2)
    service.stop()
    assert colour == ch57x.GREEN


def test_pad_takes_the_colour_of_the_next_step_and_keeps_it_through_moves() -> None:
    backend = FakeBackend()
    colours: queue.Queue[int] = queue.Queue()
    service = lit(backend, colours.put)
    seen = [colours.get(timeout=2)]
    tap(service, KP6)
    backend.called.wait(2)
    tap(service, KP_ASTERISK)
    seen.append(colours.get(timeout=2))
    service.stop()
    assert seen == [ch57x.GREEN, ch57x.YELLOW]


def test_pad_that_cannot_be_lit_still_jogs() -> None:
    backend = FakeBackend()
    tried = threading.Event()

    def light(colour: int) -> None:
        tried.set()
        raise LookupError("no CH57x pad")

    service = lit(backend, light)
    tried.wait(2)
    tap(service, KP6)
    backend.called.wait(2)
    service.stop()
    assert backend.calls == [("move", "X")]
