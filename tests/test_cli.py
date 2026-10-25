import logging
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
