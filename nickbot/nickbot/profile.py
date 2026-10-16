"""Всё, что заполняется у бота в @BotFather, в одном месте.

Используется скриптом botfather/setup_profile.py (ставит это через Bot API)
и продублировано в botfather/BOTFATHER.md для ручного копирования.
"""

BOT_NAME = "NickForge · Проверка ников"
BOT_USERNAME = "NickForgeBot"
BOT_USERNAME_ALTERNATIVES = [
    "NickForgeRuBot", "NickCheckRuBot", "FreeNickCheckBot", "NikCheckBot",
    "UsernameCheckRuBot", "SvobodenLiNikBot", "TgNickCheckBot",
]
INLINE_PLACEHOLDER = "ник для проверки…"

# Только для справки — Telegram ограничивает длину полей
LIMITS = {"name": 64, "short_description": 120, "description": 512}

SHORT_DESCRIPTION = {
    "ru": "Проверю, свободен ли ник в Telegram, и объясню, если он не по формату. "
          "А ИИ найдёт свободный и нешаблонный 🤖",
    "en": "Checks if a Telegram username is free or invalid — and an AI finds "
          "a free, non-template one for you 🤖",
}

DESCRIPTION = {
    "ru": (
        "🔎 NickForge — проверка ников в Telegram.\n\n"
        "Отправь ник (например @xlebb) — я скажу:\n"
        "🟢 свободен · 🔴 занят · 💎 продаётся на Fragment · ❌ не по формату и почему.\n"
        "Можно проверить сразу несколько.\n\n"
        "🤖 ИИ-подбор (/ai): опиши, какой ник хочешь, — ИИ придумает "
        "нешаблонные варианты, сам проверит их и покажет только свободные.\n\n"
        "Работаю в любом чате: @NickForgeBot ник\n\n"
        "Жми «Старт» 👇"
    ),
    "en": (
        "🔎 NickForge — Telegram username checker.\n\n"
        "Send a username (e.g. @xlebb) and I'll tell you:\n"
        "🟢 free · 🔴 taken · 💎 on Fragment · ❌ invalid format and why.\n"
        "You can check several at once.\n\n"
        "🤖 AI search (/ai): describe the name you want — the AI comes up with "
        "non-template ideas, checks them and shows only the free ones.\n\n"
        "Works in any chat: @NickForgeBot name\n\n"
        "Tap Start 👇"
    ),
}

COMMANDS = {
    "ru": [
        ("start", "Начать и узнать, что я умею"),
        ("check", "Проверить ники: /check xlebb durov"),
        ("ai", "ИИ-подбор свободного ника (вкл/выкл)"),
        ("help", "Статусы, правила username и помощь"),
    ],
    "en": [
        ("start", "Start and see what I can do"),
        ("check", "Check usernames: /check xlebb durov"),
        ("ai", "AI search for a free username (on/off)"),
        ("help", "Statuses, username rules and help"),
    ],
}
