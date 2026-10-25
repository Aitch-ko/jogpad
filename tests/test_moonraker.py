import io
import ipaddress
import json
import urllib.request
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
