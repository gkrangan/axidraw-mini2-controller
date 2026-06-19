"""Programmatic shape and text generation — produces SVG strings or point lists."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path


# ------------------------------------------------------------------
# SVG helpers
# ------------------------------------------------------------------

def _svg_wrap(body: str, width_in: float, height_in: float) -> str:
    w = f"{width_in}in"
    h = f"{height_in}in"
    vb = f"0 0 {width_in * 96} {height_in * 96}"   # 96 dpi
    return (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="{vb}">\n'
        f'{body}\n'
        f'</svg>\n'
    )


def _path_el(d: str, stroke: str = "black", width: float = 1.0) -> str:
    return f'  <path d="{d}" stroke="{stroke}" stroke-width="{width}" fill="none"/>'


# ------------------------------------------------------------------
# Basic shapes → SVG
# ------------------------------------------------------------------

def rect_svg(
    x: float, y: float, w: float, h: float,
    *,
    canvas_w: float = 6.0, canvas_h: float = 4.0,
) -> str:
    """Rectangle. All units in inches."""
    px, py, pw, ph = [v * 96 for v in (x, y, w, h)]
    body = f'  <rect x="{px}" y="{py}" width="{pw}" height="{ph}" stroke="black" stroke-width="1" fill="none"/>'
    return _svg_wrap(body, canvas_w, canvas_h)


def circle_svg(
    cx: float, cy: float, r: float,
    *,
    canvas_w: float = 6.0, canvas_h: float = 4.0,
) -> str:
    pcx, pcy, pr = cx * 96, cy * 96, r * 96
    body = f'  <circle cx="{pcx}" cy="{pcy}" r="{pr}" stroke="black" stroke-width="1" fill="none"/>'
    return _svg_wrap(body, canvas_w, canvas_h)


def polygon_svg(
    cx: float, cy: float, r: float, sides: int,
    *,
    canvas_w: float = 6.0, canvas_h: float = 4.0,
) -> str:
    """Regular polygon centred at (cx, cy) with circumradius r (inches)."""
    pts = _polygon_points(cx * 96, cy * 96, r * 96, sides)
    pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    body = f'  <polygon points="{pts_str}" stroke="black" stroke-width="1" fill="none"/>'
    return _svg_wrap(body, canvas_w, canvas_h)


def line_svg(
    x1: float, y1: float, x2: float, y2: float,
    *,
    canvas_w: float = 6.0, canvas_h: float = 4.0,
) -> str:
    px1, py1, px2, py2 = x1 * 96, y1 * 96, x2 * 96, y2 * 96
    body = f'  <line x1="{px1}" y1="{py1}" x2="{px2}" y2="{py2}" stroke="black" stroke-width="1"/>'
    return _svg_wrap(body, canvas_w, canvas_h)


def text_svg(
    text: str,
    x: float, y: float,
    font_size_pt: float = 12,
    font_name: str = "futural",
    *,
    canvas_w: float = 6.0, canvas_h: float = 4.0,
) -> str:
    """
    Render text as plotter-ready SVG <path> elements using Hershey stroke fonts.

    Hershey fonts are single-stroke vector fonts designed for pen plotters —
    every character is a set of line segments with no fill, so pyaxidraw can
    plot them directly without any conversion step.

    Parameters
    ----------
    text        : string to render
    x, y        : position in inches (bottom-left of text baseline)
    font_size_pt: point size (default 12)
    font_name   : Hershey font name — common options:
                    'futural'  (sans-serif, default)
                    'futuram'  (sans-serif bold)
                    'cursive'  (italic cursive)
                    'gothgbt'  (gothic)
                    'scripts'  (script)
    canvas_w/h  : SVG canvas dimensions in inches
    """
    try:
        from HersheyFonts import HersheyFonts
    except ImportError:
        raise RuntimeError(
            "hershey-fonts is not installed. Run: pip install hershey-fonts"
        )

    hf = HersheyFonts()
    try:
        hf.load_default_font(font_name)
    except Exception:
        hf.load_default_font("futural")

    # Scale factor: Hershey glyphs span roughly 21 units cap-height.
    # Convert pt → inches (1pt = 1/72 in), then to 96-dpi SVG pixels.
    scale = (font_size_pt / 72.0) * 96 / 21.0

    ox = x * 96   # origin in SVG pixels
    oy = y * 96

    paths = []
    for stroke in hf.strokes_for_text(text):
        if len(stroke) < 2:
            continue
        pts = [(ox + sx * scale, oy + sy * scale) for sx, sy in stroke]
        d = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in pts)
        paths.append(
            f'  <path d="{d}" stroke="black" stroke-width="0.8" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    if not paths:
        raise ValueError(f"No strokes generated for text: {text!r}")

    body = "\n".join(paths)
    return _svg_wrap(body, canvas_w, canvas_h)


# ------------------------------------------------------------------
# Point-list helpers (for direct plotter.draw_path())
# ------------------------------------------------------------------

def rect_path(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def circle_path(cx: float, cy: float, r: float, steps: int = 72) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(2 * math.pi * i / steps),
         cy + r * math.sin(2 * math.pi * i / steps))
        for i in range(steps + 1)
    ]


def polygon_path(cx: float, cy: float, r: float, sides: int) -> list[tuple[float, float]]:
    pts = _polygon_points(cx, cy, r, sides)
    return pts + [pts[0]]


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------

def _polygon_points(cx: float, cy: float, r: float, sides: int) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(2 * math.pi * i / sides - math.pi / 2),
         cy + r * math.sin(2 * math.pi * i / sides - math.pi / 2))
        for i in range(sides)
    ]
