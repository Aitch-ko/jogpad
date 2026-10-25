"""Take the screenshots of the web page used in the documentation.

    pip install -e ".[screenshots]" && playwright install chromium
    python scripts/screenshots.py

Starts jogpad with a demo configuration, plays key presses into the page and
writes PNGs to docs/assets/screenshots/. Run it again after changing the page,
so the documentation does not show an old one.
"""

from __future__ import annotations

import socket
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import Page, sync_playwright

from jogpad.api import create_app
from jogpad.config import load_config
from jogpad.moonraker import Moonraker

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "screenshots"
VIEWPORT = {"width": 1100, "height": 860}
# Width of a camera panel in Mainsail; the height follows the keypad panel's 40:58.
PANEL_VIEWPORT = {"width": 400, "height": 580}

# KeyEvent payloads as /api/events sends them.
PRESSES = [
    {"code": 55, "name": "KEY_KPASTERISK", "action": "step", "control": "asterisk"},
    {"code": 78, "name": "KEY_KPPLUS", "action": "z_plus", "control": "plus"},
    {"code": 72, "name": "KEY_KP8", "action": "y_plus", "control": "8"},
]
HELD = {"code": 77, "name": "KEY_KP6", "action": "x_plus", "control": "6"}
Y_PLUS = {"code": 72, "name": "KEY_KP8", "action": "y_plus", "control": "8"}


class NoCamera(Moonraker):
    """A Moonraker without jogpad's camera, so the setup shows the Add button."""

    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:1")

    def panel_url(self) -> str | None:
        return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "jogpad.toml"
        config_path.write_text('[input]\nlayout = "numpad"\n', encoding="utf-8")
        url = serve(config_path)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for scheme in ("light", "dark"):
                context = browser.new_context(
                    viewport=VIEWPORT, color_scheme=scheme, device_scale_factor=2
                )
                page = context.new_page()
                open_page(page, url)
                live_view(page, f"web-page-{scheme}.png")
                if scheme == "light":
                    learning(page, "learn-key.png")
                    direction_check(page, "check-direction.png")
                context.close()
            # The panel view as Mainsail shows it: a narrow camera panel, dark.
            context = browser.new_context(
                viewport=PANEL_VIEWPORT, color_scheme="dark", device_scale_factor=2
            )
            page = context.new_page()
            open_page(page, url + "&view=panel")
            press(page, HELD)
            page.screenshot(path=OUT / "mainsail-panel.png")
            context.close()
            browser.close()
    for path in sorted(OUT.glob("*.png")):
        print(path.relative_to(ROOT))


def serve(config_path: Path) -> str:
    """jogpad in a background thread on a free port; the demo has no pad attached."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(load_config(config_path), config_path=config_path, moonraker=NoCamera())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}/?lang=en"


def open_page(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_selector("#keys tr", state="attached")
    # Screenshots must not catch a colour halfway through a transition.
    page.add_style_tag(content="* { transition: none !important; }")
    # A version number in the pictures would be outdated with the next release.
    page.evaluate("document.getElementById('version').textContent = ''")


def press(page: Page, event: dict[str, object], pressed: bool = True) -> None:
    page.evaluate("e => showEvent({...e, part: 'press'})", {**event, "pressed": pressed})


def live_view(page: Page, name: str) -> None:
    for event in PRESSES:
        press(page, event)
        press(page, event, pressed=False)
    press(page, HELD)
    page.evaluate("document.getElementById('link').classList.add('on')")
    page.evaluate("document.getElementById('link').textContent = t('ui.connected')")
    # Down to the pad and the key list; the setup part has its own pictures.
    bottom = page.evaluate("document.querySelector('.pad').getBoundingClientRect().bottom")
    page.screenshot(
        path=OUT / name, clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": bottom + 16}
    )
    press(page, HELD, pressed=False)


def learning(page: Page, name: str) -> None:
    # The setup part starts folded away.
    page.evaluate("$('setup-details').open = true")
    page.evaluate("say(t('ui.press_key', {action: labels.e_plus}), 'wait')")
    page.locator(".setup").screenshot(path=OUT / name)
    page.evaluate("say('')")


def direction_check(page: Page, name: str) -> None:
    page.evaluate("checkDirection('Y')")
    press(page, Y_PLUS)
    page.locator(".setup").screenshot(path=OUT / name)


if __name__ == "__main__":
    main()
