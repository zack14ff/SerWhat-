import asyncio

from telethon import errors

from nickbot.checker import Checker, Status, parse_fragment_page, parse_tme_page

TME_TAKEN = '<div class="tgme_page"><div class="tgme_page_extra">@durov</div></div>'
TME_EMPTY = '<div class="tgme_page"><div class="tgme_page_description">If you have Telegram…</div></div>'
NOT_ON_FRAGMENT = (200, "https://fragment.com/?query=x", "<div>search</div>")


def run(coro):
    return asyncio.run(coro)


def test_parse_tme_page():
    assert parse_tme_page(TME_TAKEN) is Status.TAKEN
    assert parse_tme_page(TME_EMPTY) is Status.FREE
    assert parse_tme_page("<html>captcha</html>") is Status.UNKNOWN


def test_parse_fragment_page():
    assert parse_fragment_page('<span class="tm-section-header-status tm-status-avail">') is Status.FRAGMENT
    assert parse_fragment_page('<span class="tm-status-unavail">Sold</span>') is Status.FRAGMENT
    assert parse_fragment_page('<span class="tm-status-taken">Taken</span>') is Status.TAKEN
    assert parse_fragment_page("<div>search</div>") is None


class FakeWebChecker(Checker):
    """Checker без сети: страницы берутся из словаря url → (код, итоговый url, html)."""

    def __init__(self, pages, tg=None):
        super().__init__(http=None, tg=tg)
        self.pages = pages
        self.requests = []

    async def _get(self, url):
        self.requests.append(url)
        return self.pages.get(url, NOT_ON_FRAGMENT)


class FakeTelegram:
    """Подмена Telethon-клиента: отвечает как account.checkUsername."""

    def __init__(self, answers):
        self.answers = answers

    async def __call__(self, request):
        answer = self.answers[request.username]
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_web_check_statuses():
    checker = FakeWebChecker({
        "https://t.me/durov": (200, "https://t.me/durov", TME_TAKEN),
        "https://t.me/xlebb": (200, "https://t.me/xlebb", TME_EMPTY),
        "https://t.me/money": (200, "https://t.me/money", TME_EMPTY),
        "https://fragment.com/username/money": (
            200, "https://fragment.com/username/money", '<span class="tm-status-avail">'),
    })
    results = {r.username: r for r in run(checker.check_many(["@Durov", "xlebb", "money", "xl"]))}
    assert results["durov"].status is Status.TAKEN
    assert results["xlebb"].status is Status.FREE and not results["xlebb"].precise
    assert results["money"].status is Status.FRAGMENT
    assert results["xl"].status is Status.INVALID
    assert "https://t.me/xl" not in checker.requests  # невалидные ники не запрашиваем


def test_cache():
    checker = FakeWebChecker({"https://t.me/durov": (200, "https://t.me/durov", TME_TAKEN)})
    run(checker.check("durov"))
    run(checker.check("durov"))
    assert checker.requests.count("https://t.me/durov") == 1


def test_mtproto_check():
    tg = FakeTelegram({
        "xlebb": False,
        "freeone": True,
        "money": errors.UsernamePurchaseAvailableError(request=None),
        "admin": errors.UsernameInvalidError(request=None),
    })
    checker = FakeWebChecker({}, tg=tg)
    results = {r.username: r for r in run(checker.check_many(["xlebb", "freeone", "money", "admin"]))}
    assert results["xlebb"].status is Status.TAKEN and results["xlebb"].precise
    assert results["freeone"].status is Status.FREE and results["freeone"].precise
    assert results["money"].status is Status.FRAGMENT
    assert results["admin"].status is Status.INVALID
    assert checker.requests == []  # при точной проверке в веб не ходим


def test_mtproto_flood_falls_back_to_web():
    tg = FakeTelegram({"xlebb": errors.FloodWaitError(request=None, capture=60)})
    checker = FakeWebChecker({"https://t.me/xlebb": (200, "https://t.me/xlebb", TME_TAKEN)}, tg=tg)
    result = run(checker.check("xlebb"))
    assert result.status is Status.TAKEN and not result.precise
    assert not checker.precise_available
