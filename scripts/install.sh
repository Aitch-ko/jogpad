#!/usr/bin/env bash
# Installs jogpad from this checkout as a systemd service next to Klipper.
# Run it again after `git pull` to update. Asks for sudo for the service only.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${JOGPAD_VENV:-$HOME/jogpad-env}"
DATA_DIR="${JOGPAD_DATA:-$HOME/printer_data}"
SERVICE_FILE=/etc/systemd/system/jogpad.service

if [ -d "$DATA_DIR/config" ]; then
    CONFIG_FILE="$DATA_DIR/config/jogpad.toml"
else
    CONFIG_FILE="$HOME/.config/jogpad/jogpad.toml"
fi

say() { printf '\n== %s\n' "$*"; }
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = Linux ] || fail "jogpad reads input devices on Linux only."
[ "$(id -u)" -ne 0 ] || fail "run as the user that runs Klipper, not as root."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || fail "Python 3.10 or newer is needed, found $(python3 --version 2>&1)."

# Ask for the password now rather than after the long pip run, when nobody watches.
echo "The service part needs sudo."
sudo -v

say "Python environment in $VENV_DIR"
[ -x "$VENV_DIR/bin/python" ] || python3 -m venv "$VENV_DIR" \
    || fail "creating the venv failed; on Debian install python3-venv."
echo "Installing jogpad and its dependencies; the first run can take a few minutes."
"$VENV_DIR/bin/pip" install --upgrade --disable-pip-version-check "$REPO_DIR"
"$VENV_DIR/bin/jogpad" --version

say "Configuration $CONFIG_FILE"
if [ -e "$CONFIG_FILE" ]; then
    echo "exists, left unchanged"
else
    mkdir -p "$(dirname "$CONFIG_FILE")"
    {
        echo "# jogpad configuration. All options:"
        echo "# https://github.com/Aitch-ko/jogpad/blob/main/docs/reference/config.md"
        echo
        echo "[input]"
        echo "# Your pad's devices. Found on this computer:"
        "$VENV_DIR/bin/jogpad" devices | sed 's/^/#   /'
        echo "devices = []"
    } > "$CONFIG_FILE"
    echo "written; add your pad under devices"
fi
"$VENV_DIR/bin/jogpad" check-config "$CONFIG_FILE"

say "Service (needs sudo)"
if ! id -nG | tr ' ' '\n' | grep -qx input; then
    sudo usermod -aG input "$USER"
    echo "added $USER to the group input"
fi
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=jogpad jog pendant
Documentation=https://github.com/Aitch-ko/jogpad
After=moonraker.service

[Service]
Type=simple
User=$USER
SupplementaryGroups=input
ExecStart=$VENV_DIR/bin/jogpad serve --config $CONFIG_FILE
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --quiet jogpad
sudo systemctl restart jogpad

# The macro behind the on/off switch in Mainsail and Fluidd. It is jogpad's file,
# so updates replace it; it does nothing until printer.cfg includes it.
if [ -d "$DATA_DIR/config" ]; then
    cp "$REPO_DIR/klipper/jogpad.cfg" "$DATA_DIR/config/jogpad.cfg"
    echo "wrote $DATA_DIR/config/jogpad.cfg; see the docs to switch jogpad on and off in Mainsail"
fi

# Moonraker only lets Mainsail and Fluidd control services listed here.
ASVC="$DATA_DIR/moonraker.asvc"
if [ -f "$ASVC" ] && ! grep -qx jogpad "$ASVC"; then
    echo jogpad >> "$ASVC"
    echo "added jogpad to $ASVC; restart Moonraker to see it in Mainsail and Fluidd"
fi

say "Done"
systemctl --no-pager --lines=0 status jogpad || true
echo "Logs: journalctl -u jogpad -f"
