import asyncio
import json
from types import SimpleNamespace

import pytest

from nickbot.ai import MAX_ROUNDS, AIUnavailable, NickAI
from nickbot.checker import CheckResult, Status


class FakeChecker:
    def __init__(self, free):
        self.free = set(free)
        self.checked = []

    async def check_many(self, names):
        self.checked += names
        return [CheckResult(n, Status.FREE if n in self.free else Status.TAKEN, precise=True)
                for n in names]


def tool_use(names, id_="t1"):
    return SimpleNamespace(type="tool_use", id=id_, name="check_usernames", input={"usernames": names})


def text(t):
    return SimpleNamespace(type="text", text=t)


class FakeMessages:
    """Подмена client.beta.messages: отдаёт заранее заданные ответы Claude."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        stop, content = self.script.pop(0)
        return SimpleNamespace(stop_reason=stop, content=content)


def make_ai(script, free=(), limit=5, allowed=()):
    checker = FakeChecker(free)
    ai = NickAI("sk-test", checker, "claude-opus-5-5", "medium",
                daily_limit=limit, allowed_users=set(allowed))
    ai.client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(script)))
    return ai, checker


def test_ai_checks_and_answers():
    ai, checker = make_ai([
        ("tool_use", [tool_use(["xlebushek", "breadly"])]),
        ("end_turn", [text("Свободен @breadly — хлеб + -ly")]),
    ], free={"breadly"})
    progress = []

    async def on_progress(results):
        progress.append(len(results))

    reply = asyncio.run(ai.ask(1, "ник про хлеб", on_progress))
    assert "@breadly" in reply.text
    assert {r.username: r.status for r in reply.checked} == {
        "xlebushek": Status.TAKEN, "breadly": Status.FREE}
    assert checker.checked == ["xlebushek", "breadly"]
    assert progress == [2]

    calls = ai.client.beta.messages.calls
    assert calls[0]["model"] == "claude-opus-5-5"
    assert calls[0]["tools"][0]["name"] == "check_usernames"
    assert calls[0]["fallbacks"] == "default"
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "t1"
    assert json.loads(tool_result["content"])[1] == {
        "username": "breadly", "status": "free", "reason": "свободен"}
    # история сохраняется, чтобы можно было уточнять: «короче», «без цифр»
    assert len(ai._conversations[1].messages) == 4


def test_ai_follow_up_keeps_history():
    ai, _ = make_ai([("end_turn", [text("a")]), ("end_turn", [text("b")])])
    asyncio.run(ai.ask(1, "первый"))
    asyncio.run(ai.ask(1, "короче"))
    sent = ai.client.beta.messages.calls[1]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[-1]["content"] == "короче"


def test_ai_round_limit_stops_checking():
    script = [("tool_use", [tool_use([f"name{i}x"], id_=f"t{i}")]) for i in range(MAX_ROUNDS + 2)]
    ai, checker = make_ai(script)
    reply = asyncio.run(ai.ask(1, "что угодно"))
    assert len(checker.checked) == MAX_ROUNDS          # дальше лимита не проверяет
    assert 1 not in ai._conversations                  # оборванная история не сохраняется
    assert len(reply.checked) == MAX_ROUNDS


def test_ai_daily_limit_and_allow_list():
    ai, _ = make_ai([("end_turn", [text("ok")])] * 3, limit=1)
    asyncio.run(ai.ask(1, "a"))
    with pytest.raises(AIUnavailable):
        asyncio.run(ai.ask(1, "b"))

    ai, _ = make_ai([("end_turn", [text("ok")])], allowed={42})
    with pytest.raises(AIUnavailable):
        asyncio.run(ai.ask(1, "a"))
    assert asyncio.run(ai.ask(42, "a")).text == "ok"


def test_ai_refusal_resets():
    ai, _ = make_ai([("refusal", [])])
    reply = asyncio.run(ai.ask(1, "x"))
    assert reply.refused and 1 not in ai._conversations
