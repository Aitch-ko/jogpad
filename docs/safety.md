# Safety

jogpad is an operating aid. It is not a safety function and must not be relied
on as one.

## STOP is not an emergency stop

The STOP key sends the firmware's emergency stop command (for Klipper:
Moonraker's `emergency_stop`). That command travels over USB, the host
computer and the network, any of which can fail. Keep a wired emergency stop on
the machine. Do not label or build the STOP key like an emergency stop device
(red mushroom head on a yellow background).

While jogpad is switched off in Mainsail or Fluidd, STOP does nothing either,
like every other key. If jogpad cannot read the switch, STOP still goes out.

## No runaway moves

jogpad sends the next move only after the firmware has finished the previous
one. Detents that arrive in the meantime are merged into a single move. Without
this, fast turning queues moves in the firmware and the axis keeps travelling
after you stop turning. A held key is the exception, see below.

## Locks

jogpad refuses to move while a print or job is running or paused. Further
conditions, such as a spindle or laser being on, can be added per machine in
the configuration. A lock whose object or field the firmware does not know
refuses as well, so a misspelt lock does not quietly stop working.

## Holding a key

An axis key held for half a second keeps its axis moving until it is released.
jogpad sends short moves and keeps only as many queued as Klipper needs to move
without stuttering. Klipper cannot take back a move it has queued, so the axis
runs on for 0.4 to 0.65 s after the release:

| Speed | Runs on for up to |
| --- | --- |
| 2 mm/s | 1.3 mm |
| 10 mm/s | 6.5 mm |
| 50 mm/s | 33 mm |
| 250 mm/s | 16 cm |

Choose the speeds with that in mind. jogpad refuses speeds above 250 mm/s, the
reduced speed of robots moved by hand (ISO 10218-1); the machinery directive
itself names no figure.

A pad unplugged while a key is held counts as released. A jogpad that crashes
sends nothing more, so the axis stops after the moves already queued. Any
other key of the pad ends the move as well.

## Wireless pads

Wireless pads can drop or delay key presses and releases. Prefer a cable. If a
release is lost on the way, a held key's axis keeps moving until you press
another key, at most to the end of the axis.
