import pytest

from jogpad.keys import key_name, parse_key


# Codes copied from linux/input-event-codes.h.
@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("KEY_A", 30),
        ("a", 30),
        ("KEY_M", 50),
        ("KEY_P", 25),
        ("KEY_1", 2),
        ("KEY_0", 11),
        ("KEY_F1", 59),
        ("KEY_F12", 88),
        ("KEY_F13", 183),
        ("KEY_F24", 194),
        ("KEY_KPENTER", 96),
        ("KEY_VOLUMEUP", 115),
        ("KEY_RO", 89),
        ("KEY_KPJPCOMMA", 95),
        ("77", 77),
    ],
)
def test_key_name_resolves_to_linux_code(name: str, code: int) -> None:
    assert parse_key(name) == code


def test_unknown_key_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_key("KEY_DOES_NOT_EXIST")


def test_code_without_name_is_shown_as_number() -> None:
    assert key_name(999) == "999"
