"""Настройки из переменных окружения или файла .env рядом с bot.py."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Config:
    bot_token: str
    check_availability: bool


def load_config() -> Config:
    _load_dotenv(ROOT / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "Не найден BOT_TOKEN. Скопируйте .env.example в .env и вставьте токен от @BotFather."
        )
    return Config(
        bot_token=token,
        check_availability=os.getenv("CHECK_AVAILABILITY", "1") not in ("0", "false", "no"),
    )
