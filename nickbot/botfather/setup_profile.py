"""Заполняет профиль бота через Bot API — всё, что можно без @BotFather:
имя, описание («What can this bot do?»), короткое описание («About»),
меню команд (ru + en) и аватарку.

    python botfather/setup_profile.py

Username, inline-режим и картинку описания Telegram даёт менять только
в @BotFather — см. BOTFATHER.md.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from aiogram import Bot  # noqa: E402
from aiogram.exceptions import TelegramAPIError  # noqa: E402
from aiogram.types import BotCommand, FSInputFile, InputProfilePhotoStatic  # noqa: E402

from nickbot.config import load_config  # noqa: E402
from nickbot.profile import BOT_NAME, COMMANDS, DESCRIPTION, SHORT_DESCRIPTION  # noqa: E402


async def step(title: str, coro) -> None:
    try:
        await coro
        print(f"✅ {title}")
    except TelegramAPIError as e:
        print(f"⚠️  {title}: {e}")


async def main() -> None:
    bot = Bot(load_config().bot_token)
    try:
        me = await bot.me()
        print(f"Настраиваю @{me.username}…\n")
        await step("Имя", bot.set_my_name(name=BOT_NAME))
        for lang in ("en", "ru"):
            code = None if lang == "en" else lang  # en — по умолчанию для всех языков
            await step(f"Описание [{lang}]",
                       bot.set_my_description(description=DESCRIPTION[lang], language_code=code))
            await step(f"Короткое описание [{lang}]",
                       bot.set_my_short_description(short_description=SHORT_DESCRIPTION[lang],
                                                    language_code=code))
            await step(f"Команды [{lang}]", bot.set_my_commands(
                [BotCommand(command=c, description=d) for c, d in COMMANDS[lang]],
                language_code=code,
            ))
        avatar = HERE / "avatar.png"
        await step("Аватарка", bot.set_my_profile_photo(
            photo=InputProfilePhotoStatic(photo=FSInputFile(avatar))))
        print("\nОсталось вручную в @BotFather: inline-режим и картинка описания — см. BOTFATHER.md")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
