"""Стильные ники для отображаемого имени, игр и соцсетей: шрифты Unicode и украшения.

В отличие от username, здесь можно всё: кириллицу, пробелы, символы.
"""

from __future__ import annotations

import string

from .generator import transliterate

_LOWER = string.ascii_lowercase
_UPPER = string.ascii_uppercase


def _math_font(upper_start: int, lower_start: int, digit_start: int | None = None,
               exceptions: dict[str, str] | None = None):
    table: dict[str, str] = {}
    for i, ch in enumerate(_UPPER):
        table[ch] = chr(upper_start + i)
    for i, ch in enumerate(_LOWER):
        table[ch] = chr(lower_start + i)
    if digit_start is not None:
        for i in range(10):
            table[str(i)] = chr(digit_start + i)
    if exceptions:
        table.update(exceptions)
    return table


def _simple_map(src: str, dst: str) -> dict[str, str]:
    return dict(zip(src, dst))


FONTS: dict[str, dict[str, str]] = {
    "bold": _math_font(0x1D5D4, 0x1D5EE, 0x1D7EC),
    "italic": _math_font(0x1D63C, 0x1D656),
    "script": _math_font(0x1D4D0, 0x1D4EA),
    "fraktur": _math_font(0x1D56C, 0x1D586),
    "double": _math_font(0x1D538, 0x1D552, 0x1D7D8, {
        "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ",
    }),
    "mono": _math_font(0x1D670, 0x1D68A, 0x1D7F6),
    "circled": {
        **{ch: chr(0x24B6 + i) for i, ch in enumerate(_UPPER)},
        **{ch: chr(0x24D0 + i) for i, ch in enumerate(_LOWER)},
        **{str(i): chr(0x2460 + i - 1) for i in range(1, 10)},
        "0": "⓪",
    },
    "squared": {ch: chr(0x1F170 + i) for i, ch in enumerate(_UPPER)},
    "smallcaps": _simple_map(_LOWER, "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"),
    "fullwidth": {chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)},
    "tiny": _simple_map(_LOWER, "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻ"),
}

# «Латиница под кириллицу» — похожие буквы
_CYR_LOOKALIKE = _simple_map(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    "αбвгдєёжзийκлмнσπρςтуфχцчшщъыьэюя",
)

DECORATIONS = [
    "꧁{}꧂", "★彡{}彡★", "『{}』", "【{}】", "亗{}亗", "♛{}♛", "⚡{}⚡",
    "ღ{}ღ", "×{}×", "•{}•", "〖{}〗", "▄︻デ{}══━一", "✧{}✧", "࿐{}࿐",
    "☾{}☽", "꧁༺{}༻꧂", "⟦{}⟧", "─═{}═─",
]


def apply_font(text: str, font: str) -> str:
    table = FONTS[font]
    if font in ("squared",):
        text = text.upper()
    elif font in ("smallcaps", "tiny"):
        text = text.lower()
    return "".join(table.get(ch, ch) for ch in text)


def _has_cyrillic(text: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch.lower() in "ёіїєґў" for ch in text)


def stylize(text: str) -> list[str]:
    """Набор стильных вариантов текста (без повторов, в порядке «полезности»)."""
    text = " ".join(text.split())[:40]
    if not text:
        return []
    variants: list[str] = []

    # украшения работают с любым алфавитом, в том числе с кириллицей
    variants += [DECORATIONS[0].format(text), DECORATIONS[1].format(text),
                 DECORATIONS[2].format(text)]
    latin = text
    if _has_cyrillic(text):
        latin = transliterate(text).title() if text[:1].isupper() else transliterate(text)
        variants.append("".join(_CYR_LOOKALIKE.get(ch, ch) for ch in text.lower()))
    variants.append(" ".join(text.upper()))

    for font in ("bold", "script", "fraktur", "double", "mono", "italic",
                 "smallcaps", "circled", "squared", "fullwidth"):
        variants.append(apply_font(latin, font))

    styled_bold = apply_font(latin, "script")
    for deco in DECORATIONS[3:10]:
        variants.append(deco.format(styled_bold if len(variants) % 2 else latin))
    variants.append(latin + " ᵒᶠᶠⁱᶜⁱᵃˡ")
    variants.append("".join(ch + "̶" for ch in latin))   # зачёркнутый
    variants.append("".join(ch + "̲" for ch in latin))   # подчёркнутый
    variants.append("".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(latin)))

    seen: set[str] = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique
