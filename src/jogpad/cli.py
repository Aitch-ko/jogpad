"""Command line interface. `docs/reference/cli.md` is generated from `build_parser()`."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from jogpad import __version__
from jogpad.config import load_config
from jogpad.i18n import t


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jogpad",
        description="Jog pendant for 3D printers and CNC machines.",
    )
    parser.add_argument("--version", action="version", version=f"jogpad {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the web interface and API.")
    serve.add_argument("--config", type=Path, help="Path to jogpad.toml.")

    check = sub.add_parser("check-config", help="Validate a configuration file and exit.")
    check.add_argument("config", type=Path, help="Path to jogpad.toml.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = args.config
    try:
        config = load_config(path)
    except ValidationError as exc:
        print(t("config.invalid", path=path, error=exc))
        return 2
    if args.command == "check-config":
        return 0

    import uvicorn

    from jogpad.api import create_app

    lang = config.server.language
    host, port = config.server.host, config.server.port
    print(t("server.starting", lang, version=__version__, host=host, port=port))
    uvicorn.run(create_app(config), host=host, port=port)
    return 0
