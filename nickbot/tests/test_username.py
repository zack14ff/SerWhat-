import pytest

from nickbot.username import format_error, normalize, parse_usernames


@pytest.mark.parametrize("raw, name", [
    ("@XLebb", "xlebb"), ("t.me/xlebb", "xlebb"), ("https://t.me/xlebb?start=1", "xlebb"),
    ("telegram.me/durov/", "durov"), ("«@xlebb»,", "xlebb"),
])
def test_normalize(raw, name):
    assert normalize(raw) == name


def test_parse_usernames():
    assert parse_usernames("@xlebb, durov\nt.me/xlebb  @abc") == ["xlebb", "durov", "abc"]
    assert parse_usernames("   ") == []


@pytest.mark.parametrize("name", ["xlebb", "xleb_bread", "a1234", "x" * 32])
def test_valid(name):
    assert format_error(name) is None


@pytest.mark.parametrize("name, part", [
    ("xleb", "4-символьные"),
    ("xl", "слишком короткий"),
    ("x" * 33, "слишком длинный"),
    ("1xleb", "начинаться с буквы"),
    ("_xleb", "начинаться с буквы"),
    ("xleb_", "заканчиваться"),
    ("xl__eb", "два «_»"),
    ("хлебушек", "кириллица"),
    ("xleb-bread", "недопустимые символы: -"),
])
def test_invalid_with_reason(name, part):
    assert part in format_error(name)


def test_cyrillic_hint():
    assert "khlebushek" in format_error("хлебушек")
