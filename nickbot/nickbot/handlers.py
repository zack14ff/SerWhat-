from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from html import escape

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import texts
from .checker import STATUS_ICON, Status, check_many
from .generator import (
    CATEGORY_TITLES,
    TG_MAX_LEN,
    TG_MIN_LEN,
    Settings,
    extract_words,
    is_valid_username,
    random_nicks,
    suggest,
)
from .styles import stylize

router = Router()

PAGE_SIZE = 12
CATEGORY_ICON = {key: title.split()[0] for key, title in CATEGORY_TITLES.items()}


@dataclass
class Session:
    text: str
    page: int = 0
    seed: int = field(default_factory=lambda: random.randint(1, 10**9))
    names: list[tuple[str, str]] = field(default_factory=list)  # (ник, категория)


# Состояние хранится в памяти: боту не нужна база, а после перезапуска
# пользователь просто отправит слово ещё раз.
_sessions: dict[int, Session] = {}
_settings: dict[int, Settings] = {}


def user_settings(user_id: int) -> Settings:
    return _settings.setdefault(user_id, Settings())


# --------------------------------------------------------------------------- #
# Клавиатуры и форматирование
# --------------------------------------------------------------------------- #

def results_keyboard(can_check: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Ещё", callback_data="more")
    if can_check:
        kb.button(text="🔍 Проверить", callback_data="check")
    kb.button(text="✨ Стильные", callback_data="style")
    kb.button(text="⚙️ Настройки", callback_data="settings")
    kb.adjust(2, 2)
    return kb.as_markup()


def settings_keyboard(s: Settings) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➖", callback_data="set:min-")
    kb.button(text=f"мин: {s.min_len}", callback_data="noop")
    kb.button(text="➕", callback_data="set:min+")
    kb.button(text="➖", callback_data="set:max-")
    kb.button(text=f"макс: {s.max_len}", callback_data="noop")
    kb.button(text="➕", callback_data="set:max+")
    kb.button(text=f"Цифры {'✅' if s.digits else '❌'}", callback_data="set:digits")
    kb.button(text=f"«_» {'✅' if s.underscore else '❌'}", callback_data="set:us")
    kb.button(text="↩️ Сбросить", callback_data="set:reset")
    kb.button(text="✔️ Готово", callback_data="set:done")
    kb.adjust(3, 3, 2, 2)
    return kb.as_markup()


def settings_text(s: Settings) -> str:
    return texts.SETTINGS.format(
        min_len=s.min_len, max_len=s.max_len,
        digits="✅ можно" if s.digits else "❌ без цифр",
        underscore="✅ можно" if s.underscore else "❌ без «_»",
    )


def format_results(session: Session, statuses: dict[str, Status] | None = None) -> str:
    lines = [f"🔨 Ники для «<b>{escape(session.text[:60])}</b>» · стр. {session.page + 1}", ""]
    for name, category in session.names:
        icon = STATUS_ICON[statuses[name]] if statuses else CATEGORY_ICON[category]
        lines.append(f"{icon} <code>{name}</code>")
    lines.append("")
    if statuses:
        free = sum(st is Status.FREE for st in statuses.values())
        lines.append(f"Скорее свободно: <b>{free}</b> из {len(statuses)}")
        lines.append(texts.CHECK_HINT)
    else:
        lines.append(" · ".join(CATEGORY_TITLES.values()))
    lines.append(texts.COPY_HINT)
    return "\n".join(lines)


def format_styles(text: str) -> str:
    variants = stylize(text)
    lines = [f"✨ Стильные ники для «<b>{escape(text[:40])}</b>»", ""]
    lines += [f"<code>{escape(v)}</code>" for v in variants]
    lines += ["", texts.STYLE_HINT]
    return "\n".join(lines)


RANDOM_TITLE = "🎲 случайные"


def format_random(names: list[str], statuses: dict[str, Status] | None = None) -> str:
    lines = ["🎲 <b>Случайные ники</b>", ""]
    lines += [f"{STATUS_ICON[statuses[n]] if statuses else '•'} <code>{n}</code>" for n in names]
    lines += ["", texts.CHECK_HINT] if statuses else [""]
    lines.append(texts.COPY_HINT)
    return "\n".join(lines)


def new_random_session(user_id: int) -> Session:
    names = random_nicks(PAGE_SIZE, user_settings(user_id))
    session = Session(text=RANDOM_TITLE, names=[(n, "affix") for n in names])
    _sessions[user_id] = session
    return session


def fill_page(session: Session, settings: Settings) -> None:
    found = suggest(session.text, settings, page=session.page, page_size=PAGE_SIZE,
                    seed=session.seed)
    session.names = [(s.name, s.category) for s in found]


async def safe_edit(message: Message, text: str, markup: InlineKeyboardMarkup | None) -> None:
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:  # «message is not modified» и т.п.
        if "not modified" not in str(e):
            raise


# --------------------------------------------------------------------------- #
# Команды
# --------------------------------------------------------------------------- #

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    me = await bot.me()
    await message.answer(texts.START.format(
        name=escape(message.from_user.first_name if message.from_user else "друг"),
        bot=me.username,
    ))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


async def send_suggestions(message: Message, text: str, can_check: bool) -> None:
    if not extract_words(text):
        await message.answer(texts.NO_WORDS)
        return
    session = Session(text=text.strip())
    fill_page(session, user_settings(message.from_user.id))
    if not session.names:
        await message.answer(texts.NOTHING_FITS)
        return
    _sessions[message.from_user.id] = session
    await message.answer(format_results(session), reply_markup=results_keyboard(can_check))


@router.message(Command("nick"))
async def cmd_nick(message: Message, command: CommandObject, check_enabled: bool) -> None:
    if not command.args:
        await message.answer(texts.ASK_WORD)
        return
    await send_suggestions(message, command.args, check_enabled)


@router.message(Command("style"))
async def cmd_style(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer(texts.ASK_STYLE)
        return
    await message.answer(format_styles(command.args))


@router.message(Command("random"))
async def cmd_random(message: Message, check_enabled: bool) -> None:
    session = new_random_session(message.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Ещё", callback_data="random")
    if check_enabled:
        kb.button(text="🔍 Проверить", callback_data="check")
    await message.answer(format_random([n for n, _ in session.names]), reply_markup=kb.as_markup())


@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject,
                    http: aiohttp.ClientSession, check_enabled: bool) -> None:
    if not command.args:
        await message.answer(texts.ASK_CHECK)
        return
    raw = [w.lstrip("@").lower() for w in command.args.replace(",", " ").split()][:10]
    valid = [w for w in dict.fromkeys(raw) if is_valid_username(w)]
    invalid = [w for w in raw if w not in valid]
    lines = []
    if valid and check_enabled:
        statuses = await check_many(http, valid)
        lines += [f"{STATUS_ICON[statuses[w]]} <code>{w}</code>" for w in valid]
        lines += ["", texts.CHECK_HINT]
    elif valid:
        lines.append("Проверка занятости отключена владельцем бота.")
    if invalid:
        lines.append("")
        lines.append("❌ Не подходят под правила Telegram: " +
                     ", ".join(f"<code>{escape(w)}</code>" for w in invalid))
        lines.append("Нужно 5–32 символа: a–z, 0–9, «_», начинаться с буквы.")
    await message.answer("\n".join(lines).strip())


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    s = user_settings(message.from_user.id)
    await message.answer(settings_text(s), reply_markup=settings_keyboard(s))


@router.message(F.text & ~F.text.startswith("/"))
async def any_text(message: Message, check_enabled: bool) -> None:
    await send_suggestions(message, message.text, check_enabled)


@router.message()
async def other_messages(message: Message) -> None:
    await message.answer(texts.ASK_WORD)


# --------------------------------------------------------------------------- #
# Кнопки
# --------------------------------------------------------------------------- #

@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


@router.callback_query(F.data == "more")
async def cb_more(call: CallbackQuery, check_enabled: bool) -> None:
    session = _sessions.get(call.from_user.id)
    if not session or session.text == RANDOM_TITLE:
        await call.answer(texts.SESSION_LOST, show_alert=True)
        return
    session.page += 1
    fill_page(session, user_settings(call.from_user.id))
    if not session.names:
        session.page = 0
        session.seed = random.randint(1, 10**9)
        fill_page(session, user_settings(call.from_user.id))
        await call.answer(texts.NO_MORE + " Начинаю сначала.", show_alert=True)
    else:
        await call.answer()
    await safe_edit(call.message, format_results(session), results_keyboard(check_enabled))


@router.callback_query(F.data == "random")
async def cb_random(call: CallbackQuery) -> None:
    session = new_random_session(call.from_user.id)
    await call.answer()
    await safe_edit(call.message, format_random([n for n, _ in session.names]),
                    call.message.reply_markup)


@router.callback_query(F.data == "check")
async def cb_check(call: CallbackQuery, http: aiohttp.ClientSession, check_enabled: bool) -> None:
    session = _sessions.get(call.from_user.id)
    if not session or not session.names:
        await call.answer(texts.SESSION_LOST, show_alert=True)
        return
    if not check_enabled:
        await call.answer("Проверка отключена.", show_alert=True)
        return
    await call.answer("⏳ Проверяю…")
    statuses = await check_many(http, [n for n, _ in session.names])
    if session.text == RANDOM_TITLE:
        await safe_edit(call.message, format_random([n for n, _ in session.names], statuses),
                        call.message.reply_markup)
    else:
        await safe_edit(call.message, format_results(session, statuses),
                        results_keyboard(check_enabled))


@router.callback_query(F.data == "style")
async def cb_style(call: CallbackQuery) -> None:
    session = _sessions.get(call.from_user.id)
    if not session:
        await call.answer(texts.SESSION_LOST, show_alert=True)
        return
    await call.answer()
    await call.message.answer(format_styles(session.text))


@router.callback_query(F.data == "settings")
async def cb_settings(call: CallbackQuery) -> None:
    s = user_settings(call.from_user.id)
    await call.answer()
    await call.message.answer(settings_text(s), reply_markup=settings_keyboard(s))


@router.callback_query(F.data.startswith("set:"))
async def cb_set(call: CallbackQuery, check_enabled: bool) -> None:
    s = user_settings(call.from_user.id)
    action = call.data.split(":", 1)[1]
    if action == "min-":
        s.min_len = max(TG_MIN_LEN, s.min_len - 1)
    elif action == "min+":
        s.min_len = min(s.max_len, s.min_len + 1)
    elif action == "max-":
        s.max_len = max(s.min_len, s.max_len - 1)
    elif action == "max+":
        s.max_len = min(TG_MAX_LEN, s.max_len + 1)
    elif action == "digits":
        s.digits = not s.digits
    elif action == "us":
        s.underscore = not s.underscore
    elif action == "reset":
        _settings[call.from_user.id] = s = Settings()
    elif action == "done":
        await call.answer("Сохранено ✅")
        session = _sessions.get(call.from_user.id)
        if session and session.text != RANDOM_TITLE:
            session.page = 0
            fill_page(session, s)
            if session.names:
                await safe_edit(call.message, format_results(session), results_keyboard(check_enabled))
                return
        await safe_edit(call.message, settings_text(s) + "\n\n✅ Сохранено. Отправь слово!", None)
        return
    await call.answer()
    await safe_edit(call.message, settings_text(s), settings_keyboard(s))


# --------------------------------------------------------------------------- #
# Inline-режим: @NickForgeBot слово — в любом чате
# --------------------------------------------------------------------------- #

def _article(title: str, text: str, description: str) -> InlineQueryResultArticle:
    uid = hashlib.md5(f"{title}|{text}".encode()).hexdigest()
    return InlineQueryResultArticle(
        id=uid, title=title, description=description,
        input_message_content=InputTextMessageContent(message_text=text, parse_mode=None),
    )


@router.inline_query()
async def inline_query(query: InlineQuery) -> None:
    text = query.query.strip()
    settings = user_settings(query.from_user.id)
    results: list[InlineQueryResultArticle] = []
    if text and extract_words(text):
        for s in suggest(text, settings, page_size=30):
            results.append(_article(f"@{s.name}", s.name, CATEGORY_TITLES[s.category]))
        for v in stylize(text)[:15]:
            results.append(_article(v, v, "✨ Стильный ник"))
    else:
        for n in random_nicks(20, settings):
            results.append(_article(f"@{n}", n, "🎲 Случайный ник — допиши слово для подбора"))
    await query.answer(results[:50], cache_time=30, is_personal=True)
