import struct
import sys
import threading
import types

import pytest

from jogpad import linux_input
from jogpad.linux_input import EVENT_FORMAT, parse_events

EV_SYN, EV_KEY = 0, 1


def test_only_key_events_are_returned() -> None:
    data = (
        struct.pack(EVENT_FORMAT, 1, 2, EV_KEY, 77, 1)
        + struct.pack(EVENT_FORMAT, 1, 2, EV_SYN, 0, 0)
        + struct.pack(EVENT_FORMAT, 1, 3, EV_KEY, 77, 0)
    )
    assert parse_events(data) == [(77, 1), (77, 0)]


def test_incomplete_event_is_ignored() -> None:
    data = struct.pack(EVENT_FORMAT, 1, 2, EV_KEY, 77, 1)
    assert parse_events(data[:-1]) == []


def test_unplugged_device_releases_its_held_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()
    reads = iter([struct.pack(EVENT_FORMAT, 1, 2, EV_KEY, 77, 1)])

    def read(fd: int, size: int) -> bytes:
        for data in reads:
            return data
        stop.set()
        raise OSError(19, "No such device")

    fake_os = types.SimpleNamespace(
        open=lambda path, flags: 3, read=read, close=lambda fd: None, O_RDONLY=0
    )
    monkeypatch.setattr(linux_input, "os", fake_os)
    monkeypatch.setitem(sys.modules, "fcntl", types.SimpleNamespace(ioctl=lambda *args: 0))
    keys: list[tuple[int, int]] = []
    linux_input.read_device("/dev/input/pad", lambda code, value: keys.append((code, value)), stop)
    assert keys == [(77, 1), (77, 0)]
