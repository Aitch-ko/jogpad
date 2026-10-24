# jogpad

[![CI](https://github.com/Aitch-ko/jogpad/actions/workflows/ci.yml/badge.svg)](https://github.com/Aitch-ko/jogpad/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Turn a cheap programmable macro pad with knobs into a jog pendant for 3D
printers and CNC machines. One detent of a knob moves an axis by one step; keys
select the step size, home the machine or send a stop.

> [!WARNING]
> The STOP key is not an emergency stop. It goes through USB, the host and the
> network. Keep a wired emergency stop on your machine. See [Safety](docs/safety.md).

## Status

Early development, not released on PyPI yet. Working today, on Linux with
Klipper:

- jog, home and stop from a numeric keypad or any USB keyboard; tested on a
  QIDI Plus 4 with the keypad of a Logitech MX Keys S
- every move and homing shows up in the Mainsail or Fluidd console
- a web page that draws the pad, shows each key press live, learns keys and
  checks the direction of each axis
- an installer that sets jogpad up as a service next to Klipper
  ([installation](docs/installation.md), [setup](docs/usage.md))

Next: programming CH57x macro pads with knobs (waiting for the pad to arrive),
then skins for the web page.

| | Now | Later |
| --- | --- | --- |
| Firmware | Klipper (Moonraker) | RepRapFirmware, FluidNC |
| Operating system | Linux | Windows, macOS |
| Pads | numeric keypads, any USB keyboard | CH57x macro pads with knobs, programmed by jogpad |

## Why

Projects exist for single firmwares (keyboard plugins for OctoPrint and CNCjs,
`hal_input` in LinuxCNC). jogpad aims at what they leave open: one tool for
several firmwares, a knob that works like a handwheel without runaway moves,
programming the pad without the vendor's Windows software, and a web interface
to set it all up.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,docs]"
.venv/bin/pytest
```

Documentation: `docs/`, built with [Zensical](https://zensical.org/).
Rules for contributions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgements

Pad programming builds on the protocol work in
[ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool) (MIT).

## License

[MIT](LICENSE)
