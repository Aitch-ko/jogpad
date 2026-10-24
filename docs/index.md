# jogpad

jogpad turns a cheap programmable macro pad with knobs into a jog pendant for
3D printers and CNC machines. One detent of a knob moves an axis by one step;
keys select the step size, home the machine or send a stop.

!!! warning "Not a safety device"
    The STOP key sends the firmware's emergency stop over USB, the host and the
    network. It does not replace a wired emergency stop. See [Safety](safety.md).

## Status

Early development. The configuration, command line and HTTP API exist; reading
the pad and moving a machine are being ported from a working prototype.

## Planned support

| Part | First version | Later |
| --- | --- | --- |
| Firmware | Klipper (Moonraker) | RepRapFirmware, FluidNC |
| Operating system | Linux | Windows, macOS |
| Pads | CH57x macro pads with knobs, numeric keypads | any USB keyboard |

## How it fits together

jogpad runs as a service on the computer next to the machine, usually the
Raspberry Pi that already runs Klipper. It reads the pad, turns key presses into
moves and talks to the firmware over its HTTP interface. A web interface and the
API ([reference](reference/api.md)) are served by the same process.
