import ipaddress
from pathlib import Path

from fastapi.testclient import TestClient

from jogpad.api import create_app, describe_event, describe_pad, panel_aspect_ratio
from jogpad.config import Config
from jogpad.core import BackendError
from jogpad.moonraker import IPNetwork, Moonraker


def client() -> TestClient:
    return TestClient(create_app(Config()))


def test_health_reports_ok() -> None:
    assert client().get("/api/health").json() == {"status": "ok"}


def test_config_endpoint_returns_active_port() -> None:
    assert client().get("/api/config").json()["server"]["port"] == 7150


def test_state_without_service_reports_first_step() -> None:
    assert client().get("/api/state").json()["step"] == 0.01


def test_state_without_service_reports_jogpad_on() -> None:
    assert client().get("/api/state").json()["switched_on"] is True


def test_swagger_ui_is_served() -> None:
    assert client().get("/docs").status_code == 200


def test_only_learning_and_saving_config_can_write() -> None:
    paths = client().get("/openapi.json").json()["paths"]
    writes = {path for path, methods in paths.items() if set(methods) - {"get"}}
    assert writes == {
        "/api/learn",
        "/api/keys/{action}",
        "/api/invert",
        "/api/panel",
        "/api/switch",
    }


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


LOCAL = ("127.0.0.1", 50000)
REMOTE = ("192.168.1.20", 50000)


class FakeMoonraker(Moonraker):
    """Moonraker at the network boundary: trusts 192.168.1.0/24, keeps cameras in memory."""

    def __init__(self, reachable: bool = True) -> None:
        super().__init__("http://moonraker")
        self.reachable = reachable
        self.camera: tuple[str, str] | None = None
        self.switched_on: bool | None = None

    def trusted_networks(self) -> list[IPNetwork]:
        self._check()
        return [ipaddress.ip_network("192.168.1.0/24")]

    def set_switch(self, on: bool) -> None:
        self._check()
        self.switched_on = on

    def panel_url(self) -> str | None:
        self._check()
        return self.camera[0] if self.camera else None

    def add_panel(self, url: str, aspect_ratio: str) -> None:
        self._check()
        self.camera = (url, aspect_ratio)

    def remove_panel(self) -> None:
        self._check()
        self.camera = None

    def _check(self) -> None:
        if not self.reachable:
            raise BackendError("connection refused")


def writer(
    tmp_path: Path,
    config: Config | None = None,
    client_host: tuple[str, int] = LOCAL,
    moonraker: Moonraker | None = None,
    base_url: str = "http://testserver",
) -> TestClient:
    path = tmp_path / "jogpad.toml"
    path.touch()
    app = create_app(config or Config(), config_path=path, moonraker=moonraker)
    return TestClient(app, base_url=base_url, client=client_host)


def test_assigned_key_shows_in_active_config(tmp_path: Path) -> None:
    api = writer(tmp_path)
    api.put("/api/keys/x_plus", json={"keys": ["KEY_F13"]})
    assert api.get("/api/config").json()["input"]["keys"]["x_plus"] == ["KEY_F13"]


def test_key_of_another_action_is_refused(tmp_path: Path) -> None:
    response = writer(tmp_path).put("/api/keys/home", json={"keys": ["KEY_KP6"]})
    assert response.json()["detail"] == {"conflicts": {"KEY_KP6": "x_plus"}}


def test_key_of_another_action_can_be_taken_over(tmp_path: Path) -> None:
    api = writer(tmp_path)
    api.put("/api/keys/home", json={"keys": ["KEY_KP6"], "replace": True})
    assert api.get("/api/pad").json()["actions"]["6"] == {"press": "home"}


def test_unknown_key_name_is_rejected_by_api(tmp_path: Path) -> None:
    response = writer(tmp_path).put("/api/keys/x_plus", json={"keys": ["KEY_NOPE"]})
    assert response.status_code == 422


def test_invert_is_saved(tmp_path: Path) -> None:
    api = writer(tmp_path)
    api.put("/api/invert", json={"axes": ["Y"]})
    assert api.get("/api/config").json()["jog"]["invert"] == ["Y"]


def test_changes_from_the_network_are_refused(tmp_path: Path) -> None:
    response = writer(tmp_path, client_host=REMOTE).put("/api/invert", json={"axes": ["Y"]})
    assert response.status_code == 403


def test_changes_from_a_computer_moonraker_trusts_are_saved(tmp_path: Path) -> None:
    api = writer(tmp_path, client_host=REMOTE, moonraker=FakeMoonraker())
    assert api.put("/api/invert", json={"axes": ["Y"]}).status_code == 200


def test_changes_from_a_computer_moonraker_does_not_trust_are_refused(tmp_path: Path) -> None:
    api = writer(tmp_path, client_host=("10.0.0.5", 50000), moonraker=FakeMoonraker())
    assert api.put("/api/invert", json={"axes": ["Y"]}).status_code == 403


