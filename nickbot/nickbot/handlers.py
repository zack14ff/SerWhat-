from __future__ import annotations

import hashlib
import logging
import time
from html import escape

import anthropic
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import texts
from .ai import AIUnavailable, NickAI, free_first
from .checker import AVAILABLE, STATUS_ICON, Checker, CheckResult, Status
from .username import MAX_PER_MESSAGE, parse_usernames

log = logging.getLogger(__name__)
router = Router()

# Состояние в памяти: базы не нужно, после перезапуска ИИ-режим просто выключится
_ai_mode: set[int] = set()
_ai_busy: set[int] = set()
_last_unavailable: dict[int, list[str]] = {}

AI_OFF_WORDS = {"off", "stop", "выкл", "выключить", "стоп"}


# --------------------------------------------------------------------------- #
# Форматирование
# --------------------------------------------------------------------------- #

def describe(r: CheckResult) -> str:
    if r.status is Status.FREE:
        return "свободен"
    if r.status is Status.LIKELY_FREE:
        return "не найден — возможно свободен, Telegram не подтвердил"
    if r.status is Status.INVALID:
        return f"не по формату: {escape(r.reason)}"
    if r.status is Status.FRAGMENT:
        return "на Fragment — только покупка"
    if r.status is Status.TAKEN:
        return "занят"
    return "не удалось проверить"


def format_line(r: CheckResult) -> str:
    shown = escape(r.username) if r.status is Status.INVALID else f"@{r.username}"
    return f"{STATUS_ICON[r.status]} <code>{shown}</code> — {describe(r)}"


def format_check(results: list[CheckResult]) -> str:
    lines = [format_line(r) for r in results]
    free = sum(r.status is Status.FREE for r in results)
    likely = sum(r.status is Status.LIKELY_FREE for r in results)
    if len(results) > 1:
        summary = f"Свободно: <b>{free}</b> из {len(results)}"
        if likely:
            summary += f" · возможно свободно: <b>{likely}</b>"
        lines += ["", summary]
    if likely:
        lines += ["", texts.LIKELY_FREE_NOTE]
    return "\n".join(lines)


def format_ai_reply(text: str, checked: list[CheckResult]) -> str:
    parts = [f"🤖 {escape(text[:2500])}" if text else "🤖 Готово."]
    if checked:
        ordered = free_first(checked)
        free = [r for r in ordered if r.status in AVAILABLE]
        busy = [r for r in ordered if r.status in (Status.TAKEN, Status.FRAGMENT)]
        other = [r for r in ordered if r.status in (Status.INVALID, Status.UNKNOWN)]
        parts.append(f"\n<b>ИИ проверил ников: {len(checked)}</b>")
        parts += [format_line(r) for r in free[:30]]
        if any(r.status is Status.LIKELY_FREE for r in free):
            parts.append(texts.LIKELY_FREE_NOTE)
        if busy:
            names = ", ".join(f"@{r.username}" for r in busy[:40])
            parts.append(f"🔴 заняты / на Fragment ({len(busy)}): {escape(names)}")
        if other:
            names = ", ".join(r.username for r in other[:20])
            parts.append(f"⚪ не подошли ({len(other)}): {escape(names)}")
    return "\n".join(parts)[:4000]


def check_keyboard(user_id: int, results: list[CheckResult],
                   ai: NickAI | None) -> InlineKeyboardMarkup | None:
    unavailable = [r.username for r in results if r.status not in AVAILABLE | {Status.UNKNOWN}]
    if not ai or not unavailable:
        return None
    _last_unavailable[user_id] = unavailable[:5]
    kb = InlineKeyboardBuilder()
    kb.button(text="🤖 Найти похожие свободные (ИИ)", callback_data="ai:similar")
    return kb.as_markup()


def ai_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Ещё варианты", callback_data="ai:more")
    kb.button(text="🆕 Новый поиск", callback_data="ai:new")
    kb.button(text="⏹ Выключить ИИ", callback_data="ai:off")
    kb.adjust(2, 1)
    return kb.as_markup()


