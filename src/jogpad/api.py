"""HTTP API and web page. Swagger UI is served at /docs, ReDoc at /redoc."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jogpad import __version__
from jogpad.config import Config
from jogpad.core import State
from jogpad.events import EventHub
from jogpad.i18n import messages
from jogpad.keys import key_name
from jogpad.layouts import NO_LAYOUT, Layout, layout_ids, load_layout

WEB_DIR = Path(__file__).parent / "web"
KEEPALIVE_S = 15


class Health(BaseModel):
    status: str


class Version(BaseModel):
    version: str


class JogState(BaseModel):
    step: float
    selected_axis: str
    home_selection: list[str] | None
    last_refusal: str | None


class KeyEvent(BaseModel):
    code: int
    name: str
    pressed: bool
    action: str | None
    control: str | None
    part: str | None


class PadView(BaseModel):
    layout: Layout | None
    actions: dict[str, dict[str, str]]


def describe_pad(config: Config) -> PadView:
    """The configured layout with the action of every control part."""
    if config.input.layout == NO_LAYOUT:
        return PadView(layout=None, actions={})
    layout = load_layout(config.input.layout)
    by_code = config.input.actions_by_code()
    actions: dict[str, dict[str, str]] = {}
    for code, (control, part) in layout.parts_by_code().items():
        if code in by_code:
            actions.setdefault(control, {})[part] = by_code[code].value
    return PadView(layout=layout, actions=actions)


def describe_event(config: Config, code: int, value: int) -> KeyEvent:
    action = config.input.actions_by_code().get(code)
    control: str | None = None
    part: str | None = None
    if config.input.layout != NO_LAYOUT:
        control, part = load_layout(config.input.layout).parts_by_code().get(code, (None, None))
    return KeyEvent(
        code=code,
        name=key_name(code),
        pressed=value != 0,
        action=action.value if action else None,
        control=control,
        part=part,
    )


def create_app(
    config: Config,
    state: Callable[[], State] | None = None,
    events: EventHub | None = None,
) -> FastAPI:
    app = FastAPI(
        title="jogpad",
        version=__version__,
        description="Status and configuration of a jogpad instance. "
        "jogpad never moves a machine through this API.",
    )
    hub = events or EventHub()

    @app.get("/api/health", summary="Liveness check")
    def health() -> Health:
        return Health(status="ok")

    @app.get("/api/version", summary="Installed jogpad version")
    def version() -> Version:
        return Version(version=__version__)

    @app.get("/api/config", summary="Active configuration")
    def get_config() -> Config:
        return config

    @app.get("/api/state", summary="Current step size, selected axis and HOME selection")
    def get_state() -> JogState:
        s = state() if state else State(config.jog.steps[0], config.jog.select_axes[0], None, None)
        return JogState(
            step=s.step,
            selected_axis=s.selected_axis,
            home_selection=s.home_selection,
            last_refusal=s.last_refusal,
        )

    @app.get("/api/layouts", summary="Known pad layouts")
    def get_layouts() -> list[str]:
        return layout_ids()

    @app.get("/api/layouts/{layout_id}", summary="One pad layout")
    def get_layout(layout_id: str) -> Layout:
        if layout_id not in layout_ids():
            raise HTTPException(404, f"unknown layout {layout_id}")
        return load_layout(layout_id)

    @app.get("/api/pad", summary="Configured pad layout and the action of each control")
    def get_pad() -> PadView:
        return describe_pad(config)

    @app.get("/api/messages", summary="Texts of the web page in the configured language")
    def get_messages() -> dict[str, str]:
        return messages("ui.", config.server.language)

    @app.get(
        "/api/events",
        summary="Live key presses as server-sent events (KeyEvent as JSON)",
        response_class=StreamingResponse,
    )
    async def get_events(request: Request) -> StreamingResponse:
        async def stream() -> AsyncIterator[str]:
            queue = hub.subscribe()
            try:
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), KEEPALIVE_S)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    code, value = event
                    payload = describe_event(config, code, value).model_dump()
                    yield f"data: {json.dumps(payload)}\n\n"
            finally:
                hub.unsubscribe(queue)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    # Last: the page must not shadow the API or the docs.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app
