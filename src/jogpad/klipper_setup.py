"""Sets up the on/off switch: the macro for Klipper, its include, Moonraker's power device.

Both config files belong to the user, so each is backed up before it changes and
only changes when its entry is missing. Running it again only refreshes the macro.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

MACRO = Path(__file__).parent / "klipper" / "jogpad.cfg"
INCLUDE = "[include jogpad.cfg]"
POWER = "[power jogpad]\ntype: klipper_device\nobject_name: gcode_macro _JOGPAD\n"


def setup_switch(config_dir: Path, now: datetime) -> list[Path]:
    """Writes the macro and adds what is missing. Returns the backups it made."""
    printer = config_dir / "printer.cfg"
    moonraker = config_dir / "moonraker.conf"
    texts = {path: path.read_text(encoding="utf-8") for path in (printer, moonraker)}
    (config_dir / "jogpad.cfg").write_text(MACRO.read_text(encoding="utf-8"), encoding="utf-8")
    backups = []
    if not _has_section(texts[printer], r"include\s+jogpad\.cfg"):
        backups.append(_backup(printer, now))
        printer.write_text(_with_include(texts[printer]), encoding="utf-8")
    if not _has_section(texts[moonraker], r"power\s+jogpad"):
        backups.append(_backup(moonraker, now))
        moonraker.write_text(_ending_in_newline(texts[moonraker]) + "\n" + POWER, encoding="utf-8")
    return backups


def _has_section(text: str, name: str) -> bool:
    return re.search(rf"^\[{name}\]", text, re.MULTILINE) is not None


def _with_include(text: str) -> str:
    # Klipper wants the SAVE_CONFIG block at the very end of printer.cfg.
    block = re.search(r"^#\*#", text, re.MULTILINE)
    if block is None:
        return _ending_in_newline(text) + "\n" + INCLUDE + "\n"
    return text[: block.start()] + INCLUDE + "\n\n" + text[block.start() :]


def _ending_in_newline(text: str) -> str:
    return text if not text or text.endswith("\n") else text + "\n"


def _backup(path: Path, now: datetime) -> Path:
    backup = path.with_name(f"{path.name}.bak-{now:%Y%m%d-%H%M%S}")
    backup.write_bytes(path.read_bytes())
    return backup
