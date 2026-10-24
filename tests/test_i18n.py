from jogpad.i18n import t

VALUES = {"version": "1", "host": "h", "port": 1}


def test_german_message_is_used_when_requested() -> None:
    assert t("server.starting", "de", **VALUES).startswith("jogpad 1 lauscht")


def test_unknown_language_falls_back_to_english() -> None:
    assert t("server.starting", "xx", **VALUES).startswith("jogpad 1 listening")


def test_unknown_key_is_returned_unchanged() -> None:
    assert t("no.such.key") == "no.such.key"
