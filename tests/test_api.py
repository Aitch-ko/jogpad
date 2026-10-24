from fastapi.testclient import TestClient

from jogpad.api import create_app
from jogpad.config import Config


def client() -> TestClient:
    return TestClient(create_app(Config()))


def test_health_reports_ok() -> None:
    assert client().get("/api/health").json() == {"status": "ok"}


def test_config_endpoint_returns_active_port() -> None:
    assert client().get("/api/config").json()["server"]["port"] == 7150


def test_state_without_service_reports_first_step() -> None:
    assert client().get("/api/state").json()["step"] == 0.01


def test_swagger_ui_is_served() -> None:
    assert client().get("/docs").status_code == 200


def test_api_offers_no_write_methods() -> None:
    methods = {
        method for path in client().get("/openapi.json").json()["paths"].values() for method in path
    }
    assert methods == {"get"}
