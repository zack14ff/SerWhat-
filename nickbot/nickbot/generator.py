"""Генератор username-ов для Telegram: удобные и похожие варианты на слово или текст.

Правила Telegram для username:
  * 5–32 символа;
  * только латиница a–z, цифры и «_»;
  * начинается с буквы, не заканчивается на «_», без «__» подряд.
"""

from __future__ import annotations

import difflib
import random
import re
from dataclasses import dataclass, field

TG_MIN_LEN = 5
TG_MAX_LEN = 32

_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$")

# Основная транслитерация (как в загранпаспорте, но чуть «по-интернетному»)
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    # украинский / белорусский
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g", "ў": "w",
}

# Альтернативная, более короткая транслитерация
_TRANSLIT_ALT = {
    **_TRANSLIT,
    "ё": "e", "ж": "j", "й": "j", "х": "h", "ц": "c", "щ": "sh",
    "ы": "i", "ю": "ju", "я": "ja", "ї": "i", "є": "e",
}

# Похожие по звучанию/виду замены: (что, на что)
_SIMILAR_SWAPS = [
    ("ks", "x"), ("x", "ks"), ("ph", "f"), ("f", "ph"), ("c", "k"), ("k", "c"),
    ("ck", "k"), ("s", "z"), ("z", "s"), ("i", "y"), ("y", "i"), ("ee", "i"),
    ("oo", "u"), ("u", "oo"), ("w", "v"), ("v", "w"), ("kh", "h"), ("ts", "tz"),
    ("ch", "tch"), ("sh", "sch"), ("q", "k"), ("er", "a"), ("or", "a"),
]

_LEET = {"o": "0", "e": "3", "a": "4", "i": "1", "s": "5", "t": "7", "b": "8", "g": "9"}

_PREFIXES = [
    "the", "its", "im", "iam", "mr", "real", "just", "hey", "x", "neo",
    "true", "only", "super", "mega", "pro", "not", "yo", "oh",
]
_SUFFIXES = [
    "x", "o", "y", "ik", "ya", "ka", "ok", "ly", "io", "er", "on", "off", "ov", "ovich",
    "sky", "hq", "tg", "dev", "art", "live", "online", "official", "bot",
    "pro", "go", "one", "zz", "yy",
]
_NUM_SUFFIXES = ["7", "13", "21", "77", "99", "01", "007", "777", "2k", "x2"]

_VOWELS = set("aeiouy")

CATEGORY_TITLES = {
    "exact": "🎯 Точные",
    "similar": "🪞 Похожие",
    "affix": "➕ С приставками",
    "short": "✂️ Короткие",
}


@dataclass
class Settings:
    min_len: int = TG_MIN_LEN
    max_len: int = 20
    digits: bool = True
    underscore: bool = True


@dataclass(order=True)
class Suggestion:
    sort_key: float
    name: str = field(compare=False)
    category: str = field(compare=False)


# --------------------------------------------------------------------------- #
# Базовые утилиты
# --------------------------------------------------------------------------- #

def transliterate(text: str, alt: bool = False) -> str:
    table = _TRANSLIT_ALT if alt else _TRANSLIT
    return "".join(table.get(ch, ch) for ch in text.lower())


def extract_words(text: str, alt: bool = False) -> list[str]:
    """Текст → список латинских слов (из любой раскладки/языка, что умеем)."""
    latin = transliterate(text, alt=alt)
    return [w for w in re.split(r"[^a-z0-9]+", latin) if w]


def is_valid_username(name: str, min_len: int = TG_MIN_LEN, max_len: int = TG_MAX_LEN) -> bool:
    return (
        min_len <= len(name) <= max_len
        and bool(_USERNAME_RE.match(name))
        and "__" not in name
    )


def _strip_vowels(word: str) -> str:
    """Убирает гласные, кроме первой буквы: «telegram» → «tlgrm»."""
    if len(word) <= 2:
        return word
    return word[0] + "".join(ch for ch in word[1:] if ch not in _VOWELS)


def _pronounceability_penalty(name: str) -> float:
    letters = re.sub(r"[^a-z]", "", name)
    penalty = 0.0
    for run in re.findall(r"[^aeiouy]{4,}", letters):
        penalty += 0.08 * (len(run) - 3)
    for run in re.findall(r"[aeiouy]{3,}", letters):
        penalty += 0.06 * (len(run) - 2)
    return penalty


