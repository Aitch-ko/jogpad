#!/usr/bin/env bash
# Installs jogpad as a systemd service next to Klipper: the release on PyPI that
# this checkout belongs to. Asks for sudo for the service only.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$REPO_DIR/pyproject.toml")"
VENV_DIR="${JOGPAD_VENV:-$HOME/jogpad-env}"
# The Python jogpad's own venv is built from; Klipper keeps its own.
PYTHON="${JOGPAD_PYTHON:-python3}"
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
is_new_enough() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2> /dev/null; }
too_old() {
    printf 'Error: jogpad needs Python 3.10 or newer; %s is %s.\n' "$1" "$("$2" --version 2>&1)" >&2
    cat >&2 <<EOF
On Raspberry Pi OS 11 (Bullseye), install a newer one next to the system's with uv:
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ~/.local/bin/uv python install 3.12
and run again with:
    JOGPAD_PYTHON="\$(~/.local/bin/uv python find 3.12)" $0
EOF
    exit 1
}
command -v "$PYTHON" > /dev/null || fail "Python not found: $PYTHON"
is_new_enough "$PYTHON" || too_old "$PYTHON" "$PYTHON"

# Ask for the password now rather than after the long pip run, when nobody watches.
echo "The service part needs sudo."
sudo -v

say "Python environment in $VENV_DIR"
[ -x "$VENV_DIR/bin/python" ] || "$PYTHON" -m venv "$VENV_DIR" \
    || fail "creating the venv failed; on Debian install python3-venv."
# A venv from an earlier attempt keeps the Python it was made with.
is_new_enough "$VENV_DIR/bin/python" \
    || too_old "the venv $VENV_DIR (remove it, then run again)" "$VENV_DIR/bin/python"
[ -n "$VERSION" ] || fail "no version found in $REPO_DIR/pyproject.toml"
echo "Installing jogpad $VERSION from PyPI; the first run can take a few minutes."
# From PyPI rather than from this checkout: Moonraker updates only packages that
# came from an index or from git, not ones built from a folder.
"$VENV_DIR/bin/pip" install --upgrade --disable-pip-version-check "jogpad==$VERSION" \
    || fail "installing jogpad $VERSION from PyPI failed; is this computer online?"
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
# Only root may write hidraw nodes by default; jogpad program-pad needs to.
sudo tee /etc/udev/rules.d/70-jogpad.rules > /dev/null <<'EOF'
# CH57x macro pads: the group input may program them with jogpad program-pad
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1189", ATTRS{idProduct}=="884[02]", MODE="0660", GROUP="input"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
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

# The on/off switch in Mainsail and Fluidd changes printer.cfg and moonraker.conf,
# which belong to the user: ask once, and on updates only refresh the macro.
if [ -f "$DATA_DIR/config/printer.cfg" ] && [ -f "$DATA_DIR/config/moonraker.conf" ]; then
    say "Switch in Mainsail and Fluidd"
    if grep -qE '^\[include[[:space:]]+jogpad\.cfg\]' "$DATA_DIR/config/printer.cfg"; then
        "$VENV_DIR/bin/jogpad" setup-switch --config-dir "$DATA_DIR/config"
    else
        echo "jogpad can add an on/off switch to Mainsail and Fluidd. That adds"
        echo "[include jogpad.cfg] to printer.cfg and [power jogpad] to moonraker.conf;"
        echo "both files are backed up first."
        read -r -p "Set it up? [y/N] " answer || answer=""
        case "$answer" in
            [yYjJ]*) "$VENV_DIR/bin/jogpad" setup-switch --config-dir "$DATA_DIR/config" ;;
            *) echo "skipped; run 'jogpad setup-switch' later to add it" ;;
        esac
    fi
fi

# Mainsail and Fluidd show updates for what moonraker.conf lists. The file
# belongs to the user, so ask, like for the switch.
MOONRAKER_CONF="$DATA_DIR/config/moonraker.conf"
if [ -f "$MOONRAKER_CONF" ] && grep -qE '^\[update_manager\]' "$MOONRAKER_CONF" \
    && ! grep -qE '^\[update_manager[[:space:]]+jogpad\]' "$MOONRAKER_CONF"; then
    say "Updates in Mainsail and Fluidd"
    echo "Mainsail and Fluidd can show jogpad's updates and install them with one"
    echo "click. That adds [update_manager jogpad] to moonraker.conf, backed up first."
    read -r -p "Add it? [Y/n] " answer || answer=""
    case "$answer" in
        [nN]*) echo "skipped; the installer asks again next time" ;;
        *)
            cp "$MOONRAKER_CONF" "$MOONRAKER_CONF.bak-$(date +%Y%m%d-%H%M%S)"
            printf '\n[update_manager jogpad]\ntype: python\nvirtualenv: %s\nproject_name: jogpad\nmanaged_services: jogpad\n' \
                "$VENV_DIR" >> "$MOONRAKER_CONF"
            echo "added; restart Moonraker to see jogpad in the update panel"
            ;;
    esac
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

# Nothing else points to the page, so name it; jogpad.toml may move it.
read -r HOST PORT < <("$VENV_DIR/bin/python" -c '
import sys
from pathlib import Path
from jogpad.config import load_config
server = load_config(Path(sys.argv[1])).server
print(server.host, server.port)' "$CONFIG_FILE")
if [ "$HOST" = 127.0.0.1 ] || [ "$HOST" = localhost ]; then
    echo "Web page: on this computer only (host = $HOST), see the docs for an SSH tunnel"
else
    IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "Web page: http://${IP:-$(hostname).local}:$PORT/ (or http://$(hostname).local:$PORT/)"
fi
