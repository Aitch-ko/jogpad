# Installation

!!! note
    jogpad has not been released on PyPI yet. Install it from the repository.

jogpad needs Python 3.10 or newer. Raspberry Pi OS 11 (Bullseye) ships Python
3.9 and is not supported; Raspberry Pi OS 12 (Bookworm) ships 3.11.

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

Then enter your pad in `jogpad.toml`, see [Klipper setup](usage.md).

To update, pull and run the installer again:

```bash
cd ~/jogpad && git pull && ./scripts/install.sh
```

Logs: `journalctl -u jogpad -f`.

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