def score(name: str, base: str, category: str) -> float:
    """Чем больше — тем «удобнее» и ближе к исходному слову."""
    flat = name.replace("_", "")
    similarity = difflib.SequenceMatcher(None, base, flat).ratio()
    length = len(name)
    length_penalty = 0.0
    if length > 12:
        length_penalty = 0.025 * (length - 12)
    elif length < 6:
        length_penalty = 0.04 * (6 - length)
    digits = sum(ch.isdigit() for ch in name)
    bonus = {"exact": 0.35, "similar": 0.15, "short": 0.1, "affix": 0.0}[category]
    return (
        similarity
        + bonus
        - length_penalty
        - 0.12 * name.count("_")
        - 0.07 * digits
        - _pronounceability_penalty(name)
    )


# --------------------------------------------------------------------------- #
# Генерация вариантов
# --------------------------------------------------------------------------- #

def _join_variants(words: list[str]) -> set[str]:
    out = {"".join(words)}
    if len(words) > 1:
        out.add("_".join(words))
        out.add(words[0] + words[-1])
        alpha = [w for w in words if w.isalpha()]
        if len(alpha) > 1:
            out.add(alpha[0][0] + "".join(alpha[1:]))                  # i + petrov
            out.add("".join(w[0] for w in alpha[:-1]) + alpha[-1])     # инициалы + фамилия
            out.add(alpha[0] + "".join(w[0] for w in alpha[1:]))
        out.add(words[-1] + words[0])
        for w in words:
            out.add(w)
    return out


def _similar_variants(base: str) -> set[str]:
    out: set[str] = set()
    # похожие по звучанию замены
    for src, dst in _SIMILAR_SWAPS:
        if src in base:
            out.add(base.replace(src, dst, 1))
            out.add(base.replace(src, dst))
    # удвоение последней буквы и пары согласных (не всех, чтобы не было однообразия)
    if base:
        out.add(base + base[-1])
    consonants = [i for i, ch in enumerate(base) if i > 0 and ch.isalpha() and ch not in _VOWELS]
    for i in consonants[:1] + consonants[-2:-1]:
        out.add(base[: i + 1] + base[i] + base[i + 1 :])
    # растягивание гласной: «nick» → «niick»
    for i, ch in enumerate(base):
        if ch in _VOWELS:
            out.add(base[: i + 1] + ch + base[i + 1 :])
            break
    # leet: по одной замене, чтобы ник оставался читаемым
    for src, dst in _LEET.items():
        if src in base[1:]:
            idx = base.index(src, 1)
            out.add(base[:idx] + dst + base[idx + 1 :])
    # зеркальный приём: «telegram» → «margelet»
    if len(base) >= 3 and base.isalpha():
        out.add(base[::-1])
    return out


def _affix_variants(base: str, digits: bool) -> set[str]:
    out: set[str] = set()
    for p in _PREFIXES:
        out.add(p + base)
        out.add(f"{p}_{base}")
    for s in _SUFFIXES:
        out.add(base + s)
        out.add(f"{base}_{s}")
    if digits:
        for n in _NUM_SUFFIXES:
            out.add(base + n)
            out.add(f"{base}_{n}")
    out.add(f"x{base}x")
    out.add(f"x_{base}_x")
    return out


def _short_variants(base: str) -> set[str]:
    out = {_strip_vowels(base)}
    for n in range(4, min(len(base), 9)):
        out.add(base[:n])
    if len(base) > 6 and base.isalpha():
        out.add(base[:3] + base[-3:])
    return out


def _fit(name: str, settings: Settings) -> str | None:
    """Приводит вариант к настройкам пользователя или отбрасывает его."""
    if not settings.underscore:
        name = name.replace("_", "")
    if not settings.digits and any(ch.isdigit() for ch in name):
        return None
    name = name.strip("_")
    while "__" in name:
        name = name.replace("__", "_")
    if name and name[0].isdigit():
        return None
    if not is_valid_username(name, max(settings.min_len, TG_MIN_LEN), min(settings.max_len, TG_MAX_LEN)):
        return None
    return name


