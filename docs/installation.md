# Installation

!!! note
    jogpad is also on [PyPI](https://pypi.org/project/jogpad/), but on the
    Klipper computer use the installer below: `pip install jogpad` only puts the
    program there, without the service, the access to the pad and `jogpad.toml`.

jogpad needs Python 3.10 or newer. Raspberry Pi OS 12 (Bookworm) ships 3.11.
Raspberry Pi OS 11 (Bullseye) ships 3.9, and many printers with Klipper from the
factory ship 3.7 or 3.9; there the installer downloads a newer one for jogpad,
see [older systems](#older-systems-with-python-37-or-39).

## On the Klipper computer

Log in as the user that runs Klipper, usually over SSH:

```bash
cd ~
git clone https://github.com/Aitch-ko/jogpad.git
./jogpad/scripts/install.sh
```

The installer asks for your sudo password first, then downloads jogpad and its
dependencies from PyPI, which takes a few minutes on a Raspberry Pi. Where the
system's Python is older than 3.10, it offers to download a newer one before
that, see [older systems](#older-systems-with-python-37-or-39). It

- installs the release of jogpad that the checkout belongs to into its own
  environment `~/jogpad-env`, next to Klipper's `~/klippy-env`
- writes `~/printer_data/config/jogpad.toml` if it does not exist yet, so you
  can edit it in Mainsail or Fluidd. Existing files are left alone
- adds you to the group `input`, which may read keyboards and pads, and lets
  that group program CH57x macro pads (`/etc/udev/rules.d/70-jogpad.rules`)
- sets up the systemd service `jogpad`, which starts with the machine
- adds `jogpad` to `~/printer_data/moonraker.asvc`. After a Moonraker restart,
  Mainsail and Fluidd can start, stop and restart jogpad from their service menu
- asks whether to add the on/off switch for Mainsail and Fluidd to
  `printer.cfg` and `moonraker.conf`, with a backup of each, see
  [the switch](usage.md#switch-it-on-and-off-in-mainsail-or-fluidd)
- asks whether to add `[update_manager jogpad]` to `moonraker.conf`, with a
  backup. After a Moonraker restart, Mainsail and Fluidd show jogpad's updates
  in their update panel

Then enter your pad in `jogpad.toml`, see [Klipper setup](usage.md).

At the end the installer prints the address of jogpad's web page, for example
`http://192.168.1.50:7150/`. Open it on any computer in your network: it
shows every key press live, learns keys and checks the direction of each axis.
Under **Set up** it can also add the pad as a camera panel in Mainsail and
Fluidd, see [web page](usage.md#web-page).

New releases show up in the update panel of Mainsail and Fluidd. One click
installs the release from PyPI and restarts jogpad. The installer is needed
again only when a release note says "run the installer again", for example
because the service changed, or if you left out the update panel:

```bash
cd ~/jogpad && git pull && ./scripts/install.sh
```

Logs: `journalctl -u jogpad -f`.

## Older systems with Python 3.7 or 3.9

Raspberry Pi OS 11 (Bullseye) ships Python 3.9. Many printers with Klipper from
the factory run Debian 10 or 11 with Python 3.7 or 3.9, for example many QIDI
and Sovol printers. jogpad runs in its own environment, so the installer offers
to download Python 3.12 with [uv](https://docs.astral.sh/uv/) into your home
folder, about 120 MB. That needs no sudo and leaves the system's Python alone.
jogpad's environment keeps using it, also for updates from the update panel.
Klipper keeps running on its own Python; jogpad talks to it only through
Moonraker.

If the download fails on a printer with a Makerbase board, QIDI printers in
particular, check the clock with `date`. These boards often start with a wrong
date, and then every download fails. Set it with `sudo date -s 'YYYY-MM-DD'`
and run the installer again.

To use a Python of your own instead, name it when you run the installer:

```bash
JOGPAD_PYTHON=/usr/bin/python3.11 ./jogpad/scripts/install.sh
```

## For development

```bash
git clone https://github.com/Aitch-ko/jogpad.git
cd jogpad
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/jogpad --version
```

Run the API without a pad attached:

```bash
.venv/bin/jogpad serve
```

Then open `http://127.0.0.1:7150/docs` for the Swagger UI.
