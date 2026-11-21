# -*- coding: utf-8 -*-
"""Малювання цифр заряду для значка в треї (і для попереднього перегляду в налаштуваннях)."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

import winutil

GREEN = (46, 204, 113)
YELLOW = (255, 196, 0)
RED = (255, 59, 48)
GRAY = (170, 170, 170)

# Пресети вигляду. Будь-який ключ можна перевизначити в config.json.
PRESETS = {
    # Як рідні значки Windows: Segoe UI, колір за темою панелі, без контуру
    "windows": dict(icon_font="seguisb.ttf", icon_color_mode="theme",
                    icon_outline=False, icon_stretch=1.0),
    # Кольорові жирні цифри з темним контуром (зелений / жовтий / червоний)
    "colored": dict(icon_font="segoeuib.ttf", icon_color_mode="status",
                    icon_outline=True, icon_stretch=1.5),
}

STYLE_KEYS = ("icon_font", "icon_color_mode", "icon_outline", "icon_stretch")


def icon_style(cfg):
    name = str(cfg.get("icon_style", "windows")).lower()
    style = dict(PRESETS.get(name, PRESETS["windows"]))
    for key in STYLE_KEYS:
        if cfg.get(key) is not None:
            style[key] = cfg[key]
    style["icon_red_when_low"] = bool(cfg.get("icon_red_when_low", True))
    return style


def status_color(percent):
    if percent is None:
        return GRAY
    if percent > 50:
        return GREEN
    if percent >= 20:
        return YELLOW
    return RED


def pick_color(percent, style, light=None):
    """light: примусова тема (для прев'ю); None — взяти тему панелі Windows."""
    if str(style["icon_color_mode"]).lower() == "status":
        return status_color(percent)
    if percent is not None and style.get("icon_red_when_low", True) and percent < 20:
        return RED
    if light is None:
        light = winutil.taskbar_is_light()
    return (28, 28, 28) if light else (255, 255, 255)


@lru_cache(maxsize=8)
def load_font(name, px):
    for candidate in (name, "seguisb.ttf", "segoeui.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, px)
        except (OSError, TypeError):
            continue
    return ImageFont.load_default()


def make_icon(text, color, style, size=None):
    """Малює цифри на всю іконку (суперсемплінг 8x)."""
    size = size or winutil.tray_icon_size()
    big = size * 8
    stroke = big // 10 if style["icon_outline"] else 0

    font = load_font(style["icon_font"], big)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    w, h = max(1, r - l), max(1, b - t)

    glyph = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glyph).text(
        (-l, -t), text, font=font, fill=tuple(color) + (255,),
        stroke_width=stroke, stroke_fill=(0, 0, 0, 235))

    scale = min(big * 0.98 / w, big * 0.94 / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    if text.isdigit():
        nh = min(int(big * 0.94), int(nh * float(style["icon_stretch"])))
    glyph = glyph.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    canvas.paste(glyph, ((big - nw) // 2, (big - nh) // 2))
    return canvas.resize((size, size), Image.LANCZOS)
