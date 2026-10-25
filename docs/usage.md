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

The [web page](#web-page) does the same with a drawing of the pad, and can
assign keys for you.

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

`jogpad serve` also serves a page on port 7150 of the machine, for example
`http://printer.local:7150/`. It draws your
pad and lights up every key you press, with the action it triggers, and shows
step size, knob axis and the last refusal. Keys outside the drawing are listed
too, so the page also tells you which code an unknown key sends.

Pick the drawing with `layout` under `[input]`: `numpad` (default),
`ch57x-9k3`, or `none` for the list only.

The `ch57x-9k3` drawing expects the codes jogpad will program into the pad:
F13 to F24 for the nine keys and the three knob presses, and the Japanese
keys `KEY_RO`, `KEY_KATAKANAHIRAGANA`, `KEY_YEN`, `KEY_HENKAN`,
`KEY_MUHENKAN` and `KEY_KPJPCOMMA` (International1 to 6 in USB terms) for
turning the knobs left and right. Nothing on a printer host reacts to those
keys. These codes are planned and not yet checked on a real pad.

The page speaks English and German. It follows your browser's language; the
menu at the top switches it, and your browser remembers the choice. Messages in
the Mainsail or Fluidd console stay in the configured `language`, since
everyone at the machine reads them.

At the bottom, the page links to the repository, to what is new in each
version, and to a bug report form with your jogpad version already filled in.

![The web page: the drawn keypad lights up the pressed key, the list on the right shows the last keys with their actions](assets/screenshots/web-page-light.png#only-light)
![The web page: the drawn keypad lights up the pressed key, the list on the right shows the last keys with their actions](assets/screenshots/web-page-dark.png#only-dark)

### Set up keys and directions

Under **Set up**, folded away until you click it, the page changes
`jogpad.toml` for you; the running service takes the change over at once.
Comments in the file are kept.

- **Learn**: click it next to an action, then press the key on the pad. For
  30 seconds keys only show up on the page and move nothing; STOP still works.
  If the key already belongs to another action, the page asks before moving it.
- **Check** a direction: press the + key of that axis on the pad. The machine
  moves. Then pick what you saw from the front of the machine, for example
  "head away from me" or "bed towards me". If it went the wrong way, jogpad
  reverses that axis (`invert` under `[jog]`). Reversing changes only which
  way the keys move, not Klipper's coordinates.

![Learning a key: the page asks to press the key for E+](assets/screenshots/learn-key.png)

![Checking a direction: after pressing Y+, the page asks what moved](assets/screenshots/check-direction.png)

The page itself never moves the machine; moves only come from the pad.

### Who may change what

Every computer in your network can open the page and watch the key presses;
there is no login. Changes, such as learning keys or checking directions, are
allowed from the machine itself and from the computers Moonraker trusts: the
addresses and ranges under `trusted_clients` in `moonraker.conf`. Whoever may
move the machine from Mainsail or Fluidd may also change what the keys do.
jogpad asks Moonraker on every change, so an edited `moonraker.conf` counts as
soon as Moonraker has restarted.

Host names in `trusted_clients` do not count for jogpad, only addresses and
ranges. With `force_logins` in Moonraker, only the machine itself may change
anything.

To keep the page on the machine itself, set `host = "127.0.0.1"` under
`[server]` and open it through an SSH tunnel:

```bash
ssh -N -L 7150:127.0.0.1:7150 pi@printer.local
```

and then `http://127.0.0.1:7150/` on your computer. `allow_remote_changes =
true` lets every computer in the network reassign your keys, STOP included.

### Show the pad in Mainsail and Fluidd

Mainsail and Fluidd have no panels for other programs, but both show a web
page as a camera. Under **Set up**, **Add** registers jogpad's compact view,
the pad and its state, as the camera `jogpad` in Moonraker; both show it in
their camera panel. **Remove** takes it out again.

![The compact view in a camera panel: the state bar above the drawn keypad](assets/screenshots/mainsail-panel.png)

Open the page with the printer's address when you add it, for example
`http://printer.local:7150/`: Mainsail and Fluidd load the view from that
address, so `127.0.0.1` through a tunnel is refused. The view follows the
light or dark setting of your browser, not the theme of Mainsail. If you
reach Mainsail over HTTPS, the browser blocks the view, since jogpad serves
plain HTTP. The compact view is also at `http://printer.local:7150/?view=panel`.

## Switch it on and off in Mainsail or Fluidd

A switch in Mainsail and Fluidd turns jogpad off while you do not need it.
Off means every key does nothing, STOP included, and nothing appears in the
console. After a Klipper restart jogpad is on again.

The installer asks whether to set the switch up. Later, run:

```bash
jogpad setup-switch
```

It writes the macro `_JOGPAD` to `~/printer_data/config/jogpad.cfg`, adds
`[include jogpad.cfg]` to `printer.cfg` above the `SAVE_CONFIG` block and

```ini
[power jogpad]
type: klipper_device
object_name: gcode_macro _JOGPAD
```

to the end of `moonraker.conf`. Before changing a file it keeps a copy next
to it, such as `printer.cfg.bak-20261025-143000`. Entries that are already
there stay as they are, so running it again only refreshes the macro; the
installer does that on every update. `--config-dir` points it at another
folder.

After restarting Klipper and Moonraker, `jogpad` shows up among the power
devices in Mainsail and Fluidd; in Mainsail that is the power menu at the top
right. The field `jogpad` on the web page and in the
[camera panel](#show-the-pad-in-mainsail-and-fluidd) switches as well, from
the computers that may change settings. While jogpad is off, the pad there is
greyed out under a note with a button to switch it on again.

The include alone is enough for the switch on the web page and in the panel;
`[power jogpad]` adds the one in the power menu. Without the macro there is
no switch, and jogpad is always on. If jogpad cannot read the switch, it
refuses to move, but STOP still goes out.

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
status cannot be read, jogpad refuses as well, and so it does when a lock's
object or field does not exist: Klipper reports those as null, and a typo in
the name of a laser lock must not switch it off unnoticed. The refusal names
the lock, so check the console after adding one. Defining `[[machine.locks]]`
replaces the default list, so repeat the print lock if you want to keep it.
