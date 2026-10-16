import json
import sys

import pytest

import nickcheck
from test_checker import TME_EMPTY, TME_TAKEN, FakeWebChecker

PAGES = {
    "https://t.me/xlebb": (200, "https://t.me/xlebb", TME_TAKEN),
    "https://t.me/crumbly": (200, "https://t.me/crumbly", TME_EMPTY),
}


@pytest.fixture
def cli(monkeypatch, tmp_path, capsys):
    created = []

    def fake_checker(http, tg=None):
        checker = FakeWebChecker(PAGES, tg=tg)
        created.append(checker)
        return checker

    monkeypatch.setattr(nickcheck, "Checker", fake_checker)
    monkeypatch.setattr(nickcheck, "CACHE_PATH", tmp_path / "cache.json")

    async def no_telegram(quiet):
        return None

    monkeypatch.setattr(nickcheck, "open_telegram", no_telegram)

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["nickcheck", *args])
        code = nickcheck.main()
        return code, capsys.readouterr().out

    run.created = created
    return run


def test_json_output(cli):
    code, out = cli("--json", "@xlebb", "crumbly", "xleb_")
    data = json.loads(out)
    assert code == 0
    assert data["precise_mode"] is False
    assert [(r["username"], r["status"]) for r in data["results"]] == [
        ("xlebb", "taken"), ("crumbly", "likely_free"), ("xleb_", "invalid")]
    assert "заканчиваться" in data["results"][2]["reason"]


def test_only_free_and_exit_code(cli):
    code, out = cli("--json", "--only-free", "xlebb")
    assert code == 1 and json.loads(out)["results"] == []
    code, out = cli("--only-free", "xlebb", "crumbly")
    assert code == 0 and "@crumbly" in out and "@xlebb" not in out


def test_table_output(cli):
    _, out = cli("xlebb", "t.me/crumbly")
    assert "🔴 @xlebb" in out and "🟡 @crumbly" in out
    assert "Свободно: 0 · возможно свободно: 1 · всего: 2" in out
    assert "login.py" in out  # подсказка, как включить точную проверку


def test_cache_between_runs(cli):
    cli("--json", "xlebb")
    cli("--json", "xlebb")
    assert len(cli.created) == 1  # второй запуск взял результат из кэша


def test_no_names(cli):
    code, _ = cli()
    assert code == 2


def test_old_cache_free_becomes_likely_free(cli, tmp_path):
    (tmp_path / "cache.json").write_text(json.dumps({"kvasik": {
        "username": "kvasik", "status": "free", "reason": "", "precise": False,
        "ts": nickcheck.time.time()}}), encoding="utf-8")
    _, out = cli("--json", "kvasik")
    assert json.loads(out)["results"][0]["status"] == "likely_free"
