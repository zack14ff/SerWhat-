"""ИИ-подбор ников через Claude.

Claude не выдумывает статусы сам: у него есть инструмент check_usernames,
который вызывает настоящую проверку (Checker). Он предлагает осмысленные
варианты, проверяет их, отбрасывает занятые и пробует ещё — в пределах лимита
раундов и проверок. Работает только по запросу пользователя, в фоне ничего
не делает.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import anthropic

from .checker import Checker, CheckResult, Status

log = logging.getLogger(__name__)

MAX_ROUNDS = 5             # сколько раз Claude может вызвать проверку за один запрос
MAX_CHECKS = 60            # сколько ников всего можно проверить за один запрос
MAX_PER_CALL = 15
MAX_TURNS = 12             # после стольких сообщений диалог начинается заново

SYSTEM_PROMPT = """\
Ты — помощник Telegram-бота NickForge. Помогаешь человеку найти свободный username в Telegram.

Правила формата username: 5–32 символа, только латиница a–z, цифры и «_», начинается с буквы, \
не заканчивается на «_», без «__» подряд. Регистр не важен.

У тебя есть инструмент check_usernames — он по-настоящему проверяет ники в Telegram и \
возвращает статус: free (свободен — подтвердил Telegram), likely_free (не найден на t.me и \
Fragment, но Telegram не подтверждал — может оказаться зарезервирован или запрещён), \
taken (занят), fragment (продаётся на Fragment — просто так не занять), invalid (не по формату \
или запрещён), unknown (не удалось проверить). Свободным называй только free; likely_free \
называй «возможно свободен» и не выдавай за гарантированно свободный.

Как работать:
- Пойми, что человеку нужно: смысл, настроение, язык, длина, для чего ник.
- Предлагай осмысленные, читаемые и запоминающиеся варианты: игра слов, сокращения, \
ассоциации, слова из других языков, удачные сочетания. Избегай шаблонов вроде \
приписывания цифр, «x», «_official», «real», «the» — только если человек сам о них просит.
- Если ник похож на занятый, ищи близкие по звучанию или смыслу, а не по одной букве.
- Проверяй кандидатов пачками по 8–15 штук. Если свободных мало — придумай новые и \
проверь ещё раз. Обычно хватает 2–3 раундов.
- В конце ответь по-русски, коротко, простым текстом без Markdown: 3–8 лучших \
вариантов со статусом free (если их мало — добавь likely_free с пометкой «возможно»), \
каждый с @ и пояснением в несколько слов. Если подходящих \
свободных нет — честно скажи и предложи, как изменить запрос.
"""

CHECK_TOOL = {
    "name": "check_usernames",
    "description": (
        "Проверяет в Telegram, свободны ли username. Принимает до 15 ников без @. "
        "Для каждого возвращает status: free | likely_free | taken | fragment | invalid | unknown и reason."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "usernames": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ники для проверки, без @, например [\"xlebushek\", \"breadly\"]",
            },
        },
        "required": ["usernames"],
        "additionalProperties": False,
    },
    "strict": True,
}

ProgressCallback = Callable[[list[CheckResult]], Awaitable[None]]


@dataclass
class AIReply:
    text: str
    checked: list[CheckResult]
    refused: bool = False


@dataclass
class Conversation:
    messages: list = field(default_factory=list)
    turns: int = 0


class AIUnavailable(Exception):
    """ИИ не настроен, нет доступа или исчерпан лимит."""


class NickAI:
    def __init__(self, api_key: str, checker: Checker, model: str, effort: str,
                 daily_limit: int, allowed_users: set[int]) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.checker = checker
        self.model = model
        self.effort = effort
        self.daily_limit = daily_limit
        self.allowed_users = allowed_users
        self._conversations: dict[int, Conversation] = {}
        self._usage: dict[int, tuple[str, int]] = {}   # user_id → (дата, запросов)

    # -- доступ и лимиты --------------------------------------------------- #

    def is_allowed(self, user_id: int) -> bool:
        return not self.allowed_users or user_id in self.allowed_users

    def remaining_today(self, user_id: int) -> int:
        day, used = self._usage.get(user_id, ("", 0))
        if day != time.strftime("%Y-%m-%d"):
            used = 0
        return max(0, self.daily_limit - used)

    def _spend(self, user_id: int) -> None:
        today = time.strftime("%Y-%m-%d")
        day, used = self._usage.get(user_id, (today, 0))
        self._usage[user_id] = (today, (used if day == today else 0) + 1)

    def reset(self, user_id: int) -> None:
        self._conversations.pop(user_id, None)

    # -- основной цикл ----------------------------------------------------- #

    async def ask(self, user_id: int, text: str,
                  on_progress: ProgressCallback | None = None) -> AIReply:
        if not self.is_allowed(user_id):
            raise AIUnavailable("ИИ-подбор доступен только пользователям, которых добавил владелец бота.")
        if self.remaining_today(user_id) <= 0:
            raise AIUnavailable(f"Лимит ИИ-запросов на сегодня исчерпан ({self.daily_limit}). Приходи завтра!")
        self._spend(user_id)

        conv = self._conversations.get(user_id)
        if conv is None or conv.turns >= MAX_TURNS:
            conv = self._conversations[user_id] = Conversation()
        # Работаем с копией: если запрос сорвётся, история останется целой
        messages = list(conv.messages) + [{"role": "user", "content": text}]
        checked: dict[str, CheckResult] = {}
        checks_left = MAX_CHECKS

        # MAX_ROUNDS раундов с проверками + один раунд, чтобы подвести итог
        for round_no in range(MAX_ROUNDS + 2):
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=[CHECK_TOOL],
                messages=messages,
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                self.reset(user_id)
                return AIReply("ИИ отказался обрабатывать этот запрос. Попробуй сформулировать иначе.",
                               list(checked.values()), refused=True)
            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name != "check_usernames" or round_no >= MAX_ROUNDS or checks_left <= 0:
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": block.id, "is_error": True,
                        "content": "Лимит проверок на этот запрос исчерпан. Подведи итог по уже проверенным никам.",
                    })
                    continue
                names = [str(n) for n in block.input.get("usernames", [])][:min(MAX_PER_CALL, checks_left)]
                results = await self.checker.check_many(names)
                checks_left -= len(results)
                for r in results:
                    checked[r.username] = r
                if on_progress:
                    await on_progress(list(checked.values()))
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": json.dumps([r.as_dict() for r in results], ensure_ascii=False),
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            # Цикл не завершился ответом — историю не сохраняем, чтобы не оставить её «оборванной»
            self.reset(user_id)
            return AIReply(_text_of(response) or "ИИ не успел подвести итог — вот что он проверил.",
                           list(checked.values()))

        conv.messages = messages
        conv.turns += 1
        return AIReply(_text_of(response), list(checked.values()))


def _text_of(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def free_first(results: list[CheckResult]) -> list[CheckResult]:
    order = {Status.FREE: 0, Status.LIKELY_FREE: 1, Status.FRAGMENT: 2, Status.TAKEN: 3,
             Status.UNKNOWN: 4, Status.INVALID: 5}
    return sorted(results, key=lambda r: order[r.status])
