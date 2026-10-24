"""HTTP API. Swagger UI is served at /docs, ReDoc at /redoc."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from pydantic import BaseModel

from jogpad import __version__
from jogpad.config import Config
from jogpad.core import State


class Health(BaseModel):
    status: str


class Version(BaseModel):
    version: str


class JogState(BaseModel):
    step: float
    selected_axis: str
    home_selection: list[str] | None
    last_refusal: str | None


def create_app(config: Config, state: Callable[[], State] | None = None) -> FastAPI:
    app = FastAPI(
        title="jogpad",
        version=__version__,
        description="Status and configuration of a jogpad instance. "
        "jogpad never moves a machine through this API.",
    )

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

    return app
