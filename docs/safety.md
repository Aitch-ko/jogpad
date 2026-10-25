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
after you stop turning.

## Locks

jogpad refuses to move while a print or job is running or paused. Further
conditions, such as a spindle or laser being on, can be added per machine in
the configuration.

## Holding a key

Actions that run while a key is held (for example feeding filament) repeat
their command while held. The firmware side must switch off on its own when the
repetition stops, otherwise a lost cable or a crashed service leaves it running.

## Wireless pads

Wireless pads can drop or delay key presses. Prefer a cable. Over radio jogpad
only ever moves in single steps.
