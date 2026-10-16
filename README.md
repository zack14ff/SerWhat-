# SerWhat?

Репозиторий с двумя проектами — каждый в своей папке:

| Папка | Что это |
|---|---|
| [`nickbot/`](nickbot) | 🔨 **NickForge** — Telegram-бот, подбирает удобные и похожие ники на слово или текст, проверяет занятость, делает стильные ники. Аватарка и все тексты для @BotFather — в [`nickbot/botfather`](nickbot/botfather/BOTFATHER.md). |
| [`serwhat/`](serwhat) | 🖥️ **SerWhat** — менеджер локальных серверов (Minecraft и др.) на Python + Eel. Стабильная версия — V1.2.0. |

## Быстрый старт бота

```bash
cd nickbot
pip install -r requirements.txt
cp .env.example .env    # вставь токен от @BotFather
python botfather/setup_profile.py
python bot.py
```

Подробнее — в [nickbot/README.md](nickbot/README.md).
