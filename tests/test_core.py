"""Key events in, firmware calls out. The backend is faked: it is the system boundary."""

from __future__ import annotations

from typing import Any

import pytest

from jogpad.config import Config, Lock
from jogpad.core import (
    KEY_AUTOREPEAT,
    KEY_PRESS,
    KEY_RELEASE,
    SWITCH,
    BackendError,
    Jogger,
    Switch,
)

# Numeric keypad codes from linux/input-event-codes.h, written out here so the
# tests do not depend on the key table they would otherwise check against.
KP4, KP6, KP8, KP2, KPPLUS, KPASTERISK, KPENTER = 75, 77, 72, 80, 78, 55, 96
F13, F14, F15, F16 = 183, 184, 185, 186


class FakeBackend:
    def __init__(self, status: dict[str, dict[str, Any]] | None = None) -> None:
        # A printer at rest, so the default print lock finds its object.
        self.status = {"print_stats": {"state": "standby"}, **(status or {})}
        self.calls: list[tuple[Any, ...]] = []
        self.notes: list[str] = []
        self.queries: list[dict[str, list[str]]] = []
        self.fail_query = False
        self.fail_move = False
        # Seconds of moves the firmware still has queued.
        self.left = 0.0

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        self.queries.append(objects)
        if self.fail_query:
            raise BackendError("down")
        return self.status

    def move(self, axis: str, distance: float, feed: float) -> None:
        if self.fail_move:
            raise BackendError("Must home axis first")
        self.calls.append(("move", axis, distance, feed))

    def queue_move(self, axis: str, distance: float, feed: float) -> None:
        if self.fail_move:
            raise BackendError("Move out of range")
        self.calls.append(("queue", axis, distance, feed))

    def motion_left(self) -> float:
        return self.left

    def home(self, axes: list[str]) -> None:
        self.calls.append(("home", *axes))

    def emergency_stop(self) -> None:
        self.calls.append(("stop",))

    def notify(self, message: str) -> None:
        self.notes.append(message)

    def gcode(self, script: str) -> None:
        self.calls.append(("gcode", script))


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


def test_press_asks_klipper_once_for_switch_and_locks() -> None:
    # Klipper answers a query only at its next status update, up to 0.25 s later.
    assert run(press(KP6)).queries == [{"print_stats": ["state"], SWITCH: ["value"]}]


def test_step_key_selects_next_step_size() -> None:
    assert run(press(KPASTERISK, KP8)).calls == [("move", "Y", 0.1, 3000)]


def test_step_size_wraps_to_the_smallest() -> None:
    events = press(KPASTERISK, KPASTERISK, KPASTERISK, KP8)
    assert run(events).calls == [("move", "Y", 0.01, 3000)]


def test_step_change_is_announced() -> None:
    assert run(press(KPASTERISK)).notes == ["Step 0.1 mm"]


def test_step_size_beeps_its_number() -> None:
    config = Config.model_validate({"input": {"step_beep": "M300"}})
    assert run(press(KPASTERISK), config=config).calls == [("gcode", "M300\nG4 P150\nM300")]


def test_step_change_without_beep_sends_no_gcode() -> None:
    assert run(press(KPASTERISK)).calls == []


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


def test_home_says_how_to_go_on() -> None:
    assert run(press(KPENTER)).notes == ["HOME: pick axes, or press HOME to home all"]


def test_picked_home_axis_says_how_to_go_on() -> None:
    assert run(press(KPENTER, KP8)).notes[-1] == "HOME: Y picked -- press HOME to home"


def test_dropping_the_last_home_axis_says_home_homes_all() -> None:
    notes = run(press(KPENTER, KP8, KP8)).notes
    assert notes[-1] == "HOME: pick axes, or press HOME to home all"


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


def test_missing_switch_macro_is_told_apart_from_on() -> None:
    assert Jogger(Config(), switched_null()).switch() is Switch.MISSING


def test_switch_macro_at_zero_is_off() -> None:
    assert Jogger(Config(), switched(0)).switch() is Switch.OFF


