"""Key events in, firmware calls out. The backend is faked: it is the system boundary."""

from __future__ import annotations

from typing import Any

import pytest

from jogpad.config import Config, Lock
from jogpad.core import KEY_AUTOREPEAT, KEY_PRESS, KEY_RELEASE, SWITCH, BackendError, Jogger

# Numeric keypad codes from linux/input-event-codes.h, written out here so the
# tests do not depend on the key table they would otherwise check against.
KP4, KP6, KP8, KP2, KPPLUS, KPASTERISK, KPENTER = 75, 77, 72, 80, 78, 55, 96
F13, F14, F15, F16 = 183, 184, 185, 186


class FakeBackend:
    def __init__(self, status: dict[str, dict[str, Any]] | None = None) -> None:
        self.status = status or {}
        self.calls: list[tuple[Any, ...]] = []
        self.notes: list[str] = []
        self.fail_query = False
        self.fail_move = False

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        if self.fail_query:
            raise BackendError("down")
        return self.status

    def move(self, axis: str, distance: float, feed: float) -> None:
        if self.fail_move:
            raise BackendError("Must home axis first")
        self.calls.append(("move", axis, distance, feed))

    def home(self, axes: list[str]) -> None:
        self.calls.append(("home", *axes))

    def emergency_stop(self) -> None:
        self.calls.append(("stop",))

    def notify(self, message: str) -> None:
        self.notes.append(message)


def press(*codes: int) -> list[tuple[int, int]]:
    return [event for code in codes for event in ((code, KEY_PRESS), (code, KEY_RELEASE))]


def run(
    events: list[tuple[int, int]],
    backend: FakeBackend | None = None,
    config: Config | None = None,
) -> FakeBackend:
    backend = backend or FakeBackend()
    Jogger(config or Config(), backend).handle(events, now=100.0)
    return backend


def knob_config(**jog: Any) -> Config:
    return Config.model_validate(
        {
            "jog": jog,
            "input": {
                "keys": {
                    "selected_plus": ["KEY_F13"],
                    "selected_minus": ["KEY_F14"],
                    "select_next": ["KEY_F15"],
                    "e_plus": ["KEY_F16"],
                }
            },
        }
    )


def test_one_press_moves_by_the_first_step() -> None:
    assert run(press(KP6)).calls == [("move", "X", 0.01, 3000)]


def test_z_uses_its_own_feed_rate() -> None:
    assert run(press(KPPLUS)).calls == [("move", "Z", 0.01, 600)]


def test_presses_in_one_batch_become_one_move() -> None:
    assert run(press(KP6, KP6, KP6)).calls == [("move", "X", 0.03, 3000)]


def test_opposite_presses_cancel_out() -> None:
    assert run(press(KP6, KP4)).calls == []


def test_axis_change_keeps_moves_apart() -> None:
    assert run(press(KP6, KP8)).calls == [("move", "X", 0.01, 3000), ("move", "Y", 0.01, 3000)]


def test_held_key_moves_only_once() -> None:
    events = [(KP6, KEY_PRESS), (KP6, KEY_AUTOREPEAT), (KP6, KEY_AUTOREPEAT), (KP6, KEY_RELEASE)]
    assert run(events).calls == [("move", "X", 0.01, 3000)]


def test_step_key_selects_next_step_size() -> None:
    assert run(press(KPASTERISK, KP8)).calls == [("move", "Y", 0.1, 3000)]


def test_step_size_wraps_to_the_smallest() -> None:
    events = press(KPASTERISK, KPASTERISK, KPASTERISK, KP8)
    assert run(events).calls == [("move", "Y", 0.01, 3000)]


def test_step_change_is_announced() -> None:
    assert run(press(KPASTERISK)).notes == ["Step 0.1 mm"]


def test_merged_move_is_announced_once() -> None:
    assert run(press(KP4, KP4, KP4)).notes == ["X -0.03 mm"]


def test_failed_move_is_not_announced() -> None:
    backend = FakeBackend()
    backend.fail_move = True
    assert run(press(KP6), backend).notes == []


def test_moves_are_silent_when_switched_off() -> None:
    config = Config.model_validate({"jog": {"announce_moves": False}})
    assert run(press(KP6), config=config).notes == []


def test_homing_is_announced_with_its_axes() -> None:
    assert run(press(KPENTER, KP8, KPENTER)).notes[-1] == "Homing: Y"


@pytest.mark.parametrize("state", ["printing", "paused"])
def test_running_job_refuses_moves(state: str) -> None:
    backend = FakeBackend({"print_stats": {"state": state}})
    assert run(press(KP6), backend).calls == []


def test_finished_job_allows_moves() -> None:
    backend = FakeBackend({"print_stats": {"state": "complete"}})
    assert run(press(KP6), backend).calls == [("move", "X", 0.01, 3000)]


def test_truthy_lock_refuses_moves() -> None:
    config = Config.model_validate(
        {"machine": {"locks": [{"object": "laser", "field": "on", "reason": "laser on"}]}}
    )
    backend = FakeBackend({"laser": {"on": True}})
    assert run(press(KP6), backend, config).calls == []


def test_refusal_names_the_reason() -> None:
    backend = FakeBackend({"print_stats": {"state": "printing"}})
    assert run(press(KP6), backend).notes == ["Refused: job running"]


