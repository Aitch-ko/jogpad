"""Linux key codes by name, as in `linux/input-event-codes.h`.

Only the keys a pad is likely to send. Any other key can be given by number.
"""

from __future__ import annotations

KEY_CODES: dict[str, int] = {
    "ESC": 1,
    "BACKSPACE": 14,
    "TAB": 15,
    "ENTER": 28,
    "SPACE": 57,
    "KPASTERISK": 55,
    "NUMLOCK": 69,
    "KP7": 71,
    "KP8": 72,
    "KP9": 73,
    "KPMINUS": 74,
    "KP4": 75,
    "KP5": 76,
    "KP6": 77,
    "KPPLUS": 78,
    "KP1": 79,
    "KP2": 80,
    "KP3": 81,
    "KP0": 82,
    "KPDOT": 83,
    "KPENTER": 96,
    "KPSLASH": 98,
    "HOME": 102,
    "UP": 103,
    "PAGEUP": 104,
    "LEFT": 105,
    "RIGHT": 106,
    "END": 107,
    "DOWN": 108,
    "PAGEDOWN": 109,
    "INSERT": 110,
    "DELETE": 111,
    "MUTE": 113,
    "VOLUMEDOWN": 114,
    "VOLUMEUP": 115,
    "F11": 87,
    "F12": 88,
    # International1 to 6 in HID: macro pads can send them and no desktop
    # reacts to them, which gives knob turns six more codes next to F13-F24.
    "RO": 89,
    "KATAKANAHIRAGANA": 93,
    "YEN": 124,
    "HENKAN": 92,
    "MUHENKAN": 94,
    "KPJPCOMMA": 95,
}
KEY_CODES.update({c: 16 + i for i, c in enumerate("QWERTYUIOP")})
KEY_CODES.update({c: 30 + i for i, c in enumerate("ASDFGHJKL")})
KEY_CODES.update({c: 44 + i for i, c in enumerate("ZXCVBNM")})
KEY_CODES.update({str((i + 1) % 10): 2 + i for i in range(10)})
KEY_CODES.update({f"F{i + 1}": 59 + i for i in range(10)})
KEY_CODES.update({f"F{i + 13}": 183 + i for i in range(12)})

KEY_NAMES: dict[int, str] = {code: f"KEY_{name}" for name, code in KEY_CODES.items()}


def parse_key(text: str) -> int:
    """'KEY_A', 'a' or '30' -> 30."""
    name = text.strip().upper()
    if name.isdigit():
        return int(name)
    name = name.removeprefix("KEY_")
    if name not in KEY_CODES:
        raise ValueError(f"unknown key {text!r}; give its number instead (see `jogpad keys`)")
    return KEY_CODES[name]


def key_name(code: int) -> str:
    return KEY_NAMES.get(code, str(code))
