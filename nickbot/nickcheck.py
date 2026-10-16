"""nickcheck — проверка ников Telegram из командной строки.

Отдельный инструмент без бота: его запускает человек или Claude Code, чтобы
придумать ник, проверить и повторить, пока не найдётся свободный.

    python nickcheck.py xlebb crumbly @loafy t.me/durov
    python nickcheck.py --json xlebb crumbly          # машиночитаемый вывод
    python nickcheck.py --only-free a1 b2 c3          # только свободные и «возможно свободные»
    python nickcheck.py --file candidates.txt         # по одному нику в строке
    echo "xlebb crumbly" | python nickcheck.py -      # из stdin

Статусы: free (подтвердил Telegram) · likely_free (не найден на t.me и Fragment,
Telegram не подтверждал — может оказаться зарезервирован) · taken · fragment
(продаётся на Fragment) · invalid (не по формату, с причиной) · unknown.

Статус free бывает только при точной проверке через Telegram-аккаунт: нужны
TG_API_ID/TG_API_HASH в .env и один раз `python login.py`. Без неё свободные
ники получают likely_free — по публичным страницам свободный ник не отличить
от зарезервированного.

Код возврата: 0 — есть free или likely_free, 1 — нет, 2 — ошибка.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nickbot.checker import AVAILABLE, STATUS_ICON, Checker, CheckResult, Status  # noqa: E402
from nickbot.config import SESSION_PATH, load_config  # noqa: E402
from nickbot.username import parse_usernames  # noqa: E402

CACHE_PATH = ROOT / ".nickcheck-cache.json"
CACHE_TTL = 15 * 60          # секунд: повторные запуски не дёргают Telegram лишний раз
MAX_NAMES = 50

STATUS_RU = {
    Status.FREE: "свободен",
    Status.LIKELY_FREE: "возможно свободен — Telegram не подтвердил",
    Status.TAKEN: "занят",
    Status.FRAGMENT: "на Fragment — только покупка",
    Status.INVALID: "не по формату",
    Status.UNKNOWN: "не удалось проверить",
}


# --------------------------------------------------------------------------- #
# Кэш между запусками
# --------------------------------------------------------------------------- #

def load_cache() -> dict[str, dict]:
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    now = time.time()
    return {k: v for k, v in data.items() if now - v.get("ts", 0) < CACHE_TTL}


def save_cache(cache: dict[str, dict]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def from_cache(entry: dict) -> CheckResult:
    status = Status(entry["status"])
    if status is Status.FREE and not entry.get("precise"):
        status = Status.LIKELY_FREE   # запись из старой версии, где веб-проверка писала free
    return CheckResult(entry["username"], status, entry.get("reason", ""), entry.get("precise", False))


# --------------------------------------------------------------------------- #
# Проверка
# --------------------------------------------------------------------------- #

async def open_telegram(quiet: bool):
    config = load_config(require_token=False)
    if not config.precise_configured or not SESSION_PATH.exists():
        return None
    try:
        from telethon import TelegramClient
    except ImportError:
        return None
    client = TelegramClient(str(SESSION_PATH.with_suffix("")), config.tg_api_id, config.tg_api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        if not quiet:
            print("⚠️  Сессия Telegram не авторизована — выполните `python login.py`.", file=sys.stderr)
        return None
    return client


async def check(names: list[str], use_cache: bool, quiet: bool) -> tuple[list[CheckResult], bool]:
    cache = load_cache() if use_cache else {}
    todo = [n for n in names if n not in cache]
    fresh: dict[str, CheckResult] = {}
    tg = await open_telegram(quiet) if todo else None
    try:
        if todo:
            async with aiohttp.ClientSession(trust_env=True) as http:
                for r in await Checker(http, tg).check_many(todo):
                    fresh[r.username] = r
    finally:
        if tg:
            await tg.disconnect()

    now = time.time()
    for r in fresh.values():
        if r.status is not Status.UNKNOWN:
            cache[r.username] = {"username": r.username, "status": r.status.value,
                                 "reason": r.reason, "precise": r.precise, "ts": now}
    if use_cache:
        save_cache(cache)
    results = [fresh[n] if n in fresh else from_cache(cache[n]) for n in names]
    return results, tg is not None


# --------------------------------------------------------------------------- #
# Вывод
# --------------------------------------------------------------------------- #

def to_dict(r: CheckResult) -> dict:
    return {"username": r.username, "status": r.status.value,
            "reason": r.reason or STATUS_RU[r.status], "precise": r.precise}


def print_table(results: list[CheckResult], precise_mode: bool) -> None:
    width = max((len(r.username) for r in results), default=5) + 1
    for r in results:
        text = STATUS_RU[r.status]
        if r.status is Status.INVALID and r.reason:
            text += f": {r.reason}"
        elif r.status is Status.FRAGMENT and r.reason:
            text = f"на Fragment: {r.reason}"
        name = r.username if r.status is Status.INVALID else f"@{r.username}"
        print(f"{STATUS_ICON[r.status]} {name:<{width + 1}} {text}")
    free = sum(r.status is Status.FREE for r in results)
    likely = sum(r.status is Status.LIKELY_FREE for r in results)
    mode = "точная (Telegram)" if precise_mode else "по t.me и Fragment"
    print(f"\nСвободно: {free} · возможно свободно: {likely} · всего: {len(results)} · проверка: {mode}")
    if likely:
        print("🟡 Telegram не подтверждал эти ники — часть может оказаться зарезервирована.\n"
              "   Точная проверка: TG_API_ID/TG_API_HASH в nickbot/.env и `python nickbot/login.py`.")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # эмодзи в консоли Windows
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        prog="nickcheck", description="Проверка, свободны ли ники в Telegram.")
    parser.add_argument("names", nargs="*", help="ники (можно с @ или ссылкой t.me/…); «-» — читать из stdin")
    parser.add_argument("-f", "--file", help="файл с никами (через пробел, запятую или с новой строки)")
    parser.add_argument("--json", action="store_true", help="вывести JSON (удобно для скриптов и Claude Code)")
    parser.add_argument("--only-free", action="store_true", help="показать только свободные")
    parser.add_argument("--no-cache", action="store_true", help="не использовать кэш прошлых проверок")
    args = parser.parse_args()

    raw = " ".join(n for n in args.names if n != "-")
    if "-" in args.names:
        raw += " " + sys.stdin.read()
    if args.file:
        raw += " " + Path(args.file).read_text(encoding="utf-8")
    names = parse_usernames(raw, limit=MAX_NAMES)
    if not names:
        parser.print_usage(sys.stderr)
        print("nickcheck: укажите хотя бы один ник", file=sys.stderr)
        return 2

    results, precise_mode = asyncio.run(check(names, not args.no_cache, args.json))
    shown = [r for r in results if r.status in AVAILABLE] if args.only_free else results

    if args.json:
        print(json.dumps({"precise_mode": precise_mode, "results": [to_dict(r) for r in shown]},
                         ensure_ascii=False, indent=2))
    elif shown:
        print_table(shown, precise_mode)
    else:
        print("Свободных нет.")
    return 0 if any(r.status in AVAILABLE for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
