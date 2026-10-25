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
