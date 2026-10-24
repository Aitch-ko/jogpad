from pathlib import Path

import pytest
from pydantic import ValidationError

from jogpad.config import Action, load_config


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "jogpad.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_without_file_numpad_zero_is_stop() -> None:
    assert load_config(None).input.keys[Action.STOP] == ["KEY_KP0"]


def test_file_overrides_feed_rate(tmp_path: Path) -> None:
    path = write(tmp_path, "[jog]\nfeed_xy = 1200\n")
    assert load_config(path).jog.feed_xy == 1200


def test_file_keeps_defaults_of_other_sections(tmp_path: Path) -> None:
    path = write(tmp_path, "[jog]\nfeed_xy = 1200\n")
    assert load_config(path).server.port == 7150


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "[jog]\nfeed_xyz = 1200\n")
    with pytest.raises(ValidationError):
        load_config(path)


def test_negative_feed_rate_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "[jog]\nfeed_z = -5\n")
    with pytest.raises(ValidationError):
        load_config(path)
