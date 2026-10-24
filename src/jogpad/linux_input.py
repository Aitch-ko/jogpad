"""Read key events from /dev/input on Linux, without third-party packages."""

from __future__ import annotations

import glob
import logging
import os
import struct
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

EV_KEY = 1
# struct input_event: two C longs of timestamp, then type, code, value.
# Native "l" is 4 bytes on 32-bit userlands (e.g. armhf) and 8 on 64-bit.
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EVIOCGRAB = 0x40044590
RETRY_S = 2.0


def parse_events(data: bytes) -> list[tuple[int, int]]:
    """Raw bytes from an event device -> (code, value) of the key events."""
    events = []
    for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
        _, _, ev_type, code, value = struct.unpack_from(EVENT_FORMAT, data, offset)
        if ev_type == EV_KEY:
            events.append((code, value))
    return events


def list_devices() -> list[str]:
    return sorted(glob.glob("/dev/input/by-id/*-event-*"))


def read_device(
    path: str, on_key: Callable[[int, int], None], stop: threading.Event | None = None
) -> None:
    """Read `path` until `stop` is set, reopening it when it is unplugged.

    The device is grabbed exclusively, so its keys do not also reach a desktop
    or KlipperScreen on the same host.
    """
    import fcntl  # Linux only; imported here so the rest of the package loads elsewhere

    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError as exc:
            log.debug("cannot open %s: %s", path, exc)
            stop.wait(RETRY_S)
            continue
        try:
            fcntl.ioctl(fd, EVIOCGRAB, 1)
            log.info("reading %s", path)
            while not stop.is_set():
                for code, value in parse_events(os.read(fd, EVENT_SIZE * 64)):
                    on_key(code, value)
        except OSError as exc:
            log.warning("lost %s: %s", path, exc)
        finally:
            os.close(fd)
        stop.wait(RETRY_S)
