import struct

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
