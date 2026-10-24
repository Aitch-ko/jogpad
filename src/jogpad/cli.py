"""Command line interface. `docs/reference/cli.md` is generated from `build_parser()`."""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
import threading
from pathlib import Path

from pydantic import ValidationError

from jogpad import __version__
from jogpad.config import Config, load_config
from jogpad.i18n import t
from jogpad.keys import key_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jogpad",
        description="Jog pendant for 3D printers and CNC machines.",
    )
    parser.add_argument("--version", action="version", version=f"jogpad {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Read the pad, jog the machine, serve the API.")
    serve.add_argument("--config", type=Path, help="Path to jogpad.toml.")

    check = sub.add_parser("check-config", help="Validate a configuration file and exit.")
    check.add_argument("config", type=Path, help="Path to jogpad.toml.")

    sub.add_parser("devices", help="List input devices (Linux).")

    keys = sub.add_parser("keys", help="Show pressed keys and their actions. Moves nothing.")
    keys.add_argument("--config", type=Path, help="Path to jogpad.toml.")
    keys.add_argument("--device", action="append", help="Device to read; overrides the config.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.command == "devices":
        return _devices()
    path = getattr(args, "config", None)
    try:
        config = load_config(path)
    except ValidationError as exc:
        print(t("config.invalid", path=path, error=exc))
        return 2
    if args.command == "check-config":
        return 0
    if sys.platform != "linux" and (args.command == "keys" or config.input.devices):
        print(t("input.linux_only", config.server.language))
        return 2
    if args.command == "keys":
        return _keys(config, args.device or config.input.devices)
    return _serve(config, path)


def _devices() -> int:
    from jogpad.linux_input import list_devices

    devices = list_devices()
    for path in devices:
        print(path)
    if not devices:
        print(t("devices.none"))
    return 0


def _keys(config: Config, devices: list[str]) -> int:
    from jogpad.linux_input import read_device

    actions = config.input.actions_by_code()

    def show(code: int, value: int) -> None:
        if value == 1:
            action = actions.get(code)
            print(f"{key_name(code):16} {code:4}  {action.value if action else '-'}", flush=True)

    print(t("keys.prompt", config.server.language))
    stop = threading.Event()
    for device in devices:
        threading.Thread(target=read_device, args=(device, show, stop), daemon=True).start()
    with contextlib.suppress(KeyboardInterrupt):
        stop.wait()
    return 0


def _serve(config: Config, path: Path | None) -> int:
    import uvicorn

    from jogpad.api import create_app
    from jogpad.core import Jogger
    from jogpad.moonraker import Moonraker
    from jogpad.service import Service

    backend = Moonraker(config.machine.url)
    service = Service(Jogger(config, backend), backend, config.input.devices)
    service.start()
    host, port = config.server.host, config.server.port
    print(t("server.starting", config.server.language, version=__version__, host=host, port=port))
    try:
        # Open live streams never close by themselves; without a limit a restart
        # waits until systemd kills the process.
        app = create_app(config, service, path)
        uvicorn.run(app, host=host, port=port, timeout_graceful_shutdown=3)
    finally:
        service.stop()
    return 0
