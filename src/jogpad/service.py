"""Wires input devices, the core and the firmware together in background threads."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

from jogpad.ch57x import step_colour
from jogpad.config import Config
from jogpad.core import KEY_AUTOREPEAT, KEY_PRESS, Backend, BackendError, Jogger, State
from jogpad.events import EventHub
from jogpad.linux_input import read_device

log = logging.getLogger(__name__)


class Service:
    def __init__(
        self,
        jogger: Jogger,
        backend: Backend,
        devices: list[str],
        light: Callable[[int], None] | None = None,
    ) -> None:
        self.jogger = jogger
        self.backend = backend
        self.devices = devices
        self.light = light
        self._colour: int | None = None
        self.stop_event = threading.Event()
        self.events = EventHub()
        self._events: queue.Queue[tuple[int, int]] = queue.Queue()
        self._state = jogger.state()
        # The worker holds it while it handles keys, reload() while it swaps the config.
        self._lock = threading.Lock()
        self._learn_until = 0.0

    def state(self) -> State:
        return self._state

    def is_learning(self) -> bool:
        return time.monotonic() < self._learn_until

    def learn(self, seconds: float) -> None:
        """Keys only show up on the web page for `seconds`; 0 ends it early."""
        self._learn_until = time.monotonic() + seconds

    def reload(self, config: Config) -> None:
        with self._lock:
            self.jogger.reconfigure(config)
            self._state = self.jogger.state()

    def start(self) -> None:
        for path in self.devices:
            threading.Thread(
                target=read_device, args=(path, self.on_key, self.stop_event), daemon=True
            ).start()
        threading.Thread(target=self._work, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()

    def on_key(self, code: int, value: int) -> None:
        # STOP goes out from the reader thread and does not wait for a running move.
        # It works while learning, too, but not while jogpad is switched off. A
        # switch that cannot be read does not hold STOP back.
        if self.jogger.is_stop(code):
            if value == KEY_PRESS and self.jogger.switch_state() is not False:
                self._emergency_stop()
        elif not self.is_learning():
            self._events.put((code, value))
        if value != KEY_AUTOREPEAT:
            self.events.publish((code, value))

    def _emergency_stop(self) -> None:
        try:
            self.backend.emergency_stop()
            log.warning("STOP: emergency stop sent")
        except BackendError as exc:
            log.error("STOP failed: %s", exc)

    def _work(self) -> None:
        while not self.stop_event.is_set():
            deadline = self.jogger.next_deadline()
            timeout = 0.5 if deadline is None else max(0.0, deadline - time.monotonic())
            batch = []
            try:
                batch.append(self._events.get(timeout=timeout))
                while True:
                    batch.append(self._events.get_nowait())
            except queue.Empty:
                pass
            with self._lock:
                self.jogger.handle(batch, time.monotonic())
                self.jogger.tick(time.monotonic())
                self._state = self.jogger.state()
            self._light_step()

    def _light_step(self) -> None:
        colour = step_colour(self._state.step, self.jogger.config.jog.steps)
        # Only a new colour is written: the pad stores each one in flash. One that
        # fails is not tried again until the step changes, or this loop would log
        # every half second while the pad is unplugged.
        if self.light is None or colour is None or colour == self._colour:
            return
        self._colour = colour
        try:
            self.light(colour)
        except (OSError, LookupError) as exc:
            log.warning("pad not lit in the step's colour: %s", exc)
