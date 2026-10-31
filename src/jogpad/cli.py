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

log = logging.getLogger(__name__)


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

    switch = sub.add_parser(
        "setup-switch",
        help="Add the on/off switch for Mainsail and Fluidd to printer.cfg and "
        "moonraker.conf, with backups.",
    )
    switch.add_argument(
        "--config-dir",
        type=Path,
        default=Path("~/printer_data/config"),
        help="Folder with printer.cfg and moonraker.conf.",
    )

    program = sub.add_parser(
        "program-pad", help="Write a layout's key codes into a CH57x macro pad (Linux)."
    )
    program.add_argument("--layout", default="ch57x-9k3", help="Layout whose codes go in.")
    program.add_argument(
        "--device", type=Path, help="hidraw node of the pad; found automatically if left out."
    )
    program.add_argument(
        "--dry-run", action="store_true", help="Show the messages for the pad, write nothing."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.command == "devices":
        return _devices()
    if args.command == "setup-switch":
        return _setup_switch(args.config_dir.expanduser())
    if args.command == "program-pad":
        return _program_pad(args.layout, args.device, args.dry_run)
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


def _setup_switch(config_dir: Path) -> int:
    from datetime import datetime

    from jogpad.klipper_setup import setup_switch

    try:
        backups = setup_switch(config_dir, datetime.now())
    except OSError as exc:
        print(t("switch.setup_failed", error=exc))
        return 2
    for backup in backups:
        print(t("switch.backup", path=backup))
    if backups:
        print(t("switch.ready", path=config_dir))
    else:
        print(t("switch.unchanged", path=config_dir))
    return 0


def _program_pad(layout_id: str, device: Path | None, dry_run: bool) -> int:
    from jogpad import ch57x
    from jogpad.layouts import load_layout

    try:
        layout = load_layout(layout_id)
        data = ch57x.messages(layout)
    except ValueError as exc:
        print(t("pad.cannot_program", layout=layout_id, error=exc))
        return 2
    for control in layout.controls:
        for part, name in control.keys.items():
            print(f"{control.id:8} {part:6} {name}")
    if dry_run:
        for message in data:
            print(message.hex(" "))
        return 0
    try:
        device = device or ch57x.find_pad()
    except LookupError:
        print(t("pad.not_found"))
        return 2
    print(t("pad.writing", device=device))
    try:
        ch57x.write(device, data)
    except PermissionError:
        print(t("pad.no_access", device=device))
        return 2
    except OSError as exc:
        print(t("pad.write_failed", device=device, error=exc))
        return 2
    print(t("pad.done"))
    return 0


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
    # Not print(): under systemd stdout is block-buffered, and the line would reach
    # the journal late or, if the service stops first, never.
    log.info(
        t("server.starting", config.server.language, version=__version__, host=host, port=port)
    )
    try:
        # Open live streams never close by themselves; without a limit a restart
        # waits until systemd kills the process. No access log: an open page asks
        # for the state every 2 s, which would bury the journal.
        app = create_app(config, service, path, backend)
        uvicorn.run(app, host=host, port=port, timeout_graceful_shutdown=3, access_log=False)
    finally:
        service.stop()
    return 0
