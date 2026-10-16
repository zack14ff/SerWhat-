import pytest

from nickbot.checker import Status, parse_tme_page
from nickbot.generator import (
    Settings,
    build_pool,
    extract_words,
    is_valid_username,
    random_nicks,
    suggest,
    transliterate,
)
from nickbot.styles import stylize


def test_transliterate():
    assert transliterate("Иван Петров") == "ivan petrov"
    assert transliterate("Щука", alt=True) == "shuka"


def test_extract_words():
    assert extract_words("Shadow Hunter 2000!") == ["shadow", "hunter", "2000"]
    assert extract_words("🙂🙂") == []


@pytest.mark.parametrize("name, ok", [
    ("nickforge", True), ("nick_forge", True), ("a1234", True),
    ("nick", False), ("1nick", False), ("nick_", False), ("ni__ck", False),
    ("_nick", False), ("ник_ник", False), ("x" * 33, False),
])
def test_is_valid_username(name, ok):
    assert is_valid_username(name) is ok


@pytest.mark.parametrize("text", ["Кот", "Иван Петров", "telegram", "Shadow Hunter 2000", "123", "ё"])
def test_all_suggestions_are_valid_usernames(text):
    for s in build_pool(text):
        assert is_valid_username(s.name), s.name


def test_exact_match_comes_first():
    assert suggest("telegram")[0].name == "telegram"
    assert suggest("Иван Петров")[0].name == "ivanpetrov"


def test_settings_are_respected():
    settings = Settings(min_len=6, max_len=10, digits=False, underscore=False)
    pool = build_pool("Shadow Hunter", settings)
    assert pool
    for s in pool:
        assert 6 <= len(s.name) <= 10
        assert "_" not in s.name
        assert not any(ch.isdigit() for ch in s.name)


def test_pages_do_not_repeat():
    names = [s.name for page in range(50) for s in suggest("Котик", page=page, seed=7)]
    assert names and len(names) == len(set(names)) == len(build_pool("Котик"))


def test_random_nicks():
    nicks = random_nicks(10, seed=1)
    assert len(nicks) == 10 and all(is_valid_username(n) for n in nicks)


def test_stylize():
    variants = stylize("Котик")
    assert "꧁Котик꧂" in variants
    assert "𝗞𝗼𝘁𝗶𝗸" in variants
    assert len(variants) == len(set(variants))
    assert stylize("   ") == []


def test_parse_tme_page():
    assert parse_tme_page('<div class="tgme_page_extra">@durov</div>') is Status.TAKEN
    assert parse_tme_page('<div class="tgme_page"><div class="tgme_page_description">') is Status.FREE
    assert parse_tme_page("<html>captcha</html>") is Status.UNKNOWN
