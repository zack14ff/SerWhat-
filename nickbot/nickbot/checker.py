"""Проверка, занят ли username в Telegram.

Два способа:

1. **Точный** — через Telegram-аккаунт (MTProto, метод account.checkUsername,
   тот же, что срабатывает при вводе ника в настройках Telegram). Отличает
   «свободен», «занят», «продаётся на Fragment» и «запрещён». Включается, если
   заданы TG_API_ID / TG_API_HASH и выполнен вход через `python login.py`.

2. **Приблизительный** — по публичным страницам t.me/<ник> и fragment.com.
   Работает без аккаунта, но зарезервированные/скрытые ники может принять за
   свободные. Используется, если точный способ не настроен или упёрся в лимит.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import aiohttp

from .username import format_error

if TYPE_CHECKING:
    from telethon import TelegramClient

log = logging.getLogger(__name__)

CACHE_TTL = 10 * 60
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NickForgeBot/2.0; username checker)"}


class Status(str, Enum):
    FREE = "free"
    TAKEN = "taken"
    FRAGMENT = "fragment"
    INVALID = "invalid"
    UNKNOWN = "unknown"


STATUS_ICON = {
    Status.FREE: "🟢", Status.TAKEN: "🔴", Status.FRAGMENT: "💎",
    Status.INVALID: "❌", Status.UNKNOWN: "⚪",
}
STATUS_TEXT = {
    Status.FREE: "свободен",
    Status.TAKEN: "занят",
    Status.FRAGMENT: "на Fragment — только покупка",
    Status.INVALID: "не по формату",
    Status.UNKNOWN: "не удалось проверить",
}


@dataclass(frozen=True)
class CheckResult:
    username: str
    status: Status
    reason: str = ""
    precise: bool = False  # True — ответ дал сам Telegram, а не веб-страница

    def as_dict(self) -> dict:
        return {"username": self.username, "status": self.status.value,
                "reason": self.reason or STATUS_TEXT[self.status]}


# --------------------------------------------------------------------------- #
# Разбор веб-страниц
# --------------------------------------------------------------------------- #

def parse_tme_page(html: str) -> Status:
    """У существующих аккаунтов, ботов, каналов и групп на t.me есть строка
    с @ником/числом подписчиков (tgme_page_extra) и/или аватарка."""
    if "tgme_page_extra" in html or "tgme_page_photo_image" in html:
        return Status.TAKEN
    if "tgme_page" in html:
        return Status.FREE
    return Status.UNKNOWN


def parse_fragment_page(html: str) -> Status | None:
    """Статус ника на fragment.com; None — ника на Fragment нет."""
    if "tm-status-taken" in html:
        return Status.TAKEN
    if "tm-status-avail" in html or "tm-status-unavail" in html:
        return Status.FRAGMENT
    return None


# --------------------------------------------------------------------------- #
# Проверяющий
# --------------------------------------------------------------------------- #

class Checker:
    def __init__(self, http: aiohttp.ClientSession, tg: "TelegramClient | None" = None) -> None:
        self.http = http
        self.tg = tg
        self._cache: dict[str, tuple[CheckResult, float]] = {}
        self._web_limit = asyncio.Semaphore(5)
        self._tg_lock = asyncio.Lock()          # MTProto-запросы по одному, чтобы не ловить флуд
        self._tg_flood_until = 0.0

    @property
    def precise_available(self) -> bool:
        return self.tg is not None and time.monotonic() >= self._tg_flood_until

    async def check(self, raw: str) -> CheckResult:
        name = raw.strip().lstrip("@").lower()
        error = format_error(name)
        if error:
            return CheckResult(name, Status.INVALID, error, precise=True)

        cached = self._cache.get(name)
        if cached and time.monotonic() - cached[1] < CACHE_TTL:
            return cached[0]

        result = None
        if self.precise_available:
            result = await self._check_mtproto(name)
        if result is None:
            result = await self._check_web(name)
        if result.status is not Status.UNKNOWN:
            self._cache[name] = (result, time.monotonic())
        return result

    async def check_many(self, names: list[str]) -> list[CheckResult]:
        return list(await asyncio.gather(*(self.check(n) for n in names)))

    # -- точная проверка через аккаунт ------------------------------------- #

    async def _check_mtproto(self, name: str) -> CheckResult | None:
        from telethon import errors
        from telethon.tl.functions.account import CheckUsernameRequest

        async with self._tg_lock:
            if not self.precise_available:
                return None
            try:
                free = await self.tg(CheckUsernameRequest(username=name))
            except errors.UsernameOccupiedError:
                free = False
            except errors.UsernamePurchaseAvailableError:
                return CheckResult(name, Status.FRAGMENT, "продаётся на Fragment", precise=True)
            except errors.UsernameInvalidError:
                return CheckResult(name, Status.INVALID,
                                   "Telegram не разрешает этот ник (зарезервирован или запрещён)",
                                   precise=True)
            except errors.FloodWaitError as e:
                self._tg_flood_until = time.monotonic() + e.seconds
                log.warning("checkUsername: лимит Telegram на %s c, перехожу на веб-проверку", e.seconds)
                return None
            except Exception:  # сеть, разлогин и т.п. — не роняем бота, проверим по вебу
                log.exception("checkUsername упал для %s", name)
                return None
        if free:
            return CheckResult(name, Status.FREE, precise=True)
        return CheckResult(name, Status.TAKEN, precise=True)

    # -- приблизительная проверка по вебу ---------------------------------- #

    async def _get(self, url: str) -> tuple[int, str, str]:
        async with self._web_limit:
            async with self.http.get(url, headers=_HEADERS, allow_redirects=True,
                                     timeout=aiohttp.ClientTimeout(total=8)) as resp:
                return resp.status, str(resp.url), await resp.text()

    async def _check_web(self, name: str) -> CheckResult:
        try:
            status_code, _, html = await self._get(f"https://t.me/{name}")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return CheckResult(name, Status.UNKNOWN)
        tme = parse_tme_page(html) if status_code == 200 else Status.UNKNOWN
        if tme is Status.TAKEN:
            return CheckResult(name, Status.TAKEN)

        # Ника нет на t.me — но он может быть продан/выставлен на Fragment
        try:
            status_code, final_url, html = await self._get(f"https://fragment.com/username/{name}")
            if status_code == 200 and f"/username/{name}" in final_url:
                fragment = parse_fragment_page(html)
                if fragment is Status.FRAGMENT:
                    return CheckResult(name, Status.FRAGMENT, "продаётся или продан на Fragment")
                if fragment is Status.TAKEN:
                    return CheckResult(name, Status.TAKEN)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass

        if tme is Status.FREE:
            return CheckResult(name, Status.FREE, "скорее всего свободен (проверка по t.me)")
        return CheckResult(name, Status.UNKNOWN)
