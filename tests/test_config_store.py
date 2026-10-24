from pathlib import Path

import pytest
from pydantic import ValidationError

from jogpad.config import Action, Config, load_config
from jogpad.config_store import assign_keys, conflicts, set_invert

HAND_WRITTEN = """# my pad
[input]
devices = ["/dev/input/by-id/pad"]  # the left one
"""


def config_file(tmp_path: Path, text: str = HAND_WRITTEN) -> Path:
    path = tmp_path / "jogpad.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_assigned_key_is_saved(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    assign_keys(path, Config(), Action.X_PLUS, ["KEY_F13"])
    assert load_config(path).input.keys[Action.X_PLUS] == ["KEY_F13"]


def test_comments_survive_a_change(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    assign_keys(path, Config(), Action.X_PLUS, ["KEY_F13"])
    assert "# the left one" in path.read_text(encoding="utf-8")


def test_key_moves_away_from_its_old_action(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    assign_keys(path, Config(), Action.HOME, ["KEY_KP6"])
    assert load_config(path).input.keys[Action.X_PLUS] == []


def test_returned_config_is_the_saved_one(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    config = assign_keys(path, Config(), Action.X_PLUS, ["KEY_F13"])
    assert config == load_config(path)


def test_missing_file_is_created(tmp_path: Path) -> None:
    path = tmp_path / "new.toml"
    set_invert(path, ["Y"])
    assert load_config(path).jog.invert == ["Y"]


def test_invalid_change_leaves_file_alone(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    with pytest.raises(ValidationError):
        set_invert(path, ["Q"])
    assert path.read_text(encoding="utf-8") == HAND_WRITTEN


def test_conflict_names_the_other_action() -> None:
    assert conflicts(Config(), Action.HOME, ["KEY_KP6"]) == {"KEY_KP6": Action.X_PLUS}


def test_own_key_is_no_conflict() -> None:
    assert conflicts(Config(), Action.X_PLUS, ["KEY_KP6"]) == {}