def laser_lock_config() -> Config:
    lock = {"object": "gcode_macro LASER_VARS", "field": "laser_on", "reason": "laser on"}
    return Config.model_validate({"machine": {"locks": [lock]}})


def test_lock_on_an_object_klipper_does_not_know_refuses_moves() -> None:
    # What Klipper answers for a macro that does not exist, e.g. after a typo.
    backend = FakeBackend({"gcode_macro LASER_VARS": {"laser_on": None}})
    assert run(press(KP6), backend, laser_lock_config()).calls == []


def test_lock_missing_from_the_reply_refuses_moves() -> None:
    assert run(press(KP6), FakeBackend(), laser_lock_config()).calls == []


def test_missing_lock_object_is_named_in_the_refusal() -> None:
    notes = run(press(KP6), FakeBackend(), laser_lock_config()).notes
    assert notes == ["Refused: lock gcode_macro LASER_VARS laser_on not found in the firmware"]


def test_lock_on_an_existing_field_that_is_off_allows_moves() -> None:
    backend = FakeBackend({"gcode_macro LASER_VARS": {"laser_on": False}})
    assert run(press(KP6), backend, laser_lock_config()).calls == [("move", "X", 0.01, 3000)]


# A key held down: pressed at 100.0, released only when a test says so. With the
# defaults it starts moving at 100.5; the first move fills Klipper's empty queue with
# 0.65 s - 0.35 s = 0.3 s at 2 mm/s, so 0.6 mm.
def held(
    code: int, backend: FakeBackend | None = None, config: Config | None = None
) -> tuple[Jogger, FakeBackend]:
    backend = backend or FakeBackend()
    jogger = Jogger(config or Config(), backend)
    jogger.handle([(code, KEY_PRESS)], now=100.0)
    return jogger, backend


def test_key_held_past_the_delay_keeps_its_axis_moving() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    assert backend.calls == [("move", "X", 0.01, 3000), ("queue", "X", 0.6, 120)]


def test_key_held_shorter_than_the_delay_moves_one_step() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.4)
    assert backend.calls == [("move", "X", 0.01, 3000)]


def test_key_released_before_the_delay_moves_one_step() -> None:
    jogger, backend = held(KP6)
    jogger.handle([(KP6, KEY_RELEASE)], now=100.2)
    jogger.tick(100.5)
    assert backend.calls == [("move", "X", 0.01, 3000)]


def test_tap_in_a_late_batch_moves_one_step() -> None:
    # Press and release arrive together when the previous move held up the worker.
    jogger = Jogger(Config(), backend := FakeBackend())
    jogger.handle(press(KP6), now=100.0)
    jogger.tick(101.0)
    assert backend.calls == [("move", "X", 0.01, 3000)]


def test_released_key_stops_its_axis() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    jogger.handle([(KP6, KEY_RELEASE)], now=100.6)
    jogger.tick(101.0)
    assert backend.calls == [("move", "X", 0.01, 3000), ("queue", "X", 0.6, 120)]


def test_held_key_tops_up_what_klipper_has_left() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    backend.left = 0.4
    jogger.tick(100.65)
    assert backend.calls[-1] == ("queue", "X", 0.5, 120)


def test_held_key_queues_nothing_while_klipper_has_enough() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    backend.left = 1.0
    jogger.tick(100.65)
    assert backend.calls == [("move", "X", 0.01, 3000), ("queue", "X", 0.6, 120)]


def test_held_key_reads_the_queue_once_klipper_has_taken_the_last_move() -> None:
    jogger, _ = held(KP6)
    jogger.tick(100.5)
    assert jogger.next_deadline() == pytest.approx(100.65)


def test_held_key_moves_at_the_speed_of_the_step_size() -> None:
    jogger = Jogger(Config(), backend := FakeBackend())
    jogger.handle(press(KPASTERISK, KPASTERISK) + [(KP6, KEY_PRESS)], now=100.0)
    jogger.tick(100.5)
    assert backend.calls[-1] == ("queue", "X", 15.0, 3000)


def test_held_z_key_uses_the_z_speeds() -> None:
    jogger, backend = held(KPPLUS)
    jogger.tick(100.5)
    assert backend.calls[-1] == ("queue", "Z", 0.15, 30)


