from datetime import datetime
from pathlib import Path

import pytest

from jogpad.klipper_setup import setup_switch

NOW = datetime(2026, 10, 25, 14, 30, 0)
SAVE_CONFIG = (
    "#*# <---------------------- SAVE_CONFIG ---------------------->\n"
    "#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.\n"
    "#*#\n"
    "#*# [probe]\n"
    "#*# z_offset = 1.200\n"
)


def config_dir(tmp_path: Path, printer: str = "[printer]\nkinematics: corexy\n") -> Path:
    (tmp_path / "printer.cfg").write_text(printer, encoding="utf-8")
    (tmp_path / "moonraker.conf").write_text("[server]\nhost: 0.0.0.0\n", encoding="utf-8")
    return tmp_path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_macro_is_written(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path), NOW)
    assert "[gcode_macro _JOGPAD]" in read(tmp_path / "jogpad.cfg")


def test_include_goes_at_the_end_without_save_config(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path), NOW)
    assert read(tmp_path / "printer.cfg").endswith("kinematics: corexy\n\n[include jogpad.cfg]\n")


def test_include_goes_above_the_save_config_block(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path, "[printer]\n\n" + SAVE_CONFIG), NOW)
    assert read(tmp_path / "printer.cfg") == "[printer]\n\n[include jogpad.cfg]\n\n" + SAVE_CONFIG


def test_power_device_is_appended(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path), NOW)
    assert read(tmp_path / "moonraker.conf") == (
        "[server]\nhost: 0.0.0.0\n\n"
        "[power jogpad]\ntype: klipper_device\nobject_name: gcode_macro _JOGPAD\n"
    )


def test_second_run_changes_no_config_file(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path), NOW)
    before = read(tmp_path / "printer.cfg"), read(tmp_path / "moonraker.conf")
    setup_switch(tmp_path, NOW)
    assert (read(tmp_path / "printer.cfg"), read(tmp_path / "moonraker.conf")) == before


def test_second_run_makes_no_backups(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path), NOW)
    assert setup_switch(tmp_path, NOW) == []


def test_backup_holds_the_original_printer_cfg(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path), NOW)
    backup = tmp_path / "printer.cfg.bak-20261025-143000"
    assert read(backup) == "[printer]\nkinematics: corexy\n"


def test_include_written_by_hand_is_kept(tmp_path: Path) -> None:
    printer = "[include  jogpad.cfg]\n[printer]\n"
    setup_switch(config_dir(tmp_path, printer), NOW)
    assert read(tmp_path / "printer.cfg") == printer


def test_commented_out_include_does_not_count(tmp_path: Path) -> None:
    setup_switch(config_dir(tmp_path, "#[include jogpad.cfg]\n"), NOW)
    assert read(tmp_path / "printer.cfg").endswith("\n\n[include jogpad.cfg]\n")


def test_missing_moonraker_conf_changes_nothing(tmp_path: Path) -> None:
    config_dir(tmp_path)
    (tmp_path / "moonraker.conf").unlink()
    with pytest.raises(FileNotFoundError):
        setup_switch(tmp_path, NOW)
    assert read(tmp_path / "printer.cfg") == "[printer]\nkinematics: corexy\n"
