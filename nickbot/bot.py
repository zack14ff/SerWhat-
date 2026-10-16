"""NickForge — Telegram-бот для подбора ников.

Запуск:  python bot.py   (токен берётся из .env или переменной BOT_TOKEN)
"""

import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from nickbot.config import load_config
from nickbot.handlers import router
from nickbot.profile import COMMANDS


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    async with aiohttp.ClientSession() as http:
        dp["http"] = http
        dp["check_enabled"] = config.check_availability
        # Меню команд обновляем при каждом запуске — это дёшево и всегда актуально
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS["en"]])
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS["ru"]],
                                  language_code="ru")
        me = await bot.me()
        logging.info("Бот @%s запущен", me.username)
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
