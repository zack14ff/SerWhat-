"""Рисует аватарку бота (640×640) и картинку описания (640×360).

    python botfather/generate_assets.py

Готовые PNG уже лежат рядом, скрипт нужен, только если хотите их поменять.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
SCALE = 3  # рисуем крупнее и уменьшаем — так края получаются гладкими

TOP = (124, 58, 237)      # фиолетовый
BOTTOM = (14, 165, 233)   # голубой
ACCENT = (250, 204, 21)   # жёлтая искра
WHITE = (255, 255, 255)

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]
_FONT_REGULAR = [
    "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for path in (_FONT_CANDIDATES if bold else _FONT_REGULAR):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def gradient(w: int, h: int, top=TOP, bottom=BOTTOM) -> Image.Image:
    """Диагональный градиент."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.35 + y / h * 0.65)
            px[x, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img


def gradient_fast(w: int, h: int) -> Image.Image:
    small = gradient(64, max(2, 64 * h // w))
    return small.resize((w, h), Image.BICUBIC)


def sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    """Четырёхлучевая звёздочка ✦."""
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rad = r if i % 2 == 0 else r * 0.28
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def soft_shadow(size, draw_fn, blur: int, offset=(0, 0), color=(0, 0, 0, 90)) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_fn(d, color, offset)
    return layer.filter(ImageFilter.GaussianBlur(blur))


def make_avatar(path: Path, size: int = 640) -> None:
    S = size * SCALE
    img = gradient_fast(S, S).convert("RGBA")

    # мягкий световой круг за символом
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((S * 0.18, S * 0.16, S * 0.82, S * 0.80), fill=(255, 255, 255, 60))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S // 14)))

    f = font(int(S * 0.56))
    cx = S / 2
    # центрируем по реальным границам глифа, а не по метрикам шрифта
    left, top, right, bottom = ImageDraw.Draw(img).textbbox((0, 0), "@", font=f)
    x0 = cx - (left + right) / 2
    y0 = S * 0.45 - (top + bottom) / 2

    def at_sign(d, fill, off):
        d.text((x0 + off[0], y0 + off[1]), "@", font=f, fill=fill)

    img.alpha_composite(soft_shadow((S, S), at_sign, S // 60, (0, S // 60)))
    d = ImageDraw.Draw(img)
    at_sign(d, WHITE, (0, 0))

    # искры «кузницы»
    sparkle(d, S * 0.75, S * 0.21, S * 0.07, ACCENT)
    sparkle(d, S * 0.84, S * 0.33, S * 0.032, WHITE)
    sparkle(d, S * 0.22, S * 0.68, S * 0.035, (255, 255, 255, 220))

    # подпись внизу (внутри круга, который обрежет Telegram)
    label = font(int(S * 0.075))
    d.text((cx, S * 0.80), "NICK", font=label, fill=(255, 255, 255, 235), anchor="mm")

    img.resize((size, size), Image.LANCZOS).convert("RGB").save(path, optimize=True)


def chip(d: ImageDraw.ImageDraw, x: float, y: float, text: str, status: tuple, f, pad: float) -> float:
    w = d.textlength(text, font=f)
    h = f.size * 1.55
    dot = h * 0.28
    d.rounded_rectangle((x, y, x + w + pad * 2 + dot * 2.6, y + h), radius=h / 2,
                        fill=(255, 255, 255, 235))
    d.ellipse((x + pad, y + h / 2 - dot / 2, x + pad + dot, y + h / 2 + dot / 2), fill=status)
    d.text((x + pad + dot * 1.9, y + h / 2), text, font=f, fill=(49, 46, 129), anchor="lm")
    return x + w + pad * 2 + dot * 2.6


def make_description(path: Path, w: int = 640, h: int = 360) -> None:
    W, H = w * SCALE, h * SCALE
    img = gradient_fast(W, H).convert("RGBA")
    d = ImageDraw.Draw(img)

    for (sx, sy, r, c) in [(0.90, 0.16, 0.06, ACCENT), (0.95, 0.30, 0.025, WHITE),
                           (0.07, 0.86, 0.03, WHITE), (0.80, 0.84, 0.02, ACCENT)]:
        sparkle(d, W * sx, H * sy, H * r, c)

    title = font(int(H * 0.17))
    sub = font(int(H * 0.068), bold=False)
    d.text((W * 0.07, H * 0.14), "NickForge", font=title, fill=WHITE, anchor="lt")
    d.text((W * 0.07, H * 0.36), "Проверка ников + ИИ-подбор свободных", font=sub,
           fill=(255, 255, 255, 230), anchor="lt")

    green, red, fragment, invalid = (34, 197, 94), (239, 68, 68), (14, 165, 233), (249, 115, 22)
    cf = font(int(H * 0.06))
    pad = H * 0.035
    rows = [
        [("@xlebb", red), ("@crumbly", green), ("@loafy", green)],
        [("@money", fragment), ("xleb_", invalid), ("@breadly", green)],
    ]
    y = H * 0.55
    for row in rows:
        x = W * 0.07
        for text, st in row:
            x = chip(d, x, y, text, st, cf, pad) + W * 0.02
        y += cf.size * 1.55 + H * 0.045

    img.resize((w, h), Image.LANCZOS).convert("RGB").save(path, optimize=True)


if __name__ == "__main__":
    make_avatar(HERE / "avatar.png")
    make_description(HERE / "description.png")
    print("Готово:", HERE / "avatar.png", HERE / "description.png")