async def safe_edit(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise


# --------------------------------------------------------------------------- #
# Проверка ников
# --------------------------------------------------------------------------- #

async def run_check(message: Message, user_id: int, text: str,
                    checker: Checker, ai: NickAI | None) -> None:
    names = parse_usernames(text)
    if not names:
        await message.answer(texts.NOTHING_TO_CHECK)
        return
    status = await message.answer(texts.CHECKING)
    results = await checker.check_many(names)
    await safe_edit(status, format_check(results), check_keyboard(user_id, results, ai))


# --------------------------------------------------------------------------- #
# ИИ-подбор
# --------------------------------------------------------------------------- #

async def run_ai(message: Message, user_id: int, prompt: str, ai: NickAI) -> None:
    if user_id in _ai_busy:
        await message.answer(texts.AI_BUSY)
        return
    _ai_busy.add(user_id)
    try:
        status = await message.answer(texts.AI_THINKING)
        last_edit = 0.0

        async def on_progress(checked: list[CheckResult]) -> None:
            nonlocal last_edit
            if time.monotonic() - last_edit < 1.5:
                return
            last_edit = time.monotonic()
            free = sum(r.status in AVAILABLE for r in checked)
            last = "\n".join(format_line(r) for r in checked[-8:])
            try:
                await safe_edit(status, texts.AI_PROGRESS.format(n=len(checked), free=free, last=last))
            except TelegramBadRequest:
                pass

        try:
            reply = await ai.ask(user_id, prompt, on_progress)
        except AIUnavailable as e:
            await safe_edit(status, f"🤖 {escape(str(e))}")
            return
        except anthropic.APIError as e:
            log.warning("Claude API: %s", e)
            await safe_edit(status, texts.AI_ERROR.format(error=escape(type(e).__name__)))
            return
        await safe_edit(status, format_ai_reply(reply.text, reply.checked), ai_keyboard())
    finally:
        _ai_busy.discard(user_id)


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
async def cmd_help(message: Message, checker: Checker) -> None:
    await message.answer(texts.HELP.format(
        max_names=MAX_PER_MESSAGE,
        precision=texts.PRECISE_ON if checker.tg else texts.PRECISE_OFF,
    ))


@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject,
                    checker: Checker, ai: NickAI | None) -> None:
    if not command.args:
        await message.answer(texts.ASK_CHECK)
        return
    await run_check(message, message.from_user.id, command.args, checker, ai)


@router.message(Command("ai"))
async def cmd_ai(message: Message, command: CommandObject, ai: NickAI | None) -> None:
    user_id = message.from_user.id
    if not ai:
        await message.answer(texts.AI_NOT_CONFIGURED)
        return
    args = (command.args or "").strip()
    if args.lower() in AI_OFF_WORDS:
        _ai_mode.discard(user_id)
        ai.reset(user_id)
        await message.answer(texts.AI_OFF)
        return
    if not ai.is_allowed(user_id):
        await message.answer(texts.AI_NOT_ALLOWED)
        return
    _ai_mode.add(user_id)
    if args:
        await run_ai(message, user_id, args, ai)
    else:
        await message.answer(texts.AI_ON.format(left=ai.remaining_today(user_id)))


@router.message(F.text & ~F.text.startswith("/"))
async def any_text(message: Message, checker: Checker, ai: NickAI | None) -> None:
    user_id = message.from_user.id
    if ai and user_id in _ai_mode:
        await run_ai(message, user_id, message.text, ai)
    else:
        await run_check(message, user_id, message.text, checker, ai)


@router.message()
async def other_messages(message: Message) -> None:
    await message.answer(texts.ASK_CHECK)


# --------------------------------------------------------------------------- #
# Кнопки
# --------------------------------------------------------------------------- #

@router.callback_query(F.data.startswith("ai:"))
async def cb_ai(call: CallbackQuery, ai: NickAI | None) -> None:
    user_id = call.from_user.id
    if not ai:
        await call.answer(texts.AI_NOT_CONFIGURED, show_alert=True)
        return
    if not ai.is_allowed(user_id):
        await call.answer(texts.AI_NOT_ALLOWED, show_alert=True)
        return
    action = call.data.split(":", 1)[1]
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=None)
    if action == "off":
        _ai_mode.discard(user_id)
        ai.reset(user_id)
        await call.message.answer(texts.AI_OFF)
    elif action == "new":
        ai.reset(user_id)
        _ai_mode.add(user_id)
        await call.message.answer(texts.AI_RESET)
    elif action == "more":
        _ai_mode.add(user_id)
        await run_ai(call.message, user_id, texts.AI_MORE_PROMPT, ai)
    elif action == "similar":
        names = _last_unavailable.get(user_id)
        if not names:
            await call.message.answer(texts.ASK_CHECK)
            return
        _ai_mode.add(user_id)
        ai.reset(user_id)
        prompt = texts.AI_SIMILAR_PROMPT.format(names=", ".join(f"@{n}" for n in names))
        await run_ai(call.message, user_id, prompt, ai)


# --------------------------------------------------------------------------- #
# Inline-режим: @NickForgeBot ник — проверка в любом чате
# --------------------------------------------------------------------------- #

@router.inline_query()
async def inline_query(query: InlineQuery, checker: Checker) -> None:
    names = parse_usernames(query.query)[:5]
    if not names:
        await query.answer([], cache_time=5, button=InlineQueryResultsButton(
            text="Введите ник для проверки", start_parameter="inline"))
        return
    results = []
    for r in await checker.check_many(names):
        shown = r.username if r.status is Status.INVALID else f"@{r.username}"
        verdict = f"{STATUS_ICON[r.status]} {describe(r)}"
        results.append(InlineQueryResultArticle(
            id=hashlib.md5(f"{r.username}|{r.status.value}".encode()).hexdigest(),
            title=f"{shown} — {verdict}",
            description="Нажми, чтобы отправить результат в чат",
            input_message_content=InputTextMessageContent(
                message_text=f"{shown} — {verdict}", parse_mode=None),
        ))
    await query.answer(results, cache_time=60)
