"""Разбор и проверка формата username по правилам Telegram.

Правила:
  * 5–32 символа (4-символьные бывают только коллекционные, с Fragment);
  * только латиница a–z, цифры и «_»;
  * начинается с буквы, не заканчивается на «_», без «__» подряд.
"""

from __future__ import annotations

import re

MIN_LEN = 5
MAX_LEN = 32
MAX_PER_MESSAGE = 20

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g", "ў": "w",
}

# t.me/xlebb, https://t.me/xlebb, telegram.me/xlebb, @xlebb, xlebb
_LINK_RE = re.compile(r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/", re.IGNORECASE)


def transliterate(text: str) -> str:
    return "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())


def normalize(token: str) -> str:
    """«@XLebb», «t.me/xlebb», «https://t.me/xlebb?start=1» → «xlebb»."""
    token = token.strip().strip(",;.!?()[]{}«»\"'")
    token = _LINK_RE.sub("", token)
    token = token.split("?", 1)[0].split("/", 1)[0]
    return token.lstrip("@").lower()


def parse_usernames(text: str) -> list[str]:
    """Достаёт из сообщения ники (через пробел, запятую или с новой строки)."""
    seen: list[str] = []
    for token in re.split(r"[\s,;]+", text):
        name = normalize(token)
        if name and name not in seen:
            seen.append(name)
    return seen[:MAX_PER_MESSAGE]


def format_error(name: str) -> str | None:
    """None — формат правильный, иначе понятная причина, почему нет."""
    if not name:
        return "пустой ник"
    bad = sorted({ch for ch in name if not ("a" <= ch <= "z" or ch.isdigit() or ch == "_")})
    if bad:
        if any("а" <= ch <= "я" or ch in "ёіїєґў" for ch in bad):
            hint = re.sub(r"[^a-z0-9_]", "", transliterate(name))
            return ("кириллица не разрешена — только латиница a–z, цифры и «_»"
                    + (f" (например, {hint})" if len(hint) >= MIN_LEN and hint[0].isalpha() else ""))
        shown = " ".join(bad[:5])
        return f"недопустимые символы: {shown} — можно только a–z, 0–9 и «_»"
    if not name[0].isalpha():
        return "должен начинаться с буквы"
    if name.endswith("_"):
        return "не может заканчиваться на «_»"
    if "__" in name:
        return "нельзя два «_» подряд"
    if len(name) < MIN_LEN:
        extra = " (4-символьные ники бывают только на Fragment)" if len(name) == 4 else ""
        return f"слишком короткий: {len(name)} симв., нужно минимум {MIN_LEN}{extra}"
    if len(name) > MAX_LEN:
        return f"слишком длинный: {len(name)} симв., максимум {MAX_LEN}"
    return None
