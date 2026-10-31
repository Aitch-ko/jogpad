from pathlib import Path
from typing import Any

import pytest

from jogpad import ch57x
from jogpad.ch57x import bind, find_pad, messages, missing, read_request, write
from jogpad.layouts import Layout, load_layout

VENDOR_DESCRIPTOR = bytes.fromhex("0600ff0901a101850309021500")
KEYBOARD_DESCRIPTOR = bytes.fromhex("05010906a101850105071900")


@pytest.fixture
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ch57x.time, "sleep", lambda seconds: None)


def layout(**control: Any) -> Layout:
    control = {"id": "c", "kind": "knob", "x": 0, "y": 0, "slot": 0, **control}
    return Layout.model_validate({"id": "test", "name": "test", "controls": [control]})


def key_id(**control: Any) -> int:
    return messages(layout(**control))[0][2]


def answers(layout: Layout) -> list[bytes]:
    """What a pad holding `layout` answers to a read request: its bindings with FA for FE."""
    return [bytes([3, 0xFA]) + m[2:] for m in messages(layout)[::4]]


def hidraw(sysfs: Path, name: str, usb_id: str, descriptor: bytes) -> None:
    device = sysfs / name / "device"
    device.mkdir(parents=True)
    (device / "uevent").write_text(f"DRIVER=hid-generic\nHID_ID=0003:{usb_id}\n", encoding="utf-8")
    (device / "report_descriptor").write_bytes(descriptor)


def test_bind_message_matches_the_one_tried_on_a_real_pad() -> None:
    expected = bytes.fromhex("03 fe 01 01 01 00 00 00 00 00 01 00 68").ljust(64, b"\0")
    assert bind(1, 0x68)[0] == expected


def test_every_message_is_64_bytes() -> None:
    assert {len(m) for m in messages(load_layout("ch57x-9k3"))} == {64}


def test_every_binding_ends_with_the_closing_messages() -> None:
    assert len(messages(load_layout("ch57x-9k3"))) == (9 + 3 * 3) * 4


def test_key_slot_counts_from_one_in_the_pad() -> None:
    assert key_id(kind="key", slot=8, keys={"press": "KEY_F21"}) == 9


def test_first_knob_turned_left_is_key_16() -> None:
    assert key_id(slot=0, keys={"ccw": "KEY_RO"}) == 16


def test_third_knob_turned_right_is_key_24() -> None:
    assert key_id(slot=2, keys={"cw": "KEY_KPJPCOMMA"}) == 24


def test_second_knob_press_is_key_20() -> None:
    assert key_id(slot=1, keys={"press": "KEY_F23"}) == 20


def test_international6_is_hid_usage_0x8c() -> None:
    assert messages(layout(keys={"cw": "KEY_KPJPCOMMA"}))[0][12] == 0x8C


def test_f24_is_hid_usage_0x73() -> None:
    assert messages(layout(keys={"press": "KEY_F24"}))[0][12] == 0x73


def test_control_without_slot_is_refused() -> None:
    with pytest.raises(ValueError):
        messages(layout(slot=None, keys={"press": "KEY_F13"}))


def test_fourth_knob_is_refused() -> None:
    with pytest.raises(ValueError):
        messages(layout(slot=3, keys={"press": "KEY_F13"}))


def test_key_outside_f13_to_international6_is_refused() -> None:
    with pytest.raises(ValueError):
        messages(layout(keys={"press": "KEY_A"}))


def test_numpad_layout_cannot_be_programmed() -> None:
    with pytest.raises(ValueError):
        messages(load_layout("numpad"))


def test_find_pad_takes_the_vendor_interface(tmp_path: Path) -> None:
    hidraw(tmp_path, "hidraw0", "00001189:00008840", KEYBOARD_DESCRIPTOR)
    hidraw(tmp_path, "hidraw1", "00001189:00008840", VENDOR_DESCRIPTOR)
    assert find_pad(tmp_path) == Path("/dev/hidraw1")


def test_find_pad_skips_pads_with_the_other_protocol(tmp_path: Path) -> None:
    hidraw(tmp_path, "hidraw0", "00001189:00008890", VENDOR_DESCRIPTOR)
    with pytest.raises(LookupError):
        find_pad(tmp_path)


def test_find_pad_without_hidraw_finds_nothing(tmp_path: Path) -> None:
    with pytest.raises(LookupError):
        find_pad(tmp_path / "missing")


def test_write_sends_the_messages_in_order(tmp_path: Path, no_pause: None) -> None:
    device = tmp_path / "hidraw0"
    device.write_bytes(b"")
    write(device, bind(1, 0x68))
    assert device.read_bytes() == b"".join(bind(1, 0x68))


def test_read_request_asks_for_nine_keys_and_three_knobs() -> None:
    expected = bytes.fromhex("03 fa 09 03 01").ljust(64, b"\0")
    assert read_request(load_layout("ch57x-9k3")) == (expected, 18)


def test_pad_holding_the_layout_lacks_nothing() -> None:
    pad = load_layout("ch57x-9k3")
    assert missing(pad, answers(pad)) == []


def test_empty_key_in_the_answers_is_missing() -> None:
    pad = load_layout("ch57x-9k3")
    held = [a if a[2] != 5 else bytes([3, 0xFA, 5, 1, 1]).ljust(64, b"\0") for a in answers(pad)]
    assert [control.id for control, part, name in missing(pad, held) or []] == ["k5"]


def test_without_read_answers_nothing_can_be_said() -> None:
    pad = load_layout("ch57x-9k3")
    assert missing(pad, messages(pad)[:1]) is None


def test_backlight_lights_the_first_layer_in_the_colour() -> None:
    assert ch57x.backlight(ch57x.GREEN)[:13] == bytes.fromhex("03feb001080000000000010041")


STEPS = [0.01, 0.1, 1.0]


def test_smallest_step_is_green() -> None:
    assert ch57x.step_colour(0.01, STEPS) == ch57x.GREEN


def test_step_between_is_yellow() -> None:
    assert ch57x.step_colour(0.1, STEPS) == ch57x.YELLOW


def test_largest_step_is_red() -> None:
    assert ch57x.step_colour(1.0, STEPS) == ch57x.RED


def test_single_step_has_no_colour() -> None:
    assert ch57x.step_colour(1.0, [1.0]) is None


def test_ch57x_layout_fits_a_ch57x_pad() -> None:
    assert ch57x.fits(load_layout("ch57x-9k3"))


def test_numpad_layout_does_not_fit_a_ch57x_pad() -> None:
    assert not ch57x.fits(load_layout("numpad"))
