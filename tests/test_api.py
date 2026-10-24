from fastapi.testclient import TestClient

from jogpad.api import create_app, describe_event, describe_pad
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


def test_numpad_six_shows_x_plus() -> None:
    assert client().get("/api/pad").json()["actions"]["6"] == {"press": "x_plus"}


def test_unknown_layout_is_not_found() -> None:
    assert client().get("/api/layouts/nope").status_code == 404


def test_messages_are_in_the_configured_language() -> None:
    app = create_app(Config.model_validate({"server": {"language": "de"}}))
    assert TestClient(app).get("/api/messages").json()["ui.step"] == "Schritt"


def test_messages_contain_only_page_texts() -> None:
    assert all(key.startswith("ui.") for key in client().get("/api/messages").json())


def test_web_page_is_served_at_root() -> None:
    assert "<svg" in client().get("/").text


def test_event_names_control_and_action() -> None:
    event = describe_event(Config(), 77, 1)
    assert (event.control, event.action, event.pressed) == ("6", "x_plus", True)


def test_event_of_unknown_key_has_no_control() -> None:
    assert describe_event(Config(), 30, 1).control is None


def test_without_layout_pad_has_none() -> None:
    config = Config.model_validate({"input": {"layout": "none"}})
    assert describe_pad(config).layout is None
