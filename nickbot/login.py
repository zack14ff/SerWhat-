"""Один раз войти в Telegram-аккаунт для ТОЧНОЙ проверки ников.

    python login.py

Нужны TG_API_ID и TG_API_HASH в .env — их выдают на https://my.telegram.org
(API development tools). Скрипт спросит телефон и код из Telegram и сохранит
сессию в checker.session. Этот файл — доступ к аккаунту: никому его не давайте.

Лучше использовать отдельный (не основной) аккаунт: Telegram ограничивает
частоту проверок, а бот делает их от имени этого аккаунта.
"""

import asyncio

from telethon import TelegramClient

from nickbot.config import SESSION_PATH, load_config


async def main() -> None:
    config = load_config(require_token=False)
    if not config.precise_configured:
        raise SystemExit("Заполните TG_API_ID и TG_API_HASH в .env (https://my.telegram.org)")
    client = TelegramClient(str(SESSION_PATH.with_suffix("")), config.tg_api_id, config.tg_api_hash)
    await client.start()  # спросит телефон, код и пароль 2FA, если он есть
    me = await client.get_me()
    print(f"✅ Вошли как {me.first_name} (@{me.username}). Сессия: {SESSION_PATH.name}")
    print("Теперь запустите бота: python bot.py")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
