# jogpad

**Jog your 3D printer or CNC machine with keys and knobs you can feel, not with
a touchscreen.**

Levelling the bed with a sheet of paper means looking at the nozzle. A
touchscreen has nothing to feel, so every tap is a glance away or a blind
guess, and a finger that slipped to the next button moves 10 mm instead of
0.1. A mouse is no better when the printer is not next to the monitor.

jogpad turns a numeric keypad or a small macro pad with knobs into a jog
pendant. Every key sits where your finger left it; one press or one knob
detent is one step; your eyes stay on the nozzle. The same applies to mills,
lasers and other machines: see [use cases](use-cases.md).

![Animation: the big knob of a macro pad with nine keys and three knobs is turned; with every detent the nozzle moves down one step towards a sheet of paper, and the console reports each move. The step key switches from 1 mm to 0.01 mm, and the pad's light from red to green](assets/demo.svg)

!!! warning "Not a safety device"
    The STOP key sends the firmware's emergency stop over USB, the host and the
    network. It does not replace a wired emergency stop. See [Safety](safety.md).

## Which pad

- **A small USB numeric keypad.** It costs a few euros and works as it
  comes: plug it in, enter it in `jogpad.toml`, done.
- **An old keyboard** from the drawer: its numeric block works the same way.
  Wireless keyboards work too, but take one with a cable if you can. A key
  release lost over radio keeps a held key's axis moving until you press
  another key, see [Safety](safety.md#wireless-pads).
- **A macro pad with 9 keys and 3 knobs (recommended).** The knobs turn like
  handwheels, the big one for Z, and the pad lights up in the colour of the
  step size. It is sold under many names. jogpad is tested with one that
  shows up with USB ID 1189:8840 (`lsusb` shows it), and
  [`jogpad program-pad`](usage.md#program-a-ch57x-macro-pad) sets it up
  without the vendor's software. Pads with 1189:8890 speak another protocol
  and do not work yet.

## Status

Early development, not released on PyPI yet. Working today on Linux with
Klipper, tested on a QIDI Plus 4 with the keypad of a Logitech MX Keys S:

- jog, home and stop from a numeric keypad or any USB keyboard
- a held axis key keeps moving until released, at a speed set with the step
  key, at most 250 mm/s
- every move and homing shows up in the Mainsail or Fluidd console
- a web page that draws the pad with arrows and signs in the colour of each
  axis, shows key presses live and the step size from green to red, learns
  keys and checks axis directions; open in the network, changes only from
  computers Moonraker trusts
- a switch in Mainsail and Fluidd that turns jogpad off, STOP included
- the pad and its state as a camera panel in Mainsail and Fluidd, sized to
  the pad and with a link to the full page
- an [installer](installation.md) that sets jogpad up as a service next to
  Klipper
- [programming a CH57x macro pad](usage.md#program-a-ch57x-macro-pad) with
  9 keys and 3 knobs, without the vendor's software; it lights up in the
  colour of the step size

| Part | Now | Later |
| --- | --- | --- |
| Firmware | Klipper (Moonraker) | RepRapFirmware, FluidNC |
| Operating system | Linux | Windows, macOS |
| Pads | numeric keypads, any USB keyboard, CH57x macro pad 1189:8840 programmed by jogpad | other CH57x macro pads |

## How it fits together

jogpad runs as a service on the computer next to the machine, usually the
Raspberry Pi that already runs Klipper. It reads the pad, turns key presses into
moves and talks to the firmware over its HTTP interface. The web page and the
API ([reference](reference/api.md)) are served by the same process.
