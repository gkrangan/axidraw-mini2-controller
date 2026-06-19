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
    *,
    canvas_w: float = 6.0, canvas_h: float = 4.0,
) -> str:
    """
    Render text as SVG <text> element.
    Note: AxiDraw will render this as a font glyph outline only if Hershey
    text is used. For best results, convert to paths with Inkscape first.
    """
    px, py = x * 96, y * 96
    fs = font_size_pt * 1.333   # pt → px
    body = (
        f'  <text x="{px}" y="{py}" font-size="{fs:.1f}" '
        f'font-family="sans-serif" stroke="black" stroke-width="0.5" fill="none">'
        f'{text}</text>'
    )
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
