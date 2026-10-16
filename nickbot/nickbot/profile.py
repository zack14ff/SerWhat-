"""Всё, что заполняется у бота в @BotFather, в одном месте.

Используется скриптом botfather/setup_profile.py (ставит это через Bot API)
и продублировано в botfather/BOTFATHER.md для ручного копирования.
"""

BOT_NAME = "NickForge · Подбор ников"
BOT_USERNAME = "NickForgeBot"
BOT_USERNAME_ALTERNATIVES = [
    "NickForgeRuBot", "NickSmithBot", "NikPodborBot", "PodborNikaBot",
    "NickIdeasBot", "UsernameForgeBot", "TgNickHelperBot",
]
INLINE_PLACEHOLDER = "слово, имя или фраза…"

# Только для справки — Telegram ограничивает длину полей
LIMITS = {"name": 64, "short_description": 120, "description": 512}

SHORT_DESCRIPTION = {
    "ru": "Подберу удобный и свободный ник для Telegram, игр и соцсетей по любому слову. "
          "Напиши слово — получи идеи ✨",
    "en": "I find handy, available usernames for Telegram, games and socials from any word. "
          "Send a word — get ideas ✨",
}

DESCRIPTION = {
    "ru": (
        "🔨 NickForge — кузница ников.\n\n"
        "Отправь слово, имя или фразу (можно по-русски), и я:\n"
        "• подберу удобные и похожие username для Telegram;\n"
        "• проверю, какие из них, скорее всего, свободны 🟢;\n"
        "• сделаю стильные ники со шрифтами и украшениями для игр и профиля;\n"
        "• придумаю случайный ник, если идей нет.\n\n"
        "Работаю и в любом чате: набери @NickForgeBot слово.\n\n"
        "Жми «Старт» 👇"
    ),
    "en": (
        "🔨 NickForge — the username forge.\n\n"
        "Send a word, name or phrase and I will:\n"
        "• suggest handy and similar Telegram usernames;\n"
        "• check which ones are most likely available 🟢;\n"
        "• make stylish nicknames with fancy fonts for games and profiles;\n"
        "• generate a random nickname if you have no ideas.\n\n"
        "Works in any chat too: type @NickForgeBot word.\n\n"
        "Tap Start 👇"
    ),
}

COMMANDS = {
    "ru": [
        ("start", "Начать и узнать, что я умею"),
        ("nick", "Подобрать username: /nick слово"),
        ("style", "Стильный ник со шрифтами: /style текст"),
        ("check", "Проверить, свободен ли ник: /check имя"),
        ("random", "Случайные ники, если нет идей"),
        ("settings", "Длина, цифры и подчёркивания"),
        ("help", "Помощь и правила username"),
    ],
    "en": [
        ("start", "Start and see what I can do"),
        ("nick", "Suggest usernames: /nick word"),
        ("style", "Fancy nickname: /style text"),
        ("check", "Check if a username is free: /check name"),
        ("random", "Random nicknames"),
        ("settings", "Length, digits and underscores"),
        ("help", "Help and username rules"),
    ],
}
