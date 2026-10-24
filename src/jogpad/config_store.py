"""Changes to jogpad.toml from the web page.

Edits go through tomlkit so that comments and layout of a hand-written file
survive. Every change is validated as a whole before the file is replaced.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import tomlkit
from tomlkit.items import Table

from jogpad.config import Action, Config
from jogpad.keys import parse_key


def conflicts(config: Config, action: Action, keys: list[str]) -> dict[str, Action]:
    """Keys from `keys` that already trigger another action."""
    by_code = config.input.actions_by_code()
    found = {}
    for name in keys:
        other = by_code.get(parse_key(name))
        if other is not None and other is not action:
            found[name] = other
    return found


def assign_keys(path: Path, config: Config, action: Action, keys: list[str]) -> Config:
    """Give `action` exactly `keys`, taking them away from other actions."""
    codes = {parse_key(name) for name in keys}
    changes = {action: keys}
    for other in set(conflicts(config, action, keys).values()):
        remaining = [n for n in config.input.keys[other] if parse_key(n) not in codes]
        changes[other] = remaining

    def change(doc: tomlkit.TOMLDocument) -> None:
        _table(doc, "input", "keys").update({a.value: names for a, names in changes.items()})

    return _update(path, change)


def set_invert(path: Path, axes: list[str]) -> Config:
    def change(doc: tomlkit.TOMLDocument) -> None:
        _table(doc, "jog")["invert"] = sorted(axes)

    return _update(path, change)


def _update(path: Path, change: Callable[[tomlkit.TOMLDocument], None]) -> Config:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    doc = tomlkit.parse(text)
    change(doc)
    config = Config.model_validate(doc.unwrap())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(tomlkit.dumps(doc), encoding="utf-8")
    os.replace(tmp, path)
    return config


def _table(doc: tomlkit.TOMLDocument, first: str, *rest: str) -> Table:
    parent: tomlkit.TOMLDocument | Table = doc
    for name in (first, *rest):
        if name not in parent:
            parent[name] = tomlkit.table()
        item = parent[name]
        if not isinstance(item, Table):
            raise ValueError(f"[{name}] must be a table section to be edited here")
        parent = item
    assert isinstance(parent, Table)  # the loop ran at least once
    return parent
