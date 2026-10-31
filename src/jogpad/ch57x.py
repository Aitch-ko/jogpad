"""Programs CH57x macro pads through their vendor HID interface (Linux hidraw).

The messages are those of the k884x pads in ch57x-keyboard-tool (MIT): 64 bytes
each, starting with report ID 3. Every binding is followed by the tool's closing
messages, after which the pad stores it. The read request comes from the
vendor's Windows software: the pad answers it with one message per key, laid out
like the binding it holds. A backlight message takes effect at once, and the pad
keeps its colour when unplugged, closing messages or not.
"""

from __future__ import annotations

import os
import select
import time
from collections.abc import Iterable
from pathlib import Path

from jogpad.keys import KEY_CODES, parse_key
from jogpad.layouts import Control, Layout, Part

# 1189:8890 pads speak another protocol; these two take k884x messages.
USB_IDS = {(0x1189, 0x8840), (0x1189, 0x8842)}
REPORT_ID = 3
MESSAGE_SIZE = 64
MAX_KEYS = 15
MAX_KNOBS = 3
KNOB_PARTS: dict[Part, int] = {"ccw": 0, "press": 1, "cw": 2}
# Written back to back, a real pad once lost the last 2 of 18 bindings and kept
# all of them on an identical second run; a short pause gives it time to store.
PAUSE_S = 0.025
# The pad answers a read request at once; a second of silence means it is done,
# or does not know the request.
READ_TIMEOUT_S = 1.0
# Usage page 0xFF00 marks the vendor interface; the pad's other hidraw nodes
# are its keyboard, mouse and media keys.
VENDOR_PAGE = bytes([0x06, 0x00, 0xFF])
# Colours as the pad numbers them, and the mode that keeps all keys lit.
RED, YELLOW, GREEN = 1, 3, 4
BACKLIGHT = 1

# HID usages of the keys jogpad programs: F13 to F24, then International1 to 6.
HID_USAGES: dict[int, int] = {KEY_CODES[f"F{13 + i}"]: 0x68 + i for i in range(12)} | {
    KEY_CODES[name]: 0x87 + i
    for i, name in enumerate(("RO", "KATAKANAHIRAGANA", "YEN", "HENKAN", "MUHENKAN", "KPJPCOMMA"))
}


Binding = tuple[Control, Part, str]


def messages(layout: Layout) -> list[bytes]:
    """Everything to write for `layout`; ValueError if a pad cannot hold it."""
    return messages_for(bindings(layout))


def messages_for(items: Iterable[Binding]) -> list[bytes]:
    result = []
    for control, part, name in items:
        result += bind(_key_id(control, part), _usage(name))
    return result


def bindings(layout: Layout) -> list[Binding]:
    return [(c, part, name) for c in layout.controls for part, name in c.keys.items()]


def bind(key_id: int, usage: int) -> list[bytes]:
    """One key without modifiers, on the pad's first layer."""
    return [
        _message(0xFE, key_id, 1, 0x01, 0, 0, 0, 0, 0, 1, 0, usage),
        _message(0xAA, 0xAA),
        _message(0xFD, 0xFE, 0xFF),
        _message(0xAA, 0xAA),
    ]


def fits(layout: Layout) -> bool:
    """Whether `layout` is drawn after a CH57x pad, its controls numbered by slot."""
    return any(c.slot is not None for c in layout.controls)


def backlight(colour: int) -> bytes:
    """All keys of the pad's first layer lit in `colour`."""
    return _message(0xFE, 0xB0, 1, 0x08, 0, 0, 0, 0, 0, 1, 0, colour << 4 | BACKLIGHT)


def step_colour(step: float, steps: list[float]) -> int | None:
    """Green for the smallest step, red for the largest, yellow between; None with one step."""
    sizes = sorted(set(steps))
    if step not in sizes or len(sizes) < 2:
        return None
    if step == sizes[0]:
        return GREEN
    return RED if step == sizes[-1] else YELLOW


