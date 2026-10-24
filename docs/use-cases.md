# Use cases

Every machine below has the same problem: your eyes need to be at the tool,
and the controls are somewhere else. Each story says whether jogpad covers it
today.

!!! info "What works today"
    jogpad talks to Klipper through Moonraker. Other firmwares are planned,
    not built. Where a story needs one of them, it says so.

## 3D printer: levelling the bed

You slide a sheet of paper under the nozzle and lower Z until the paper drags.
On a touchscreen that means looking at the screen for every tap, or tapping
blind while you watch the paper. One slip onto the next button and the nozzle
moves 10 mm instead of 0.1, or the wrong way.

With jogpad, Z− is a key under your finger. You switch to 0.01 mm steps with
another key and keep your eyes on the paper. The same goes for setting the Z
offset, checking a probe, or positioning the nozzle over a mark.

**Works today** with Klipper.

## 3D printer: loading filament and tidying up

Pushing filament through by a few millimetres, pulling it back, moving the
head out of the way to clear a blob: small moves you want to do with one hand
while the other hand is busy.

**Works today** with Klipper. Extruder keys have no default; assign them on
the [web page](usage.md#web-page).

## CNC mill: touching off a workpiece

To find the edge of a workpiece you move the tool towards it in ever smaller
steps, with a sheet of paper or an edge finder, until it just touches. That is
what a handwheel (MPG) is for: one detent, one step, eyes on the tool.

**Planned.** Most hobby mills run GRBL, FluidNC or LinuxCNC. FluidNC is on the
list; LinuxCNC already reads keyboards with `hal_input`. A mill running
Klipper works today.

## Laser cutter and engraver: setting the origin and the focus

Before a job you move the head to the corner of the sheet and set the focus
distance, often with a gauge between nozzle and material. You watch the head,
not the screen.

**Planned** for GRBL-based lasers via FluidNC support.

!!! danger "The beam stays off"
    jogpad only moves axes. It never switches a laser on, and positioning is
    done with the beam off. Add a lock so jogpad refuses to move while the
    laser is enabled, see [Locks](usage.md#locks). STOP is not an emergency
    stop; see [Safety](safety.md).

## Plasma cutter: tracing the outline

Before cutting, many people trace the outline of the job over the sheet to
check it fits. Small corrections of the start point are easier with a knob
than with a mouse while looking at the torch.

**Planned**, depends on the firmware (often LinuxCNC or GRBL-based).
The same rule as for lasers applies: the torch stays off, and a lock should
refuse moves while it could fire.

## Metal additive manufacturing: positioning the head

On wire or powder deposition machines (DED) the head is positioned over an
edge or a previous layer and the distance to the workpiece is set by eye,
often with the operator wearing gloves and protective eyewear. Keys you can
feel help more than a touchscreen there.

**Works today** where the machine runs Klipper, with locks on everything that
can emit: the energy source must be off whenever jogpad may move.

## Your machine is not listed?

Open an issue with the [feature request](https://github.com/Aitch-ko/jogpad/issues/new/choose)
template: which machine, which firmware, and what you need to move by hand.
