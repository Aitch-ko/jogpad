"""HTTP API. Swagger UI is served at /docs, ReDoc at /redoc."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from jogpad import __version__
from jogpad.config import Config


class Health(BaseModel):
    status: str


class Version(BaseModel):
    version: str


def create_app(config: Config) -> FastAPI:
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

    return app
