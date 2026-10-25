import logging

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