def test_held_extruder_key_uses_the_extruder_speeds() -> None:
    jogger, backend = held(F16, config=knob_config())
    jogger.tick(100.5)
    assert backend.calls[-1] == ("queue", "E", 0.3, 60)


def test_held_inverted_axis_moves_the_other_way() -> None:
    config = Config.model_validate({"jog": {"invert": ["X"]}})
    jogger, backend = held(KP6, config=config)
    jogger.tick(100.5)
    assert backend.calls[-1] == ("queue", "X", -0.6, 120)


def test_held_key_waits_as_long_as_configured() -> None:
    config = Config.model_validate({"jog": {"hold_delay": 1.0}})
    jogger, backend = held(KP6, config=config)
    jogger.tick(100.5)
    assert backend.calls == [("move", "X", 0.01, 3000)]


def test_held_move_is_announced_once_on_release() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    jogger.tick(100.65)
    jogger.handle([(KP6, KEY_RELEASE)], now=100.7)
    assert backend.notes == ["X +0.01 mm", "X +1.2 mm"]


def test_other_key_stops_a_held_key() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    jogger.handle(press(KP8), now=100.55)
    jogger.tick(101.0)
    assert backend.calls == [
        ("move", "X", 0.01, 3000),
        ("queue", "X", 0.6, 120),
        ("move", "Y", 0.01, 3000),
    ]


def test_refused_press_does_not_hold() -> None:
    backend = FakeBackend({"print_stats": {"state": "printing"}})
    jogger, _ = held(KP6, backend)
    jogger.tick(100.5)
    assert backend.calls == []


def test_held_key_after_presses_that_cancelled_out_is_checked() -> None:
    backend = FakeBackend({"print_stats": {"state": "printing"}})
    jogger = Jogger(Config(), backend)
    jogger.handle(press(KP4) + [(KP6, KEY_PRESS)], now=100.0)
    jogger.tick(100.5)
    assert backend.calls == []


def test_held_key_after_presses_that_cancelled_out_moves_when_allowed() -> None:
    jogger = Jogger(Config(), backend := FakeBackend())
    jogger.handle(press(KP4) + [(KP6, KEY_PRESS)], now=100.0)
    jogger.tick(100.5)
    assert backend.calls == [("queue", "X", 0.6, 120)]


def test_held_key_after_cancelled_presses_sees_a_lock_that_came_since() -> None:
    jogger = Jogger(Config(), backend := FakeBackend())
    jogger.handle(press(KP4) + [(KP6, KEY_PRESS)], now=100.0)
    backend.status = {"print_stats": {"state": "printing"}}
    jogger.tick(100.5)
    assert backend.calls == []


def test_held_key_starts_without_asking_klipper_again() -> None:
    jogger, backend = held(KP6)
    backend.fail_query = True
    jogger.tick(100.5)
    assert backend.calls[-1] == ("queue", "X", 0.6, 120)


def test_refused_move_stops_a_held_key() -> None:
    jogger, backend = held(KP6)
    jogger.tick(100.5)
    backend.fail_move = True
    jogger.tick(100.65)
    backend.fail_move = False
    jogger.tick(101.0)
    assert backend.calls == [("move", "X", 0.01, 3000), ("queue", "X", 0.6, 120)]


def test_release_stops_a_held_key_after_the_switch_went_off() -> None:
    jogger, backend = held(KP6, switched(1))
    jogger.tick(100.5)
    backend.status[SWITCH]["value"] = 0
    jogger.handle([(KP6, KEY_RELEASE), (KP8, KEY_PRESS)], now=100.6)
    jogger.tick(101.0)
    assert backend.calls == [("move", "X", 0.01, 3000), ("queue", "X", 0.6, 120)]


def test_held_key_in_the_home_selection_only_selects() -> None:
    jogger = Jogger(Config(), backend := FakeBackend())
    jogger.handle(press(KPENTER) + [(KP6, KEY_PRESS)], now=100.0)
    jogger.tick(100.5)
    assert backend.calls == []
