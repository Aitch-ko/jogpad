import logging
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from jogpad import ch57x
from jogpad.cli import main
from jogpad.moonraker import Moonraker


@pytest.fixture
def no_camera(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Moonraker, "panel", lambda self: None)


def test_serve_logs_where_it_listens(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, no_camera: None
) -> None:
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: None)
    with caplog.at_level(logging.INFO, logger="jogpad.cli"):
        main(["serve"])
    assert "listening on http://0.0.0.0:7150" in caplog.text


def test_serve_keeps_requests_out_of_the_journal(
    monkeypatch: pytest.MonkeyPatch, no_camera: None
) -> None:
    options: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **given: options.update(given))
    main(["serve"])
    assert options["access_log"] is False


def test_program_pad_dry_run_shows_the_first_binding(capsys: pytest.CaptureFixture[str]) -> None:
    main(["program-pad", "--dry-run"])
    assert "03 fe 01 01 01 00 00 00 00 00 01 00 68 00" in capsys.readouterr().out


class Pad:
    """Stands in for the pad's hidraw node: it keeps what is written and answers
    read requests with it, after losing the first `lose[key_id]` bindings of a key."""

    def __init__(self, lose: dict[int, int] | None = None, silent: bool = False) -> None:
        self.written: list[bytes] = []
        self.lose = Counter(lose or {})
        self.held: dict[int, bytes] = {}
        self.silent = silent

    def write(self, device: Path, data: Iterable[bytes]) -> None:
        for message in data:
            self.written.append(message)
            if message[1] != 0xFE:
                continue
            if self.lose[message[2]]:
                self.lose[message[2]] -= 1
            else:
                self.held[message[2]] = message

    def read(self, device: Path, request: bytes, count: int) -> list[bytes]:
        return [] if self.silent else [bytes([3, 0xFA]) + m[2:] for m in self.held.values()]


def program(monkeypatch: pytest.MonkeyPatch, pad: Pad) -> int:
    monkeypatch.setattr(ch57x, "write", pad.write)
    monkeypatch.setattr(ch57x, "read", pad.read)
    return main(["program-pad", "--device", "/dev/hidraw0"])


def test_program_pad_writes_every_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    pad = Pad()
    program(monkeypatch, pad)
    assert len(pad.written) == (9 + 3 * 3) * 4


def test_program_pad_reports_every_binding_read_back(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    program(monkeypatch, Pad())
    assert "all 18 bindings are there" in capsys.readouterr().out


def test_program_pad_writes_a_lost_binding_once_more(monkeypatch: pytest.MonkeyPatch) -> None:
    pad = Pad(lose={5: 1})
    program(monkeypatch, pad)
    assert [m[2] for m in pad.written[(9 + 3 * 3) * 4 :] if m[1] == 0xFE] == [5]


def test_program_pad_fails_when_a_binding_never_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    assert program(monkeypatch, Pad(lose={5: 99})) == 2


def test_program_pad_names_the_binding_that_never_arrived(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    program(monkeypatch, Pad(lose={5: 99}))
    assert "KEY_F17" in capsys.readouterr().out.split("still lacks")[1]


def test_program_pad_leaves_the_check_to_the_user_when_the_pad_is_silent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    program(monkeypatch, Pad(silent=True))
    assert "did not answer" in capsys.readouterr().out


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
