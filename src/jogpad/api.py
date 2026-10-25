"""HTTP API and web page. Swagger UI is served at /docs, ReDoc at /redoc."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from collections.abc import AsyncIterator, Callable
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from jogpad import __version__
from jogpad.config import Action, Config
from jogpad.config_store import assign_keys, conflicts, set_invert
from jogpad.core import BackendError, State, Switch
from jogpad.events import EventHub
from jogpad.i18n import languages, messages, t
from jogpad.keys import key_name
from jogpad.layouts import NO_LAYOUT, Layout, layout_ids, load_layout
from jogpad.moonraker import Moonraker
from jogpad.service import Service

WEB_DIR = Path(__file__).parent / "web"
KEEPALIVE_S = 15
LANG = Query(None, description="Language of the page; default: the configured one.")
MAX_LEARN_S = 60
# Height of the state bar in the panel view, in key units: one row of cells at the
# usual width of a camera panel.
PANEL_STATE_ROWS = 0.8
FORBIDDEN = "changes are only allowed from this computer and from computers Moonraker trusts"


class Health(BaseModel):
    status: str


class Version(BaseModel):
    version: str
    links: dict[str, str] = Field(
        description="Project URLs from the package metadata, e.g. `Homepage`, `Issues`, "
        "`Changelog`. Empty when jogpad runs from a source tree without installing."
    )


def project_links() -> dict[str, str]:
    """[project.urls] from pyproject.toml, as installed with the package."""
    try:
        entries = metadata("jogpad").get_all("Project-URL") or []
    except PackageNotFoundError:
        return {}
    return dict(entry.split(", ", 1) for entry in entries if ", " in entry)


class JogState(BaseModel):
    switched_on: bool | None = Field(
        description="The switch in Mainsail or Fluidd; true without one, null if unreadable."
    )
    has_switch: bool = Field(
        description="Whether Klipper has the switch macro, so `PUT /api/switch` works."
    )
    step: float
    selected_axis: str
    home_selection: list[str] | None
    last_refusal: str | None
    learning: bool


class LearnRequest(BaseModel):
    seconds: float = Field(30, ge=0, le=MAX_LEARN_S, description="0 ends learning.")


class KeysRequest(BaseModel):
    keys: list[str]
    replace: bool = Field(
        False, description="Take the keys away from other actions instead of refusing."
    )


class SwitchRequest(BaseModel):
    on: bool


class InvertRequest(BaseModel):
    axes: list[str]


class KeyEvent(BaseModel):
    code: int
    name: str
    pressed: bool
    action: str | None
    control: str | None
    part: str | None


class Panel(BaseModel):
    url: str | None = Field(
        description="Address that Mainsail and Fluidd show as the camera `jogpad`; "
        "null while it is not added."
    )


class Language(BaseModel):
    code: str
    name: str = Field(description="Name of the language in that language.")


class PadView(BaseModel):
    layout: Layout | None
    actions: dict[str, dict[str, str]]


def describe_pad(config: Config, language: str | None = None) -> PadView:
    """The configured layout with the action of every control part."""
    if config.input.layout == NO_LAYOUT:
        return PadView(layout=None, actions={})
    layout = load_layout(config.input.layout).localized(language or config.server.language)
    by_code = config.input.actions_by_code()
    actions: dict[str, dict[str, str]] = {}
    for code, (control, part) in layout.parts_by_code().items():
        if code in by_code:
            actions.setdefault(control, {})[part] = by_code[code].value
    return PadView(layout=layout, actions=actions)


def panel_aspect_ratio(config: Config) -> str:
    """Width to height of the panel view: the pad plus the state bar above it."""
    if config.input.layout == NO_LAYOUT:
        return "4:3"
    controls = load_layout(config.input.layout).controls
    width = max(c.x + c.w for c in controls)
    height = max(c.y + c.h for c in controls) + PANEL_STATE_ROWS
    return f"{round(width * 10)}:{round(height * 10)}"


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
    service: Service | None = None,
    config_path: Path | None = None,
    moonraker: Moonraker | None = None,
) -> FastAPI:
    """`service` is the running jogpad; without it the page shows a static state.
    Changes are written to `config_path`. They are allowed from this computer and
    from the addresses `moonraker` trusts, asked anew for every change."""
    app = FastAPI(
        title="jogpad",
        version=__version__,
        description="Status and configuration of a jogpad instance. "
        "jogpad never moves a machine through this API.",
    )
    hub = service.events if service else EventHub()
    current = [config]

    def cfg() -> Config:
        return current[0]

    def page_language(lang: str | None) -> str:
        # Each viewer may read the page in their own language; console messages
        # stay in the configured one, since everyone at the machine sees them.
        if lang is None:
            return cfg().server.language
        if lang not in languages():
            raise HTTPException(422, f"unknown language {lang}, known: {', '.join(languages())}")
        return lang

    def may_change(request: Request) -> None:
        # A changed STOP key from anywhere in the network would be a nasty surprise.
        # Computers Moonraker trusts may move the machine anyway, so they may also
        # change what the keys do.
        if cfg().server.allow_remote_changes:
            return
        try:
            address = ipaddress.ip_address(request.client.host if request.client else "")
        except ValueError:
            raise HTTPException(403, FORBIDDEN) from None
        if address.is_loopback:
            return
        if moonraker is not None:
            try:
                networks = moonraker.trusted_networks()
            except BackendError as exc:
                raise HTTPException(
                    503, f"cannot ask Moonraker which computers it trusts: {exc}"
                ) from exc
            if any(address in network for network in networks):
                return
        raise HTTPException(403, FORBIDDEN)

    def save(change: Callable[[Path], Config]) -> Config:
        if config_path is None:
            raise HTTPException(409, "jogpad runs without a config file (serve --config)")
        try:
            new = change(config_path)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(422, str(exc)) from exc
        current[0] = new
        if service:
            service.reload(new)
        return new

    @app.get("/api/health", summary="Liveness check")
    def health() -> Health:
        return Health(status="ok")

    @app.get("/api/version", summary="Installed jogpad version")
    def version() -> Version:
        return Version(version=__version__, links=project_links())

    @app.get("/api/config", summary="Active configuration")
    def get_config() -> Config:
        return cfg()

    @app.get("/api/state", summary="Current step size, selected axis and HOME selection")
    def get_state() -> JogState:
        c = cfg()
        s = service.state() if service else State(c.jog.steps[0], c.jog.select_axes[0], None, None)
        switch = service.jogger.switch() if service else Switch.MISSING
        return JogState(
            switched_on=None if switch is Switch.UNREADABLE else switch is not Switch.OFF,
            has_switch=switch in (Switch.ON, Switch.OFF),
            step=s.step,
            selected_axis=s.selected_axis,
            home_selection=s.home_selection,
            last_refusal=s.last_refusal,
            learning=service.is_learning() if service else False,
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
    def get_pad(lang: str | None = LANG) -> PadView:
        return describe_pad(cfg(), page_language(lang))

    @app.get("/api/languages", summary="Languages the web page can be shown in")
    def get_languages() -> list[Language]:
        return [Language(code=code, name=t("ui.language_name", code)) for code in languages()]

    @app.get("/api/messages", summary="Texts of the web page")
    def get_messages(lang: str | None = LANG) -> dict[str, str]:
        return messages("ui.", page_language(lang))

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
                    payload = describe_event(cfg(), code, value).model_dump()
                    yield f"data: {json.dumps(payload)}\n\n"
            finally:
                hub.unsubscribe(queue)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.post(
        "/api/learn",
        summary="For a while keys only show up here and move nothing; STOP still works",
        dependencies=[Depends(may_change)],
    )
    def learn(request: LearnRequest) -> JogState:
        if service is None:
            raise HTTPException(409, "no pad is being read")
        service.learn(request.seconds)
        return get_state()

    @app.put(
        "/api/keys/{action}",
        summary="Assign keys to an action and save the configuration",
        dependencies=[Depends(may_change)],
        responses={409: {"description": "A key belongs to another action"}},
    )
    def put_keys(action: Action, request: KeysRequest) -> Config:
        try:
            taken = conflicts(cfg(), action, request.keys)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if taken and not request.replace:
            detail = {name: other.value for name, other in taken.items()}
            raise HTTPException(409, {"conflicts": detail})
        return save(lambda path: assign_keys(path, cfg(), action, request.keys))

    @app.put(
        "/api/invert",
        summary="Set the axes whose keys move the other way and save the configuration",
        dependencies=[Depends(may_change)],
    )
    def put_invert(request: InvertRequest) -> Config:
        return save(lambda path: set_invert(path, request.axes))

    def firmware() -> Moonraker:
        if moonraker is None:
            raise HTTPException(503, "jogpad runs without Moonraker")
        return moonraker

    @app.put(
        "/api/switch",
        summary="Switch jogpad on or off, like its switch in Mainsail and Fluidd",
        dependencies=[Depends(may_change)],
    )
    def put_switch(request: SwitchRequest) -> JogState:
        try:
            firmware().set_switch(request.on)
        except BackendError as exc:
            raise HTTPException(503, f"cannot switch jogpad: {exc}") from exc
        return get_state()

    @app.get("/api/panel", summary="jogpad's view in Mainsail and Fluidd")
    def get_panel() -> Panel:
        try:
            return Panel(url=firmware().panel_url())
        except BackendError as exc:
            raise HTTPException(503, f"cannot ask Moonraker: {exc}") from exc

    @app.put(
        "/api/panel",
        summary="Show jogpad's view in Mainsail and Fluidd as the camera `jogpad`",
        dependencies=[Depends(may_change)],
    )
    def put_panel(request: Request) -> Panel:
        # Mainsail and Fluidd load the view from the address this page was opened
        # with; a tunnel's 127.0.0.1 would point every other browser at itself.
        host = request.url.hostname or ""
        if host == "localhost" or _is_loopback(host):
            raise HTTPException(409, "open this page with the printer's address, not " + host)
        url = f"{request.base_url}?view=panel"
        try:
            firmware().add_panel(url, panel_aspect_ratio(cfg()))
        except BackendError as exc:
            raise HTTPException(503, f"cannot add the camera in Moonraker: {exc}") from exc
        return Panel(url=url)

    @app.delete(
        "/api/panel",
        summary="Remove jogpad's view from Mainsail and Fluidd",
        dependencies=[Depends(may_change)],
    )
    def delete_panel() -> Panel:
        try:
            firmware().remove_panel()
        except BackendError as exc:
            raise HTTPException(503, f"cannot remove the camera in Moonraker: {exc}") from exc
        return Panel(url=None)

    # Last: the page must not shadow the API or the docs.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
