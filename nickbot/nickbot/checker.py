"""Примерная проверка, занят ли username в Telegram.

Bot API не умеет напрямую проверять свободность username, поэтому смотрим
публичную страницу https://t.me/<username>: у существующего аккаунта, канала
или бота там есть строка с @ником/подписчиками (tgme_page_extra) или аватарка.

Ограничения: ники, проданные/зарезервированные на Fragment, а также недавно
освобождённые могут выглядеть «свободными». Окончательный ответ даёт только
сам Telegram при попытке занять ник.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum

import aiohttp

CACHE_TTL = 15 * 60
_cache: dict[str, tuple["Status", float]] = {}
_semaphore = asyncio.Semaphore(5)


class Status(str, Enum):
    FREE = "free"
    TAKEN = "taken"
    UNKNOWN = "unknown"


STATUS_ICON = {Status.FREE: "🟢", Status.TAKEN: "🔴", Status.UNKNOWN: "⚪"}


def parse_tme_page(html: str) -> Status:
    # У существующих аккаунтов, ботов, каналов и групп есть строка с @ником или
    # числом подписчиков (tgme_page_extra) и/или аватарка.
    if "tgme_page_extra" in html or "tgme_page_photo_image" in html:
        return Status.TAKEN
    if "tgme_page" in html:
        return Status.FREE
    return Status.UNKNOWN


async def check_username(session: aiohttp.ClientSession, username: str) -> Status:
    username = username.lower().lstrip("@")
    cached = _cache.get(username)
    if cached and time.monotonic() - cached[1] < CACHE_TTL:
        return cached[0]
    async with _semaphore:
        try:
            async with session.get(
                f"https://t.me/{username}",
                timeout=aiohttp.ClientTimeout(total=8),
                headers={"User-Agent": "Mozilla/5.0 (NickForgeBot username checker)"},
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return Status.UNKNOWN
                status = parse_tme_page(await resp.text())
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return Status.UNKNOWN
    _cache[username] = (status, time.monotonic())
    return status


async def check_many(session: aiohttp.ClientSession, usernames: list[str]) -> dict[str, Status]:
    results = await asyncio.gather(*(check_username(session, u) for u in usernames))
    return dict(zip(usernames, results))
