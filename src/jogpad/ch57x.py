"""Programs CH57x macro pads through their vendor HID interface (Linux hidraw).

The messages are those of the k884x pads in ch57x-keyboard-tool (MIT): 64 bytes
each, starting with report ID 3. The pad answers none of them. Every binding is
followed by the tool's closing messages, after which the pad stores it.
"""

from __future__ import annotations

import os
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
# Usage page 0xFF00 marks the vendor interface; the pad's other hidraw nodes
# are its keyboard, mouse and media keys.
VENDOR_PAGE = bytes([0x06, 0x00, 0xFF])

# HID usages of the keys jogpad programs: F13 to F24, then International1 to 6.
HID_USAGES: dict[int, int] = {KEY_CODES[f"F{13 + i}"]: 0x68 + i for i in range(12)} | {
    KEY_CODES[name]: 0x87 + i
    for i, name in enumerate(("RO", "KATAKANAHIRAGANA", "YEN", "HENKAN", "MUHENKAN", "KPJPCOMMA"))
}


def messages(layout: Layout) -> list[bytes]:
    """Everything to write for `layout`; ValueError if a pad cannot hold it."""
    result = []
    for control in layout.controls:
        for part, name in control.keys.items():
            result += bind(_key_id(control, part), _usage(name))
    return result


def bind(key_id: int, usage: int) -> list[bytes]:
    """One key without modifiers, on the pad's first layer."""
    return [
        _message(0xFE, key_id, 1, 0x01, 0, 0, 0, 0, 0, 1, 0, usage),
        _message(0xAA, 0xAA),
        _message(0xFD, 0xFE, 0xFF),
        _message(0xAA, 0xAA),
    ]


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


def _key_id(control: Control, part: Part) -> int:
    slot = control.slot
    if control.kind == "key" and slot is not None and slot < MAX_KEYS:
        return slot + 1
    if control.kind == "knob" and slot is not None and slot < MAX_KNOBS:
        return 16 + 3 * slot + KNOB_PARTS[part]
    raise ValueError(f"{control.id} has no {control.kind} slot a CH57x pad knows: {slot}")


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
