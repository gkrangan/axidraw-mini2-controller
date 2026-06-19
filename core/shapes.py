"""Programmatic shape and text generation — produces plotter-ready SVG strings."""

from __future__ import annotations

import math
from typing import Literal

MM_PER_IN: float = 25.4

# Hard physical limits — mirrors plotter.py constants so shapes.py stays independent
_X_HARD_MAX_MM: float = 150.0
_Y_HARD_MAX_MM: float = 100.0

Unit = Literal["mm", "in"]


# ------------------------------------------------------------------
# Unit conversion
# ------------------------------------------------------------------

def _to_mm(v: float, unit: Unit) -> float:
    return v if unit == "mm" else v * MM_PER_IN


def _to_in(v: float, unit: Unit) -> float:
    return v / MM_PER_IN if unit == "mm" else v


# ------------------------------------------------------------------
# Bounds checking
# ------------------------------------------------------------------

def check_bounds(
    x1_mm: float, y1_mm: float,
    x2_mm: float, y2_mm: float,
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> None:
    """
    Raise ValueError if the bounding box (x1,y1)→(x2,y2) in mm falls
    outside the plotter's configured travel limits or the hard physical caps.
    x1/y1 are the minimum corners; x2/y2 are the maximum corners.
    """
    x_limit = min(x_max_mm, _X_HARD_MAX_MM)
    y_limit = min(y_max_mm, _Y_HARD_MAX_MM)
    errors = []
    if x1_mm < 0:
        errors.append(f"left edge {x1_mm:.1f} mm is left of origin")
    if y1_mm < 0:
        errors.append(f"top edge {y1_mm:.1f} mm is above origin")
    if x2_mm > x_limit:
        errors.append(
            f"right edge {x2_mm:.1f} mm exceeds X limit ({x_limit:.0f} mm)"
        )
    if y2_mm > y_limit:
        errors.append(
            f"bottom edge {y2_mm:.1f} mm exceeds Y limit ({y_limit:.0f} mm)"
        )
    if errors:
        raise ValueError("Shape out of bounds — " + "; ".join(errors))


def _bounds_from_points(pts_mm: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Return (x1, y1, x2, y2) bounding box from a list of (x, y) mm points."""
    xs = [p[0] for p in pts_mm]
    ys = [p[1] for p in pts_mm]
    return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------
# SVG helpers
# ------------------------------------------------------------------

def _svg_wrap(body: str, canvas_w_in: float, canvas_h_in: float) -> str:
    w = f"{canvas_w_in:.4f}in"
    h = f"{canvas_h_in:.4f}in"
    vb = f"0 0 {canvas_w_in * 96:.2f} {canvas_h_in * 96:.2f}"
    return (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="{vb}">\n'
        f'{body}\n'
        f'</svg>\n'
    )


def _px(mm: float) -> float:
    """Convert mm to SVG pixels (96 dpi)."""
    return (mm / MM_PER_IN) * 96


# ------------------------------------------------------------------
# Rectangle
# ------------------------------------------------------------------

def rect_svg(
    x: float, y: float, w: float, h: float,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """
    Rectangle with top-left corner at (x, y) and given width/height.

    Args:
        x, y    : top-left corner position
        w, h    : width and height
        unit    : "mm" (default) or "in"
        x_max_mm, y_max_mm : plotter travel limits for bounds check
    """
    x_mm  = _to_mm(x, unit)
    y_mm  = _to_mm(y, unit)
    w_mm  = _to_mm(w, unit)
    h_mm  = _to_mm(h, unit)
    check_bounds(x_mm, y_mm, x_mm + w_mm, y_mm + h_mm, x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    px, py, pw, ph = _px(x_mm), _px(y_mm), _px(w_mm), _px(h_mm)
    body = (
        f'  <rect x="{px:.2f}" y="{py:.2f}" width="{pw:.2f}" height="{ph:.2f}" '
        f'stroke="black" stroke-width="1" fill="none"/>'
    )
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Square
# ------------------------------------------------------------------

def square_svg(
    x: float, y: float, side: float,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """Square with top-left corner at (x, y) and equal side length."""
    return rect_svg(x, y, side, side, unit=unit, x_max_mm=x_max_mm, y_max_mm=y_max_mm)


# ------------------------------------------------------------------
# Circle
# ------------------------------------------------------------------

def circle_svg(
    cx: float, cy: float, r: float,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """Circle with centre (cx, cy) and radius r."""
    cx_mm = _to_mm(cx, unit)
    cy_mm = _to_mm(cy, unit)
    r_mm  = _to_mm(r, unit)
    check_bounds(cx_mm - r_mm, cy_mm - r_mm, cx_mm + r_mm, cy_mm + r_mm, x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    body = (
        f'  <circle cx="{_px(cx_mm):.2f}" cy="{_px(cy_mm):.2f}" r="{_px(r_mm):.2f}" '
        f'stroke="black" stroke-width="1" fill="none"/>'
    )
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Ellipse
# ------------------------------------------------------------------

def ellipse_svg(
    cx: float, cy: float, rx: float, ry: float,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """Ellipse with centre (cx, cy) and X/Y radii rx, ry."""
    cx_mm = _to_mm(cx, unit)
    cy_mm = _to_mm(cy, unit)
    rx_mm = _to_mm(rx, unit)
    ry_mm = _to_mm(ry, unit)
    check_bounds(cx_mm - rx_mm, cy_mm - ry_mm, cx_mm + rx_mm, cy_mm + ry_mm, x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    body = (
        f'  <ellipse cx="{_px(cx_mm):.2f}" cy="{_px(cy_mm):.2f}" '
        f'rx="{_px(rx_mm):.2f}" ry="{_px(ry_mm):.2f}" '
        f'stroke="black" stroke-width="1" fill="none"/>'
    )
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Regular polygon
# ------------------------------------------------------------------

def polygon_svg(
    cx: float, cy: float, r: float, sides: int,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """Regular polygon with centre (cx, cy) and circumradius r."""
    cx_mm = _to_mm(cx, unit)
    cy_mm = _to_mm(cy, unit)
    r_mm  = _to_mm(r, unit)
    pts_mm = _polygon_points_mm(cx_mm, cy_mm, r_mm, sides)
    check_bounds(*_bounds_from_points(pts_mm), x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    pts_str = " ".join(f"{_px(x):.2f},{_px(y):.2f}" for x, y in pts_mm)
    body = f'  <polygon points="{pts_str}" stroke="black" stroke-width="1" fill="none"/>'
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Triangle
# ------------------------------------------------------------------

def triangle_svg(
    cx: float, cy: float, side: float,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """
    Equilateral triangle centred at (cx, cy) with given side length.
    Flat base at the bottom (one vertex pointing up).
    """
    cx_mm   = _to_mm(cx, unit)
    cy_mm   = _to_mm(cy, unit)
    side_mm = _to_mm(side, unit)
    # Circumradius of equilateral triangle = side / √3
    r_mm = side_mm / math.sqrt(3)
    pts_mm = _polygon_points_mm(cx_mm, cy_mm, r_mm, 3, start_angle=-math.pi / 2)
    check_bounds(*_bounds_from_points(pts_mm), x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    pts_str = " ".join(f"{_px(x):.2f},{_px(y):.2f}" for x, y in pts_mm)
    body = f'  <polygon points="{pts_str}" stroke="black" stroke-width="1" fill="none"/>'
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Star
# ------------------------------------------------------------------

def star_svg(
    cx: float, cy: float,
    r_outer: float, r_inner: float,
    points: int = 5,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """
    N-pointed star centred at (cx, cy).

    Args:
        r_outer : radius to the outer tips
        r_inner : radius to the inner valleys (typically 0.4–0.5 × r_outer)
        points  : number of star points (default 5)
    """
    cx_mm      = _to_mm(cx, unit)
    cy_mm      = _to_mm(cy, unit)
    r_out_mm   = _to_mm(r_outer, unit)
    r_in_mm    = _to_mm(r_inner, unit)
    pts_mm = _star_points_mm(cx_mm, cy_mm, r_out_mm, r_in_mm, points)
    check_bounds(*_bounds_from_points(pts_mm), x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    pts_str = " ".join(f"{_px(x):.2f},{_px(y):.2f}" for x, y in pts_mm)
    body = f'  <polygon points="{pts_str}" stroke="black" stroke-width="1" fill="none"/>'
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Line
# ------------------------------------------------------------------

def line_svg(
    x1: float, y1: float, x2: float, y2: float,
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """Straight line from (x1, y1) to (x2, y2)."""
    pts_mm = [
        (_to_mm(x1, unit), _to_mm(y1, unit)),
        (_to_mm(x2, unit), _to_mm(y2, unit)),
    ]
    check_bounds(*_bounds_from_points(pts_mm), x_max_mm, y_max_mm)
    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    (ax, ay), (bx, by) = pts_mm
    body = (
        f'  <line x1="{_px(ax):.2f}" y1="{_px(ay):.2f}" '
        f'x2="{_px(bx):.2f}" y2="{_px(by):.2f}" '
        f'stroke="black" stroke-width="1"/>'
    )
    return _svg_wrap(body, cw, ch)


# ------------------------------------------------------------------
# Text (Hershey stroke fonts)
# ------------------------------------------------------------------

def text_svg(
    text: str,
    x: float, y: float,
    font_size_pt: float = 12,
    font_name: str = "futural",
    *,
    unit: Unit = "mm",
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
) -> str:
    """
    Render text as plotter-ready SVG <path> elements using Hershey stroke fonts.

    Args:
        text        : string to render
        x, y        : baseline start position
        font_size_pt: point size (default 12)
        font_name   : Hershey font — 'futural' (default), 'futuram', 'cursive',
                      'gothgbt', 'gothgrt', 'scripts', 'cyrillic'
        unit        : "mm" (default) or "in"
        x_max_mm, y_max_mm : plotter travel limits for bounds check
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

    x_mm = _to_mm(x, unit)
    y_mm = _to_mm(y, unit)

    # Hershey glyph cap-height ≈ 21 units → convert pt to mm then to glyph scale
    scale_mm = (font_size_pt / 72.0) * MM_PER_IN / 21.0

    all_pts_mm: list[tuple[float, float]] = []
    paths: list[str] = []

    for stroke in hf.strokes_for_text(text):
        if len(stroke) < 2:
            continue
        pts = [(x_mm + sx * scale_mm, y_mm + sy * scale_mm) for sx, sy in stroke]
        all_pts_mm.extend(pts)
        d = "M " + " L ".join(f"{_px(px):.2f},{_px(py):.2f}" for px, py in pts)
        paths.append(
            f'  <path d="{d}" stroke="black" stroke-width="0.8" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    if not paths:
        raise ValueError(f"No strokes generated for text: {text!r}")

    check_bounds(*_bounds_from_points(all_pts_mm), x_max_mm, y_max_mm)

    cw = x_max_mm / MM_PER_IN
    ch = y_max_mm / MM_PER_IN
    return _svg_wrap("\n".join(paths), cw, ch)


# ------------------------------------------------------------------
# Point-list helpers (for direct plotter.draw_path() — units always inches)
# ------------------------------------------------------------------

def rect_path(x_in: float, y_in: float, w_in: float, h_in: float) -> list[tuple[float, float]]:
    return [(x_in, y_in), (x_in + w_in, y_in), (x_in + w_in, y_in + h_in),
            (x_in, y_in + h_in), (x_in, y_in)]


def circle_path(cx_in: float, cy_in: float, r_in: float, steps: int = 72) -> list[tuple[float, float]]:
    return [
        (cx_in + r_in * math.cos(2 * math.pi * i / steps),
         cy_in + r_in * math.sin(2 * math.pi * i / steps))
        for i in range(steps + 1)
    ]


def polygon_path(cx_in: float, cy_in: float, r_in: float, sides: int) -> list[tuple[float, float]]:
    pts = _polygon_points_mm(cx_in, cy_in, r_in, sides)
    return pts + [pts[0]]


# ------------------------------------------------------------------
# Internal geometry helpers (always work in mm / native units)
# ------------------------------------------------------------------

def _polygon_points_mm(
    cx: float, cy: float, r: float, sides: int,
    start_angle: float = -math.pi / 2,
) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(start_angle + 2 * math.pi * i / sides),
         cy + r * math.sin(start_angle + 2 * math.pi * i / sides))
        for i in range(sides)
    ]


def _star_points_mm(
    cx: float, cy: float,
    r_outer: float, r_inner: float,
    points: int,
) -> list[tuple[float, float]]:
    pts = []
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        angle = -math.pi / 2 + math.pi * i / points
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts
