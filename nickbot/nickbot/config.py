"""Настройки из переменных окружения или файла .env рядом с bot.py."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION_PATH = ROOT / "checker.session"   # создаётся командой `python login.py`


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
    # точная проверка через Telegram-аккаунт (необязательно)
    tg_api_id: int | None
    tg_api_hash: str
    # ИИ-подбор через Claude (необязательно)
    anthropic_api_key: str
    ai_model: str
    ai_effort: str
    ai_daily_limit: int
    ai_allowed_users: frozenset[int]

    @property
    def precise_configured(self) -> bool:
        return bool(self.tg_api_id and self.tg_api_hash)

    @property
    def ai_configured(self) -> bool:
        return bool(self.anthropic_api_key)


def load_config(require_token: bool = True) -> Config:
    _load_dotenv(ROOT / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    if require_token and not token:
        raise SystemExit(
            "Не найден BOT_TOKEN. Скопируйте .env.example в .env и вставьте токен от @BotFather."
        )
    api_id = os.getenv("TG_API_ID", "").strip()
    allowed = {int(x) for x in os.getenv("AI_ALLOWED_USERS", "").replace(" ", "").split(",") if x}
    return Config(
        bot_token=token,
        tg_api_id=int(api_id) if api_id.isdigit() else None,
        tg_api_hash=os.getenv("TG_API_HASH", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        ai_model=os.getenv("AI_MODEL", "claude-opus-5-5").strip(),
        ai_effort=os.getenv("AI_EFFORT", "medium").strip(),
        ai_daily_limit=int(os.getenv("AI_DAILY_LIMIT", "20")),
        ai_allowed_users=frozenset(allowed),
    )
