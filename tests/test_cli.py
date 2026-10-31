import logging
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from jogpad import ch57x
from jogpad.cli import main


def test_serve_logs_where_it_listens(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: None)
    with caplog.at_level(logging.INFO, logger="jogpad.cli"):
        main(["serve"])
    assert "listening on http://0.0.0.0:7150" in caplog.text


def test_serve_keeps_requests_out_of_the_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    options: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **given: options.update(given))
    main(["serve"])
    assert options["access_log"] is False


def test_program_pad_dry_run_shows_the_first_binding(capsys: pytest.CaptureFixture[str]) -> None:
    main(["program-pad", "--dry-run"])
    assert "03 fe 01 01 01 00 00 00 00 00 01 00 68 00" in capsys.readouterr().out


def test_program_pad_writes_every_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ch57x, "PAUSE_S", 0)
    device = tmp_path / "hidraw0"
    device.write_bytes(b"")
    main(["program-pad", "--device", str(device)])
    assert len(device.read_bytes()) == (9 + 3 * 3) * 4 * 64


def test_program_pad_refuses_a_layout_without_slots() -> None:
    assert main(["program-pad", "--layout", "numpad", "--dry-run"]) == 2


def test_program_pad_without_a_pad_fails_visibly(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_pad() -> Path:
        raise LookupError

    monkeypatch.setattr(ch57x, "find_pad", no_pad)
    assert main(["program-pad"]) == 2


def test_setup_switch_fails_visibly_without_printer_cfg(tmp_path: Path) -> None:
    assert main(["setup-switch", "--config-dir", str(tmp_path)]) == 2


def test_setup_switch_adds_the_include(tmp_path: Path) -> None:
    (tmp_path / "printer.cfg").write_text("[printer]\n", encoding="utf-8")
    (tmp_path / "moonraker.conf").write_text("[server]\n", encoding="utf-8")
    main(["setup-switch", "--config-dir", str(tmp_path)])
    assert "[include jogpad.cfg]" in (tmp_path / "printer.cfg").read_text(encoding="utf-8")
