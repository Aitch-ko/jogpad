"""Service threads with a fake firmware. Waits on results, never on fixed sleeps."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any

from jogpad import ch57x
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

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        if self.fail_query:
            raise BackendError("down")
        return self.status

    def move(self, axis: str, distance: float, feed: float) -> None:
        self.calls.append(("move", axis))
        self.called.set()

    def home(self, axes: list[str]) -> None:
        self.calls.append(("home",))

    def emergency_stop(self) -> None:
        self.calls.append(("stop",))

    def notify(self, message: str) -> None:
        pass


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
