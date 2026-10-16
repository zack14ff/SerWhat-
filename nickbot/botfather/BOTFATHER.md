# Всё для @BotFather

Готовые тексты и картинки для бота **NickForge**. Те же тексты лежат в коде —
`nickbot/profile.py`, и скрипт `setup_profile.py` может проставить большую часть сам.

| Поле в BotFather | Команда | Что вставить |
|---|---|---|
| Имя | `/newbot`, `/setname` | `NickForge · Подбор ников` |
| Username | `/newbot` | `NickForgeBot` (запасные — ниже) |
| Аватарка | `/setuserpic` | [`avatar.png`](avatar.png) |
| Описание (What can this bot do?) | `/setdescription` | текст ниже |
| Картинка описания | `/mybots` → бот → Edit Bot → Edit Description Picture | [`description.png`](description.png) |
| About (короткое описание) | `/setabouttext` | текст ниже |
| Команды | `/setcommands` | список ниже |
| Inline-режим | `/setinline` | `слово, имя или фраза…` |

<p>
  <img src="avatar.png" width="160" alt="Аватарка">
  &nbsp;
  <img src="description.png" width="285" alt="Картинка описания">
</p>

---

## 1. Создать бота

1. Открой [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Имя: `NickForge · Подбор ников`
3. Username (должен заканчиваться на `bot`): `NickForgeBot`.
   Если занят — по очереди: `NickForgeRuBot`, `NickSmithBot`, `NikPodborBot`,
   `PodborNikaBot`, `NickIdeasBot`, `UsernameForgeBot`, `TgNickHelperBot`.
   Или спроси у самого бота: `/nick nick forge bot` 😉
4. BotFather пришлёт **токен** — вставь его в `nickbot/.env`:
   ```
   BOT_TOKEN=1234567890:AAAA...
   ```

## 2. Заполнить профиль автоматически (рекомендую)

```bash
cd nickbot
python botfather/setup_profile.py
```

Скрипт через Bot API поставит имя, описание и About (ru + en), меню команд и аватарку.
Останется вручную только **inline-режим** и **картинка описания** (шаги 4 и 3.5 ниже).

## 3. …или заполнить вручную

### 3.1 `/setuserpic` — аватарка
Отправь файл [`avatar.png`](avatar.png) (640×640) **как фото**.

### 3.2 `/setdescription` — «What can this bot do?»
Показывается в пустом чате перед кнопкой «Старт» (до 512 символов):

```
🔨 NickForge — кузница ников.

Отправь слово, имя или фразу (можно по-русски), и я:
• подберу удобные и похожие username для Telegram;
• проверю, какие из них, скорее всего, свободны 🟢;
• сделаю стильные ники со шрифтами и украшениями для игр и профиля;
• придумаю случайный ник, если идей нет.

Работаю и в любом чате: набери @NickForgeBot слово.

Жми «Старт» 👇
```

### 3.3 `/setabouttext` — About
Видно в профиле бота и при пересылке ссылки (до 120 символов):

```
Подберу удобный и свободный ник для Telegram, игр и соцсетей по любому слову. Напиши слово — получи идеи ✨
```

### 3.4 `/setcommands` — меню команд
Отправь одним сообщением:

```
start - Начать и узнать, что я умею
nick - Подобрать username: /nick слово
style - Стильный ник со шрифтами: /style текст
check - Проверить, свободен ли ник: /check имя
random - Случайные ники, если нет идей
settings - Длина, цифры и подчёркивания
help - Помощь и правила username
```

### 3.5 Картинка описания
`/mybots` → выбери бота → **Edit Bot** → **Edit Description Picture** →
отправь [`description.png`](description.png) (640×360).

## 4. `/setinline` — работа в любом чате

`/setinline` → выбери бота → плейсхолдер:

```
слово, имя или фраза…
```

После этого в любом чате можно набрать `@NickForgeBot котик` и выбрать ник из списка.

## 5. Остальные настройки (по желанию)

| Команда | Значение | Зачем |
|---|---|---|
| `/setjoingroups` | Enable | можно добавить в группу и звать командами `/nick@NickForgeBot слово` |
| `/setprivacy` | Enable (по умолчанию) | в группах бот видит только команды, а не всю переписку |
| `/setinlinefeedback` | Disabled | статистика inline-выбора боту не нужна |

> Если поменяешь имя/username бота — поправь тексты в `nickbot/profile.py`
> и перезапусти `setup_profile.py`. Картинки перерисовываются командой
> `python botfather/generate_assets.py`.
