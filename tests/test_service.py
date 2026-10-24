"""Service threads with a fake firmware. Waits on results, never on fixed sleeps."""

from __future__ import annotations

import threading
from typing import Any

from jogpad.config import Config
from jogpad.core import KEY_PRESS, KEY_RELEASE, Jogger
from jogpad.service import Service

KP6, KP8, KP0 = 77, 72, 82


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.called = threading.Event()

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        return {}

    def move(self, axis: str, distance: float, feed: float) -> None:
        self.calls.append(("move", axis))
        self.called.set()

    def home(self, axes: list[str]) -> None:
        self.calls.append(("home",))

    def emergency_stop(self) -> None:
        self.calls.append(("stop",))

    def notify(self, message: str) -> None:
        pass


def started(config: Config | None = None) -> tuple[Service, FakeBackend]:
    backend = FakeBackend()
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


def test_reload_applies_new_keys() -> None:
    service, backend = started()
    service.reload(
        Config.model_validate({"input": {"keys": {"x_plus": [], "y_plus": ["KEY_KP6"]}}})
    )
    tap(service, KP6)
    backend.called.wait(2)
    service.stop()
    assert backend.calls == [("move", "Y")]
