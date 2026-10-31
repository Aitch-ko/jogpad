import pytest
from pydantic import ValidationError

from jogpad.layouts import Layout, layout_ids, load_layout

KP6 = 77


@pytest.mark.parametrize("layout_id", layout_ids())
def test_shipped_layout_loads(layout_id: str) -> None:
    assert load_layout(layout_id).id == layout_id


@pytest.mark.parametrize("layout_id", layout_ids())
def test_shipped_layout_has_unique_control_ids(layout_id: str) -> None:
    ids = [control.id for control in load_layout(layout_id).controls]
    assert len(ids) == len(set(ids))


def test_numpad_key_belongs_to_its_control() -> None:
    assert load_layout("numpad").parts_by_code()[KP6] == ("6", "press")


def test_ch57x_layout_gives_every_part_its_own_code() -> None:
    assert len(load_layout("ch57x-9k3").parts_by_code()) == 9 + 3 * 3


def test_unknown_layout_is_rejected() -> None:
    with pytest.raises(ValueError):
        load_layout("does-not-exist")


def test_unknown_key_name_in_layout_is_rejected() -> None:
    control = {"id": "a", "kind": "key", "x": 0, "y": 0, "keys": {"press": "KEY_NOPE"}}
    with pytest.raises(ValidationError):
        Layout.model_validate({"id": "x", "name": "x", "controls": [control]})


def test_layout_without_translation_keeps_english() -> None:
    assert load_layout("numpad").localized("fr").name == "Numeric keypad"


def test_ch57x_outline_holds_every_control() -> None:
    layout = load_layout("ch57x-9k3")
    box = layout.outline
    assert box is not None and all(
        box.x <= c.x and c.x + c.w <= box.x + box.w and box.y <= c.y and c.y + c.h <= box.y + box.h
        for c in layout.controls
    )
