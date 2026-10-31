from pathlib import Path

import pytest
from pydantic import ValidationError

from jogpad.config import Action, InputConfig, load_config
from jogpad.keys import parse_key
from jogpad.layouts import Part, load_layout

KP0 = 82


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "jogpad.toml"
    path.write_text(text, encoding="utf-8")
    return path


def ch57x_action(control_id: str, part: Part, **keys: list[str]) -> Action | None:
    """What a control of the CH57x pad does with layout `ch57x-9k3` and `keys`."""
    control = next(c for c in load_layout("ch57x-9k3").controls if c.id == control_id)
    config = InputConfig.model_validate({"layout": "ch57x-9k3", "keys": keys})
    return config.actions_by_code().get(parse_key(control.keys[part]))


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


def test_own_key_keeps_numpad_default_for_others(tmp_path: Path) -> None:
    path = write(tmp_path, '[input.keys]\nx_plus = ["KEY_D"]\n')
    assert load_config(path).input.keys[Action.STOP] == ["KEY_KP0"]


def test_own_key_replaces_numpad_key_of_that_action(tmp_path: Path) -> None:
    path = write(tmp_path, '[input.keys]\nx_plus = ["KEY_D"]\n')
    assert load_config(path).input.actions_by_code().get(77) is None


def test_empty_list_switches_an_action_off(tmp_path: Path) -> None:
    path = write(tmp_path, "[input.keys]\nstop = []\n")
    assert 82 not in load_config(path).input.actions_by_code()


def test_key_used_twice_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, '[input.keys]\nx_plus = ["KEY_D"]\nhome = ["KEY_D"]\n')
    with pytest.raises(ValidationError):
        load_config(path)


def test_unknown_key_name_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, '[input.keys]\nx_plus = ["KEY_NOPE"]\n')
    with pytest.raises(ValidationError):
        load_config(path)


def test_lock_from_file_is_read(tmp_path: Path) -> None:
    text = '[[machine.locks]]\nobject = "spindle"\nfield = "speed"\nreason = "spindle on"\n'
    assert load_config(write(tmp_path, text)).machine.locks[0].reason == "spindle on"


def test_ch57x_big_knob_turned_right_moves_z_up() -> None:
    assert ch57x_action("knob3", "cw") is Action.Z_PLUS


def test_ch57x_top_knob_turned_left_moves_x_down() -> None:
    assert ch57x_action("knob1", "ccw") is Action.X_MINUS


def test_ch57x_middle_knob_turned_right_moves_y_up() -> None:
    assert ch57x_action("knob2", "cw") is Action.Y_PLUS


def test_ch57x_key_above_the_middle_moves_y_up() -> None:
    assert ch57x_action("k2", "press") is Action.Y_PLUS


def test_ch57x_key_left_of_the_middle_moves_x_down() -> None:
    assert ch57x_action("k4", "press") is Action.X_MINUS


def test_ch57x_middle_key_changes_the_step() -> None:
    assert ch57x_action("k5", "press") is Action.STEP


def test_ch57x_top_right_key_is_stop() -> None:
    assert ch57x_action("k3", "press") is Action.STOP


def test_ch57x_knob_presses_do_nothing() -> None:
    presses = [ch57x_action(knob, "press") for knob in ("knob1", "knob2", "knob3")]
    assert presses == [None, None, None]


def test_ch57x_layout_drops_the_numpad_defaults() -> None:
    config = InputConfig.model_validate({"layout": "ch57x-9k3"})
    assert KP0 not in config.actions_by_code()


def test_ch57x_own_key_keeps_the_pad_default_for_others() -> None:
    assert ch57x_action("k3", "press", home=["KEY_H"]) is Action.STOP


def test_unknown_layout_is_rejected_in_config(tmp_path: Path) -> None:
    path = write(tmp_path, '[input]\nlayout = "nope"\n')
    with pytest.raises(ValidationError):
        load_config(path)