def test_unreadable_status_refuses_moves() -> None:
    backend = FakeBackend()
    backend.fail_query = True
    assert run(press(KP6), backend).calls == []


def test_failed_move_does_not_raise() -> None:
    backend = FakeBackend()
    backend.fail_move = True
    assert run(press(KP6), backend).calls == []


def test_home_twice_homes_all_axes() -> None:
    assert run(press(KPENTER, KPENTER)).calls == [("home",)]


def test_home_with_selected_axes() -> None:
    assert run(press(KPENTER, KP4, KP8, KPENTER)).calls == [("home", "X", "Y")]


def test_home_axis_pressed_twice_is_deselected() -> None:
    assert run(press(KPENTER, KP6, KP4, KPENTER)).calls == [("home",)]


def test_other_key_cancels_home() -> None:
    assert run(press(KPENTER, KPASTERISK)).calls == []


def test_running_job_refuses_home() -> None:
    backend = FakeBackend({"print_stats": {"state": "printing"}})
    assert run(press(KPENTER, KPENTER), backend).calls == []


def test_home_selection_expires() -> None:
    backend = FakeBackend()
    jogger = Jogger(Config(), backend)
    jogger.handle(press(KPENTER), now=100.0)
    jogger.tick(106.0)
    jogger.handle(press(KP6), now=106.0)
    assert backend.calls == [("move", "X", 0.01, 3000)]


def test_knob_moves_the_selected_axis() -> None:
    assert run(press(F13, F13), config=knob_config()).calls == [("move", "X", 0.02, 3000)]


def test_select_next_switches_the_knob_to_y() -> None:
    assert run(press(F15, F14), config=knob_config()).calls == [("move", "Y", -0.01, 3000)]


def test_select_next_wraps_around() -> None:
    assert run(press(F15, F15, F13), config=knob_config()).calls == [("move", "X", 0.01, 3000)]


def test_select_axes_can_include_z() -> None:
    config = knob_config(select_axes=["X", "Y", "Z"])
    assert run(press(F15, F15, F13), config=config).calls == [("move", "Z", 0.01, 600)]


def test_knob_turn_cancels_home_selection() -> None:
    assert run(press(KPENTER, F13), config=knob_config()).calls == []


def test_extruder_uses_its_feed_rate() -> None:
    assert run(press(F16), config=knob_config()).calls == [("move", "E", 0.01, 300)]


def test_stop_key_is_recognised() -> None:
    assert Jogger(Config(), FakeBackend()).is_stop(82)


def test_lock_without_values_ignores_false() -> None:
    lock = Lock(object="laser", field="on", reason="laser on")
    config = Config.model_validate({"machine": {"locks": [lock.model_dump()]}})
    backend = FakeBackend({"laser": {"on": False}})
    assert run(press(KP6), backend, config).calls == [("move", "X", 0.01, 3000)]


def test_inverted_axis_moves_the_other_way() -> None:
    config = Config.model_validate({"jog": {"invert": ["Y"]}})
    assert run(press(KP8), config=config).calls == [("move", "Y", -0.01, 3000)]


def test_invert_leaves_other_axes_alone() -> None:
    config = Config.model_validate({"jog": {"invert": ["Y"]}})
    assert run(press(KP6), config=config).calls == [("move", "X", 0.01, 3000)]


def switched(value: int) -> FakeBackend:
    return FakeBackend({SWITCH: {"value": value}})


def switched_null() -> FakeBackend:
    return FakeBackend({SWITCH: {"value": None}})


def test_switched_off_pad_moves_nothing() -> None:
    assert run(press(KP6), switched(0)).calls == []


def test_switched_off_pad_writes_nothing_to_the_console() -> None:
    assert run(press(KPASTERISK, KPENTER), switched(0)).notes == []


def test_switched_off_pad_keeps_its_step_size() -> None:
    jogger = Jogger(Config(), switched(0))
    jogger.handle(press(KPASTERISK), now=100.0)
    assert jogger.step == 0.01


def test_switched_off_pad_names_the_switch_as_refusal() -> None:
    jogger = Jogger(Config(), switched(0))
    jogger.handle(press(KP6), now=100.0)
    assert jogger.state().last_refusal == "jogpad is switched off in Mainsail or Fluidd"


def test_switched_on_pad_moves() -> None:
    assert run(press(KP6), switched(1)).calls == [("move", "X", 0.01, 3000)]


def test_without_switch_macro_jogpad_is_on() -> None:
    # What Klipper answers for a macro that does not exist.
    assert Jogger(Config(), switched_null()).switch_state() is True


def test_without_switch_macro_pad_moves() -> None:
    assert run(press(KP6), switched_null()).calls == [("move", "X", 0.01, 3000)]


def test_unreadable_switch_is_unknown() -> None:
    backend = FakeBackend()
    backend.fail_query = True
    assert Jogger(Config(), backend).switch_state() is None


def test_unreadable_switch_keeps_the_step_size() -> None:
    backend = FakeBackend()
    backend.fail_query = True
    jogger = Jogger(Config(), backend)
    jogger.handle(press(KPASTERISK), now=100.0)
    assert jogger.step == 0.01
