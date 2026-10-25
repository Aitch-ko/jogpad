# Installation

!!! note
    jogpad has not been released on PyPI yet. Install it from the repository.

jogpad needs Python 3.10 or newer. Raspberry Pi OS 12 (Bookworm) ships 3.11.
Raspberry Pi OS 11 (Bullseye) ships 3.9; there jogpad gets its own Python, see
[older systems](#older-systems-with-python-39).

## On the Klipper computer

Log in as the user that runs Klipper, usually over SSH:

```bash
cd ~
git clone https://github.com/Aitch-ko/jogpad.git
./jogpad/scripts/install.sh
```

The installer asks for your sudo password first, then downloads jogpad's
dependencies, which takes a few minutes on a Raspberry Pi. It

- installs jogpad into its own environment `~/jogpad-env`, next to Klipper's
  `~/klippy-env`
- writes `~/printer_data/config/jogpad.toml` if it does not exist yet, so you
  can edit it in Mainsail or Fluidd. Existing files are left alone
- adds you to the group `input`, which may read keyboards and pads
- sets up the systemd service `jogpad`, which starts with the machine
- adds `jogpad` to `~/printer_data/moonraker.asvc`. After a Moonraker restart,
  Mainsail and Fluidd can start, stop and restart jogpad from their service menu
- asks whether to add the on/off switch for Mainsail and Fluidd to
  `printer.cfg` and `moonraker.conf`, with a backup of each, see
  [the switch](usage.md#switch-it-on-and-off-in-mainsail-or-fluidd)

Then enter your pad in `jogpad.toml`, see [Klipper setup](usage.md).

At the end the installer prints the address of jogpad's web page, for example
`http://192.168.1.50:7150/`. Open it on any computer in your network: it
shows every key press live, learns keys and checks the direction of each axis.
Under **Set up** it can also add the pad as a camera panel in Mainsail and
Fluidd, see [web page](usage.md#web-page).

To update, pull and run the installer again:

```bash
cd ~/jogpad && git pull && ./scripts/install.sh
```

Logs: `journalctl -u jogpad -f`.

## Older systems with Python 3.9

jogpad runs in its own environment, so it does not need the system's Python.
[uv](https://docs.astral.sh/uv/) installs a newer one in your home folder,
without sudo and without touching the system or Klipper:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.12
JOGPAD_PYTHON="$(~/.local/bin/uv python find 3.12)" ./jogpad/scripts/install.sh
```

The installer says the same when it finds Python 3.9. Klipper keeps running on
its own Python; jogpad talks to it only through Moonraker.

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
