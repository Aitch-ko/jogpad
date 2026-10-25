import logging
from pathlib import Path
from typing import Any

import pytest
import uvicorn

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


def test_setup_switch_fails_visibly_without_printer_cfg(tmp_path: Path) -> None:
    assert main(["setup-switch", "--config-dir", str(tmp_path)]) == 2


def test_setup_switch_adds_the_include(tmp_path: Path) -> None:
    (tmp_path / "printer.cfg").write_text("[printer]\n", encoding="utf-8")
    (tmp_path / "moonraker.conf").write_text("[server]\n", encoding="utf-8")
    main(["setup-switch", "--config-dir", str(tmp_path)])
    assert "[include jogpad.cfg]" in (tmp_path / "printer.cfg").read_text(encoding="utf-8")