def build_pool(text: str, settings: Settings | None = None) -> list[Suggestion]:
    """Все варианты для текста, отсортированные по удобству."""
    settings = settings or Settings()
    words = extract_words(text)
    if not words:
        return []
    alt_words = extract_words(text, alt=True)

    base = "".join(words)
    raw: dict[str, str] = {}  # имя → категория (первая назначенная побеждает)

    def add(names: set[str], category: str) -> None:
        for n in names:
            raw.setdefault(n, category)

    exact = _join_variants(words)
    if alt_words != words:
        exact |= _join_variants(alt_words)
    add(exact, "exact")

    heads = {base, "".join(alt_words)}
    if len(words) > 1:
        heads.add(words[0])
        heads.add(words[-1])
    for h in heads:
        add(_similar_variants(h), "similar")
        add(_short_variants(h), "short")
        add(_affix_variants(h, settings.digits), "affix")

    pool: list[Suggestion] = []
    seen: set[str] = set()
    for name, category in raw.items():
        fitted = _fit(name, settings)
        if not fitted or fitted in seen:
            continue
        seen.add(fitted)
        pool.append(Suggestion(-score(fitted, base, category), fitted, category))
    pool.sort()
    return pool


def interleave(pool: list[Suggestion], seed: int | None = None) -> list[Suggestion]:
    """Смешивает категории, чтобы на каждой странице было разнообразие.

    Внутри категории порядок по удобству сохраняется; seed слегка
    перемешивает соседние варианты, чтобы «Ещё» давало свежие идеи.
    """
    rng = random.Random(seed)
    buckets: dict[str, list[Suggestion]] = {}
    for s in pool:
        buckets.setdefault(s.category, []).append(s)
    if seed is not None:
        for items in buckets.values():
            # лёгкое перемешивание в окнах по 4, лучшие остаются наверху
            for i in range(0, len(items), 4):
                window = items[i : i + 4]
                rng.shuffle(window)
                items[i : i + 4] = window
    order = ["exact", "similar", "affix", "short"]
    weights = {"exact": 2, "similar": 3, "affix": 3, "short": 1}
    result: list[Suggestion] = []
    while any(buckets.get(c) for c in order):
        for c in order:
            items = buckets.get(c)
            for _ in range(weights[c]):
                if items:
                    result.append(items.pop(0))
    return result


def suggest(text: str, settings: Settings | None = None, page: int = 0,
            page_size: int = 12, seed: int | None = None) -> list[Suggestion]:
    ordered = interleave(build_pool(text, settings), seed)
    return ordered[page * page_size : (page + 1) * page_size]


# --------------------------------------------------------------------------- #
# Случайные ники
# --------------------------------------------------------------------------- #

_ADJECTIVES = [
    "silent", "neon", "lucky", "frosty", "shadow", "cosmic", "lazy", "wild",
    "pixel", "crimson", "velvet", "rapid", "quiet", "golden", "lunar", "cyber",
    "misty", "stormy", "sunny", "brave", "sly", "dark", "fuzzy", "solar",
]
_NOUNS = [
    "fox", "wolf", "raven", "panda", "tiger", "ghost", "comet", "otter",
    "falcon", "dragon", "koala", "lynx", "orbit", "nova", "byte", "echo",
    "storm", "pixel", "ninja", "cat", "bear", "owl", "shark", "phoenix",
]


def random_nicks(count: int = 10, settings: Settings | None = None,
                 seed: int | None = None) -> list[str]:
    settings = settings or Settings()
    rng = random.Random(seed)
    result: list[str] = []
    attempts = 0
    while len(result) < count and attempts < count * 30:
        attempts += 1
        adj, noun = rng.choice(_ADJECTIVES), rng.choice(_NOUNS)
        pattern = rng.randint(0, 4)
        if pattern == 0:
            name = adj + noun
        elif pattern == 1:
            name = f"{adj}_{noun}"
        elif pattern == 2:
            name = noun + rng.choice(_SUFFIXES)
        elif pattern == 3:
            name = adj + noun + rng.choice(_NUM_SUFFIXES)
        else:
            name = rng.choice(_PREFIXES) + noun
        fitted = _fit(name, settings)
        if fitted and fitted not in result:
            result.append(fitted)
    return result
