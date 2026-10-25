"""Klipper through Moonraker's HTTP API."""

from __future__ import annotations

import ipaddress
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from jogpad.core import BackendError

MOVE_TIMEOUT_S = 30
HOME_TIMEOUT_S = 180

log = logging.getLogger(__name__)

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
# Name of jogpad's camera in Mainsail and Fluidd.
PANEL = "jogpad"


class Moonraker:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        # Objects that do not exist on this printer come back with every field null.
        query = "&".join(
            urllib.parse.quote(name) + "=" + ",".join(fields) for name, fields in objects.items()
        )
        reply = self._request("/printer/objects/query?" + query)
        try:
            status: dict[str, dict[str, Any]] = reply["result"]["status"]
        except (KeyError, TypeError) as exc:
            raise BackendError(f"unexpected reply: {reply!r}") from exc
        return status

    def move(self, axis: str, distance: float, feed: float) -> None:
        mode = "M83" if axis == "E" else "G91"
        # M400 holds the reply until the move has finished; the core relies on
        # that to merge presses instead of queueing them.
        self._script(
            "SAVE_GCODE_STATE NAME=JOGPAD\n"
            f"{mode}\n"
            f"G1 {axis}{distance:.3f} F{feed:.0f}\n"
            "RESTORE_GCODE_STATE NAME=JOGPAD\n"
            "M400",
            MOVE_TIMEOUT_S,
        )

    def home(self, axes: list[str]) -> None:
        self._script(" ".join(["G28", *axes]), HOME_TIMEOUT_S)

    def emergency_stop(self) -> None:
        self._request("/printer/emergency_stop", {}, timeout=5)

    def notify(self, message: str) -> None:
        # Shown in the Mainsail/Fluidd console; needs [respond] in printer.cfg.
        text = message.replace('"', "'").replace("\n", " ")
        self._script(f'RESPOND PREFIX=jogpad MSG="{text}"', 5)

    def trusted_networks(self) -> list[IPNetwork]:
        """Addresses Moonraker lets in without a login, from `trusted_clients`.

        Host names are left out: Moonraker looks them up per request, jogpad
        does not. With `force_logins` the list is empty, since jogpad cannot
        tell whether Moonraker has users that make it count.
        """
        reply = self._request("/server/config")
        try:
            authorization: dict[str, Any] = reply["result"]["config"].get("authorization", {})
        except (KeyError, TypeError, AttributeError) as exc:
            # The reply holds the whole Moonraker configuration; the start is enough.
            raise BackendError(f"unexpected reply: {reply!r:.300}") from exc
        if authorization.get("force_logins"):
            return []
        entries = authorization.get("trusted_clients", [])
        if not isinstance(entries, list):
            raise BackendError(f"unexpected trusted_clients: {entries!r}")
        networks: list[IPNetwork] = []
        for entry in entries:
            try:
                networks.append(ipaddress.ip_network(entry))
            except ValueError:
                log.warning(
                    "trusted_clients: ignoring %r, jogpad takes addresses and ranges only", entry
                )
        return networks

    def panel_url(self) -> str | None:
        """Address of jogpad's camera in Mainsail and Fluidd, None if there is none."""
        reply = self._request("/server/webcams/list")
        try:
            webcams: list[dict[str, Any]] = reply["result"]["webcams"]
        except (KeyError, TypeError) as exc:
            raise BackendError(f"unexpected reply: {reply!r:.300}") from exc
        for webcam in webcams:
            if webcam.get("name") == PANEL:
                return str(webcam.get("stream_url", ""))
        return None

    def add_panel(self, url: str, aspect_ratio: str) -> None:
        # Mainsail and Fluidd have no plugin panels, but both show a web page
        # as a camera of the service "iframe".
        camera = {"name": PANEL, "service": "iframe", "stream_url": url}
        self._request("/server/webcams/item", {**camera, "aspect_ratio": aspect_ratio})

    def remove_panel(self) -> None:
        self._request(f"/server/webcams/item?name={PANEL}", method="DELETE")

    def _script(self, gcode: str, timeout: float) -> None:
        self._request("/printer/gcode/script", {"script": gcode}, timeout)

    def _request(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float = 10,
        method: str | None = None,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.url + path, data=data, headers={"Content-Type": "application/json"}, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Klipper errors such as "Must home axis first" arrive as 400 with a body.
            raise BackendError(exc.read().decode(errors="replace")[:300]) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise BackendError(str(exc)) from exc
