# Klipper setup

jogpad talks to Klipper through Moonraker. It runs on the same computer, usually
the Raspberry Pi, and reads the pad from `/dev/input`.

## Requirements

- Linux with Python 3.10 or newer
- Klipper with Moonraker, and `[respond]` in `printer.cfg` so jogpad's messages
  appear in the Mainsail or Fluidd console
- A USB numeric keypad, or a macro pad programmed to send distinct keys

## 1. Find the pad

```bash
jogpad devices
```

Pick the entries for your pad. Pads often show up as two devices (keys and
media keys); add both if your knobs send volume keys. Use the
`/dev/input/by-id/...` path, it survives replugging.

The user running jogpad must be allowed to read input devices:

```bash
sudo usermod -aG input $USER    # log out and in again
```

## 2. Write `jogpad.toml`

A numeric keypad works without a `[input.keys]` section:

```toml
[input]
devices = ["/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd"]
```

A macro pad with knobs, programmed to send F13 to F18 for the knobs:

```toml
[input]
devices = ["/dev/input/by-id/usb-1189_8890-event-kbd"]

[input.keys]
selected_plus = ["KEY_F13"]    # knob 1 right
selected_minus = ["KEY_F14"]   # knob 1 left
select_next = ["KEY_F15"]      # knob 1 press: X -> Y
z_plus = ["KEY_F16"]           # knob 2 right
z_minus = ["KEY_F17"]          # knob 2 left
step = ["KEY_F18"]             # knob 2 press
home = ["KEY_H"]
stop = ["KEY_ESC"]
```

Your keys replace the keypad default of the same action; the others keep their
default. `[]` switches an action off. All options:
[configuration reference](reference/config.md).

Check what each key sends and which action it triggers, without moving
anything:

```bash
jogpad keys --config jogpad.toml
```

## 3. Run it

```bash
jogpad check-config jogpad.toml
jogpad serve --config jogpad.toml
```

The installer sets jogpad up as a service that starts with the machine, see
[Installation](installation.md). After editing `jogpad.toml`, restart it from
the service menu in Mainsail or Fluidd, or with `sudo systemctl restart jogpad`.
Stop the service before running `jogpad keys`: it holds the pad exclusively.

## Using it

| Key | What happens |
| --- | --- |
| Axis key or knob detent | moves by one step. Presses during a running move are merged into the next move |
| Step | next step size (0.01, 0.1, 1 mm by default); jogpad starts with the smallest |
| Select next | the knob switches to the next axis in `select_axes` |
| HOME | starts the HOME selection: press axis keys to pick axes, HOME again to home. Twice HOME homes all axes. Any other key, or 5 s without input, cancels |
| STOP | sends Klipper's emergency stop immediately, even during a move. Not a safety device, see [Safety](safety.md) |

Holding a key does not repeat it: one press is one step.

Every move and every homing shows up in the Mainsail or Fluidd console, for
example `jogpad X +0.3 mm`, so others at the machine can see who moved it. Merged
presses give one line. Set `announce_moves = false` under `[jog]` to turn this off.

## Web page

`jogpad serve` also serves a page at `http://127.0.0.1:7150/`. It draws your
pad and lights up every key you press, with the action it triggers, and shows
step size, knob axis and the last refusal. Keys outside the drawing are listed
on the right, so the page also tells you which code an unknown key sends. The
page only shows; it never moves the machine.

Pick the drawing with `layout` under `[input]`: `numpad` (default),
`ch57x-9k3`, or `none` for the list only.

By default the page is only reachable on the machine itself. To open it from
another computer, set `host = "0.0.0.0"` under `[server]`. Anyone in your
network can then watch the key presses; there is no login yet.

## Locks

By default jogpad refuses to move or home while a print is running or paused.
Add your own conditions, for example for a laser or a spindle:

```toml
[[machine.locks]]
object = "print_stats"
field = "state"
equals = ["printing", "paused"]
reason = "job running"

[[machine.locks]]
object = "gcode_macro LASER_VARS"
field = "laser_on"
reason = "laser on"
```

Without `equals`, a lock applies when the field is true or non-zero. When the
status cannot be read, jogpad refuses as well. Defining `[[machine.locks]]`
replaces the default list, so repeat the print lock if you want to keep it.