def test_network_changes_fail_visibly_while_moonraker_is_down(tmp_path: Path) -> None:
    api = writer(tmp_path, client_host=REMOTE, moonraker=FakeMoonraker(reachable=False))
    assert api.put("/api/invert", json={"axes": ["Y"]}).status_code == 503


def test_local_changes_work_while_moonraker_is_down(tmp_path: Path) -> None:
    api = writer(tmp_path, moonraker=FakeMoonraker(reachable=False))
    assert api.put("/api/invert", json={"axes": ["Y"]}).status_code == 200


def test_network_changes_can_be_allowed(tmp_path: Path) -> None:
    config = Config.model_validate({"server": {"allow_remote_changes": True}})
    api = writer(tmp_path, config, REMOTE)
    assert api.put("/api/invert", json={"axes": ["Y"]}).status_code == 200


def test_without_config_file_nothing_is_saved() -> None:
    api = TestClient(create_app(Config()), client=LOCAL)
    assert api.put("/api/invert", json={"axes": ["Y"]}).status_code == 409


def test_learning_needs_a_running_pad() -> None:
    api = TestClient(create_app(Config()), client=LOCAL)
    assert api.post("/api/learn", json={"seconds": 10}).status_code == 409


def test_pad_name_is_in_the_configured_language() -> None:
    app = create_app(Config.model_validate({"server": {"language": "de"}}))
    assert TestClient(app).get("/api/pad").json()["layout"]["name"] == "Ziffernblock"


def test_version_links_to_the_issues() -> None:
    links = client().get("/api/version").json()["links"]
    assert links["Issues"] == "https://github.com/Aitch-ko/jogpad/issues"


def test_languages_are_named_in_their_own_language() -> None:
    names = {lang["code"]: lang["name"] for lang in client().get("/api/languages").json()}
    assert names["de"] == "Deutsch"


def test_page_language_can_differ_from_the_config() -> None:
    assert client().get("/api/messages?lang=de").json()["ui.step"] == "Schritt"


def test_pad_name_follows_the_requested_language() -> None:
    assert client().get("/api/pad?lang=de").json()["layout"]["name"] == "Ziffernblock"


def test_unknown_page_language_is_rejected() -> None:
    assert client().get("/api/messages?lang=xx").status_code == 422


PRINTER = "http://192.168.1.5:7150"


def test_added_panel_points_at_the_compact_view(tmp_path: Path) -> None:
    moonraker = FakeMoonraker()
    writer(tmp_path, moonraker=moonraker, base_url=PRINTER).put("/api/panel")
    assert moonraker.panel_url() == "http://192.168.1.5:7150/?view=panel"


def test_added_panel_is_reported(tmp_path: Path) -> None:
    api = writer(tmp_path, moonraker=FakeMoonraker(), base_url=PRINTER)
    api.put("/api/panel")
    assert api.get("/api/panel").json() == {"url": "http://192.168.1.5:7150/?view=panel"}


def test_removed_panel_is_gone(tmp_path: Path) -> None:
    api = writer(tmp_path, moonraker=FakeMoonraker(), base_url=PRINTER)
    api.put("/api/panel")
    api.delete("/api/panel")
    assert api.get("/api/panel").json() == {"url": None}


def test_panel_opened_through_a_tunnel_is_refused(tmp_path: Path) -> None:
    api = writer(tmp_path, moonraker=FakeMoonraker(), base_url="http://127.0.0.1:7150")
    assert api.put("/api/panel").status_code == 409


def test_panel_from_an_untrusted_computer_is_refused(tmp_path: Path) -> None:
    api = writer(tmp_path, client_host=("10.0.0.5", 50000), moonraker=FakeMoonraker())
    assert api.put("/api/panel", headers={"host": "192.168.1.5:7150"}).status_code == 403


def test_panel_while_moonraker_is_down_fails_visibly(tmp_path: Path) -> None:
    api = writer(tmp_path, moonraker=FakeMoonraker(reachable=False), base_url=PRINTER)
    assert api.get("/api/panel").status_code == 503


def test_panel_of_the_keypad_fits_the_pad_and_the_state_bar() -> None:
    assert panel_aspect_ratio(Config()) == "40:58"


def test_switch_turns_jogpad_off_through_moonraker(tmp_path: Path) -> None:
    moonraker = FakeMoonraker()
    writer(tmp_path, moonraker=moonraker).put("/api/switch", json={"on": False})
    assert moonraker.switched_on is False


def test_switch_from_an_untrusted_computer_is_refused(tmp_path: Path) -> None:
    api = writer(tmp_path, client_host=("10.0.0.5", 50000), moonraker=FakeMoonraker())
    assert api.put("/api/switch", json={"on": False}).status_code == 403


def test_switch_while_moonraker_is_down_fails_visibly(tmp_path: Path) -> None:
    api = writer(tmp_path, moonraker=FakeMoonraker(reachable=False))
    assert api.put("/api/switch", json={"on": True}).status_code == 503


def test_state_without_service_has_no_switch() -> None:
    assert client().get("/api/state").json()["has_switch"] is False
