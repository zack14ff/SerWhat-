"""NickForge — Telegram-бот: проверка ников и ИИ-подбор свободных.

Запуск:  python bot.py   (настройки — в .env, см. .env.example)
"""

import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from nickbot.ai import NickAI
from nickbot.checker import Checker
from nickbot.config import SESSION_PATH, Config, load_config
from nickbot.handlers import router
from nickbot.profile import COMMANDS

log = logging.getLogger("nickbot")


async def start_telegram_client(config: Config):
    """Telegram-аккаунт для точной проверки ников (если настроен через login.py)."""
    if not config.precise_configured:
        log.info("Точная проверка выключена (нет TG_API_ID/TG_API_HASH) — проверяю по t.me и Fragment")
        return None
    if not SESSION_PATH.exists():
        log.warning("Нет файла %s — выполните `python login.py`. Пока проверяю по t.me", SESSION_PATH.name)
        return None
    from telethon import TelegramClient

    client = TelegramClient(str(SESSION_PATH.with_suffix("")), config.tg_api_id, config.tg_api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        log.warning("Сессия Telegram не авторизована — выполните `python login.py` ещё раз")
        await client.disconnect()
        return None
    log.info("Точная проверка ников через Telegram включена")
    return client


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    tg = await start_telegram_client(config)
    try:
        async with aiohttp.ClientSession(trust_env=True) as http:
            checker = Checker(http, tg)
            ai = None
            if config.ai_configured:
                ai = NickAI(config.anthropic_api_key, checker, config.ai_model, config.ai_effort,
                            config.ai_daily_limit, set(config.ai_allowed_users))
                log.info("ИИ-подбор включён (модель %s)", config.ai_model)
            else:
                log.info("ИИ-подбор выключен (нет ANTHROPIC_API_KEY)")
            dp["checker"] = checker
            dp["ai"] = ai

            # Меню команд обновляем при каждом запуске — это дёшево и всегда актуально
            await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS["en"]])
            await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS["ru"]],
                                      language_code="ru")
            me = await bot.me()
            log.info("Бот @%s запущен", me.username)
            await dp.start_polling(bot)
    finally:
        if tg:
            await tg.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