def light(colour: int) -> None:
    """Lights the first pad in `colour`; LookupError if there is none."""
    # Looked up each time: a pad plugged in again may come back as another node.
    write(find_pad(), [backlight(colour)])


def read_request(layout: Layout) -> tuple[bytes, int]:
    """The request for every key and knob up to the layout's last, and the number of answers."""
    keys, knobs = _slots(layout, "key"), _slots(layout, "knob")
    return _message(0xFA, keys, knobs, 1), keys + 3 * knobs


def check(device: Path, layout: Layout) -> list[Binding] | None:
    """Reads the pad back: bindings of `layout` it lacks, None if it does not answer."""
    request, count = read_request(layout)
    return missing(layout, read(device, request, count))


def missing(layout: Layout, answers: Iterable[bytes]) -> list[Binding] | None:
    """Bindings of `layout` the pad does not hold; None if no answer is one to a read request."""
    held: dict[int, int | None] = {}
    for answer in answers:
        if answer[:2] == bytes([REPORT_ID, 0xFA]) and len(answer) > 12:
            kind, count, modifiers, usage = answer[4], answer[10], answer[11], answer[12]
            held[answer[2]] = usage if (kind, count, modifiers) == (1, 1, 0) else None
    if not held:
        return None
    return [b for b in bindings(layout) if held.get(_key_id(b[0], b[1])) != _usage(b[2])]


def find_pad(hidraw: Path = Path("/sys/class/hidraw")) -> Path:
    """The /dev/hidraw node of the first pad's vendor interface; LookupError if none."""
    for node in sorted(hidraw.glob("hidraw*")):
        device = node / "device"
        if (
            _usb_id(device / "uevent") in USB_IDS
            and VENDOR_PAGE in (device / "report_descriptor").read_bytes()
        ):
            return Path("/dev") / node.name
    raise LookupError("no CH57x pad")


def write(device: Path, data: Iterable[bytes]) -> None:
    fd = os.open(device, os.O_WRONLY)
    try:
        for message in data:
            os.write(fd, message)
            time.sleep(PAUSE_S)
    finally:
        os.close(fd)


def read(device: Path, request: bytes, count: int) -> list[bytes]:
    """Up to `count` answers to `request`; fewer when the pad falls silent."""
    fd = os.open(device, os.O_RDWR)
    try:
        os.write(fd, request)
        answers: list[bytes] = []
        while len(answers) < count and select.select([fd], [], [], READ_TIMEOUT_S)[0]:
            answers.append(os.read(fd, MESSAGE_SIZE))
        return answers
    finally:
        os.close(fd)


def _key_id(control: Control, part: Part) -> int:
    slot = control.slot
    if control.kind == "key" and slot is not None and slot < MAX_KEYS:
        return slot + 1
    if control.kind == "knob" and slot is not None and slot < MAX_KNOBS:
        return 16 + 3 * slot + KNOB_PARTS[part]
    raise ValueError(f"{control.id} has no {control.kind} slot a CH57x pad knows: {slot}")


def _slots(layout: Layout, kind: str) -> int:
    return max(
        (c.slot + 1 for c in layout.controls if c.kind == kind and c.slot is not None), default=0
    )


def _usage(name: str) -> int:
    code = parse_key(name)
    if code not in HID_USAGES:
        raise ValueError(f"{name} cannot be programmed, only F13 to F24 and International1 to 6")
    return HID_USAGES[code]


def _message(*data: int) -> bytes:
    return bytes([REPORT_ID, *data]).ljust(MESSAGE_SIZE, b"\0")


def _usb_id(uevent: Path) -> tuple[int, int] | None:
    for line in uevent.read_text(encoding="utf-8").splitlines():
        if line.startswith("HID_ID="):
            _, vendor, product = line.removeprefix("HID_ID=").split(":")
            return int(vendor, 16), int(product, 16)
    return None
