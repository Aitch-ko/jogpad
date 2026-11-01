import io
import ipaddress
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from jogpad.core import BackendError
from jogpad.moonraker import Moonraker


def answer_with(monkeypatch: pytest.MonkeyPatch, reply: Any) -> None:
    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def server_config(authorization: dict[str, Any]) -> dict[str, Any]:
    # Shape of Moonraker's GET /server/config, trimmed to what jogpad reads.
    return {"result": {"config": {"authorization": authorization}}}


def test_trusted_ranges_and_addresses_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = ["192.168.178.0/24", "10.0.0.7"]
    answer_with(monkeypatch, server_config({"trusted_clients": clients}))
    assert Moonraker("http://moonraker").trusted_networks() == [
        ipaddress.ip_network("192.168.178.0/24"),
        ipaddress.ip_network("10.0.0.7/32"),
    ]


def test_trusted_host_names_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = ["printer.lan", "10.0.0.7"]
    answer_with(monkeypatch, server_config({"trusted_clients": clients}))
    assert Moonraker("http://moonraker").trusted_networks() == [ipaddress.ip_network("10.0.0.7")]


def test_forced_logins_trust_nobody(monkeypatch: pytest.MonkeyPatch) -> None:
    authorization = {"force_logins": True, "trusted_clients": ["192.168.178.0/24"]}
    answer_with(monkeypatch, server_config(authorization))
    assert Moonraker("http://moonraker").trusted_networks() == []


def test_unexpected_server_config_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    answer_with(monkeypatch, server_config({"trusted_clients": "192.168.178.0/24"}))
    with pytest.raises(BackendError):
        Moonraker("http://moonraker").trusted_networks()


def test_panel_url_is_read_from_the_camera_list(monkeypatch: pytest.MonkeyPatch) -> None:
    webcams = [
        {"name": "Bed", "stream_url": "/webcam/?action=stream"},
        {"name": "jogpad", "stream_url": "http://printer:7150/?view=panel"},
    ]
    answer_with(monkeypatch, {"result": {"webcams": webcams}})
    assert Moonraker("http://moonraker").panel_url() == "http://printer:7150/?view=panel"


def test_panel_reports_the_aspect_ratio_of_the_camera(monkeypatch: pytest.MonkeyPatch) -> None:
    webcams = [
        {"name": "jogpad", "stream_url": "http://printer:7150/?view=panel", "aspect_ratio": "40:58"}
    ]
    answer_with(monkeypatch, {"result": {"webcams": webcams}})
    assert Moonraker("http://moonraker").panel() == ("http://printer:7150/?view=panel", "40:58")


def test_without_jogpad_camera_there_is_no_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    answer_with(monkeypatch, {"result": {"webcams": [{"name": "Bed"}]}})
    assert Moonraker("http://moonraker").panel_url() is None


def test_panel_is_added_as_an_iframe_camera(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        sent.append(json.loads(request.data))  # type: ignore[arg-type]
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    Moonraker("http://moonraker").add_panel("http://printer:7150/?view=panel", "40:65")
    assert sent == [
        {
            "name": "jogpad",
            "service": "iframe",
            "stream_url": "http://printer:7150/?view=panel",
            "aspect_ratio": "40:65",
        }
    ]


def test_panel_is_removed_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, str]] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        requests.append((request.get_method(), request.full_url))
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    Moonraker("http://moonraker").remove_panel()
    assert requests == [("DELETE", "http://moonraker/server/webcams/item?name=jogpad")]


REFUSAL = b'{"error": {"code": 400, "message": "Move out of range"}}'


def refuse_moves(monkeypatch: pytest.MonkeyPatch, restore_fails: bool = False) -> list[str]:
    """Klipper at the network boundary: refuses every G1 and keeps the scripts it got."""
    scripts: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        script = json.loads(request.data)["script"]  # type: ignore[arg-type]
        scripts.append(script)
        if "G1" in script:
            raise urllib.error.HTTPError(
                request.full_url, 400, "Bad Request", Message(), io.BytesIO(REFUSAL)
            )
        if restore_fails:
            raise urllib.error.URLError("connection refused")
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return scripts


def test_refused_move_restores_the_gcode_state(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = refuse_moves(monkeypatch)
    with pytest.raises(BackendError):
        Moonraker("http://moonraker").move("E", -1.0, 300)
    assert scripts[-1] == "RESTORE_GCODE_STATE NAME=JOGPAD"


def test_refused_move_still_reports_the_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    refuse_moves(monkeypatch)
    with pytest.raises(BackendError, match="Move out of range"):
        Moonraker("http://moonraker").move("X", 400.0, 3000)


def test_refusal_is_reported_even_when_restoring_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    refuse_moves(monkeypatch, restore_fails=True)
    with pytest.raises(BackendError, match="Move out of range"):
        Moonraker("http://moonraker").move("X", 400.0, 3000)


def test_switch_runs_the_macro(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        sent.append(json.loads(request.data))  # type: ignore[arg-type]
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    Moonraker("http://moonraker").set_switch(False)
    assert sent == [{"script": "_JOGPAD VALUE=0"}]


def test_gcode_is_sent_as_one_script(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = record_scripts(monkeypatch)
    Moonraker("http://moonraker").gcode("M300\nG4 P150\nM300")
    assert scripts == ["M300\nG4 P150\nM300"]


def record_scripts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    scripts: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        scripts.append(json.loads(request.data)["script"])  # type: ignore[arg-type]
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return scripts


def test_move_waits_until_the_move_is_done(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = record_scripts(monkeypatch)
    Moonraker("http://moonraker").move("X", 0.1, 3000)
    assert scripts[0].endswith("\nM400")


def test_queued_move_returns_without_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = record_scripts(monkeypatch)
    Moonraker("http://moonraker").queue_move("X", 0.3, 120)
    assert scripts == [
        "SAVE_GCODE_STATE NAME=JOGPAD\nG91\nG1 X0.300 F120\nRESTORE_GCODE_STATE NAME=JOGPAD"
    ]


def toolhead(print_time: float, estimated_print_time: float) -> dict[str, Any]:
    status = {"print_time": print_time, "estimated_print_time": estimated_print_time}
    return {"result": {"status": {"toolhead": status}}}


def test_motion_left_runs_to_the_end_of_the_queued_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(monkeypatch, toolhead(105.0, 104.6))
    assert Moonraker("http://moonraker").motion_left() == pytest.approx(0.4)


def test_idle_printer_has_no_motion_left(monkeypatch: pytest.MonkeyPatch) -> None:
    # At rest, the end of the last move lies in the past.
    answer_with(monkeypatch, toolhead(9984.0, 10025.1))
    assert Moonraker("http://moonraker").motion_left() == 0.0


def test_unexpected_toolhead_reply_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    answer_with(monkeypatch, {"result": {"status": {"toolhead": {"print_time": None}}}})
    with pytest.raises(BackendError):
        Moonraker("http://moonraker").motion_left()
