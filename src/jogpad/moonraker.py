"""Klipper through Moonraker's HTTP API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from jogpad.core import BackendError

MOVE_TIMEOUT_S = 30
HOME_TIMEOUT_S = 180


class Moonraker:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def query(self, objects: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        # Objects that do not exist on this printer are simply missing from the reply.
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

    def _script(self, gcode: str, timeout: float) -> None:
        self._request("/printer/gcode/script", {"script": gcode}, timeout)

    def _request(self, path: str, body: dict[str, Any] | None = None, timeout: float = 10) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.url + path, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Klipper errors such as "Must home axis first" arrive as 400 with a body.
            raise BackendError(exc.read().decode(errors="replace")[:300]) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise BackendError(str(exc)) from exc
