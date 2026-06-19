"""Raster image → SVG conversion.

Three backends are supported:
  - hatchsvg  : hatched plotter-optimised SVG (pen-lift minimised serpentine paths)
  - vtracer   : outline/colour tracing via the vtracer library
  - potrace   : greyscale outline tracing via the potrace CLI

hatch_to_svg()  — dedicated hatchsvg entry-point (colour layers, hatch lines)
trace_to_svg()  — outline tracing; tries vtracer → potrace fallback chain
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

# Hard physical limits — kept here so image_trace stays self-contained
_X_HARD_MAX_MM: float = 150.0
_Y_HARD_MAX_MM: float = 100.0
_MM_PER_IN: float = 25.4
_PX_PER_IN: float = 96.0   # SVG default DPI


# ------------------------------------------------------------------
# SVG bounds fitting
# ------------------------------------------------------------------

def fit_svg_to_bounds(
    svg_path: str,
    x_max_mm: float = 140.0,
    y_max_mm: float = 90.0,
    scale_pct: float = 90.0,
) -> str:
    """
    Read an SVG file, scale its content to fill `scale_pct` percent of the
    plotter's travel area, centre it, and write the result back in place.

    Returns the same svg_path (modified in place).

    Args:
        svg_path   : path to the SVG file to modify
        x_max_mm   : plotter X travel limit in mm (from config)
        y_max_mm   : plotter Y travel limit in mm (from config)
        scale_pct  : how much of the travel area to fill (1–100, default 90)

    Raises:
        ValueError : if scale_pct is out of range or SVG has no readable viewBox
    """
    if not (1 <= scale_pct <= 100):
        raise ValueError(f"scale_pct must be 1–100 (got {scale_pct})")

    # Clamp limits to hard caps
    x_limit_mm = min(x_max_mm, _X_HARD_MAX_MM)
    y_limit_mm = min(y_max_mm, _Y_HARD_MAX_MM)

    frac = scale_pct / 100.0
    target_w_mm = x_limit_mm * frac
    target_h_mm = y_limit_mm * frac

    svg_text = Path(svg_path).read_text(encoding="utf-8")

    # Extract viewBox — preferred over width/height as it covers all tracers
    vb_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_text)
    if not vb_match:
        # Fall back to width/height attributes (inches or px)
        w_match = re.search(r'\bwidth=["\']([^"\']+)["\']', svg_text)
        h_match = re.search(r'\bheight=["\']([^"\']+)["\']', svg_text)
        if not w_match or not h_match:
            raise ValueError("SVG has no viewBox, width, or height — cannot fit to bounds.")
        src_w_px = _parse_svg_length(w_match.group(1))
        src_h_px = _parse_svg_length(h_match.group(1))
        vb_x, vb_y = 0.0, 0.0
    else:
        parts = vb_match.group(1).split()
        vb_x, vb_y, src_w_px, src_h_px = (float(p) for p in parts)

    if src_w_px <= 0 or src_h_px <= 0:
        raise ValueError(f"SVG has zero or negative dimensions ({src_w_px} × {src_h_px}).")

    # Convert source pixel dimensions to mm (96 dpi)
    src_w_mm = src_w_px / _PX_PER_IN * _MM_PER_IN
    src_h_mm = src_h_px / _PX_PER_IN * _MM_PER_IN

    # Uniform scale to fit target box while preserving aspect ratio
    scale = min(target_w_mm / src_w_mm, target_h_mm / src_h_mm)

    out_w_mm = src_w_mm * scale
    out_h_mm = src_h_mm * scale

    # Centre inside the travel area
    offset_x_mm = (x_limit_mm - out_w_mm) / 2.0
    offset_y_mm = (y_limit_mm - out_h_mm) / 2.0

    # Convert offsets to SVG px
    offset_x_px = offset_x_mm / _MM_PER_IN * _PX_PER_IN
    offset_y_px = offset_y_mm / _MM_PER_IN * _PX_PER_IN

    canvas_w_px = x_limit_mm / _MM_PER_IN * _PX_PER_IN
    canvas_h_px = y_limit_mm / _MM_PER_IN * _PX_PER_IN
    canvas_w_in = x_limit_mm / _MM_PER_IN
    canvas_h_in = y_limit_mm / _MM_PER_IN

    # Wrap all existing content in a transform group: translate then scale
    # The translate moves the (possibly non-zero) viewBox origin to our offset.
    tx = offset_x_px - vb_x * scale
    ty = offset_y_px - vb_y * scale
    transform = f"translate({tx:.4f},{ty:.4f}) scale({scale:.6f})"

    # Strip the existing <svg ...> opening tag and reconstruct it
    svg_text = re.sub(
        r'<svg[^>]*>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{canvas_w_in:.4f}in" height="{canvas_h_in:.4f}in" '
            f'viewBox="0 0 {canvas_w_px:.2f} {canvas_h_px:.2f}">'
            f'\n<g transform="{transform}">'
        ),
        svg_text,
        count=1,
        flags=re.DOTALL,
    )
    # Close the wrapping group before </svg>
    svg_text = re.sub(r'</svg>', '</g>\n</svg>', svg_text, count=1)

    Path(svg_path).write_text(svg_text, encoding="utf-8")
    return svg_path


def _parse_svg_length(s: str) -> float:
    """Convert an SVG length string (e.g. '210mm', '595.28', '8.5in') to px."""
    s = s.strip()
    if s.endswith("mm"):
        return float(s[:-2]) / _MM_PER_IN * _PX_PER_IN
    if s.endswith("in"):
        return float(s[:-2]) * _PX_PER_IN
    if s.endswith("cm"):
        return float(s[:-2]) / 10.0 / _MM_PER_IN * _PX_PER_IN
    if s.endswith("pt"):
        return float(s[:-2]) / 72.0 * _PX_PER_IN
    # Bare number treated as px
    return float(re.sub(r'[^\d.]', '', s) or "0")

# hatchsvg supports a broader set of raster formats than vtracer/potrace
SUPPORTED_RASTER = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tiff", ".tif"}
# subset accepted by the outline tracers (vtracer / potrace)
_OUTLINE_RASTER = {".jpg", ".jpeg", ".png", ".bmp"}


def is_raster(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_RASTER


# ------------------------------------------------------------------
# hatchsvg backend
# ------------------------------------------------------------------

def hatch_to_svg(
    image_path: str,
    output_path: str | None = None,
    *,
    max_palette: int = 12,
    line_step: int = 4,
    stroke_width: float = 0.5,
    outline_width: float = 0.8,
    hatch_angle: float = 45.0,
    scale: float = 1.0,
    continuous_paths: bool = True,
    arc_radius: float = 2.0,
    skip_bg: bool = False,
    separate_outline: bool = False,
    optimize_travel: bool = True,
) -> str:
    """
    Convert a raster image to a hatched plotter-optimised SVG using hatchsvg.

    Returns the path to the generated SVG file.

    Parameters
    ----------
    image_path       : source raster (PNG/JPG/BMP/WebP/GIF/TIFF)
    output_path      : destination SVG; defaults to <source>.svg
    max_palette      : max number of colour layers (default 12)
    line_step        : spacing between hatch lines in pixels (default 4)
    stroke_width     : SVG stroke width for hatch lines (default 0.5)
    outline_width    : SVG stroke width for outlines (default 0.8)
    hatch_angle      : angle of hatch lines in degrees (default 45.0)
    scale            : image scale factor before processing (default 1.0)
    continuous_paths : serpentine paths to minimise pen lifts (default True)
    arc_radius       : arc smoothing radius at U-turns (default 2.0)
    skip_bg          : skip the background/dominant colour layer (default False)
    separate_outline : write outline as a separate path element (default False)
    optimize_travel  : reorder layers to minimise pen-up travel (default True)
    """
    try:
        from hatchsvg.core import process_image_to_hatched_svg, RenderParams  # type: ignore
    except ImportError:
        raise RuntimeError("hatchsvg is not installed. Run: pip install hatchsvg")

    src = Path(image_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if src.suffix.lower() not in SUPPORTED_RASTER:
        raise ValueError(f"Unsupported format: {src.suffix}. Supported: {SUPPORTED_RASTER}")

    dst = Path(output_path) if output_path else src.with_suffix(".svg")

    params = RenderParams(
        max_palette=max_palette,
        line_step=line_step,
        stroke_width=stroke_width,
        outline_width=outline_width,
        hatch_angle=hatch_angle,
        scale=scale,
        continuous_paths=continuous_paths,
        arc_radius=arc_radius,
        skip_bg=skip_bg,
        separate_outline=separate_outline,
    )

    process_image_to_hatched_svg(
        input_path=src,
        output_path=dst,
        params=params,
        optimize_travel=optimize_travel,
    )

    return str(dst)


# ------------------------------------------------------------------
# Outline tracing (vtracer → potrace fallback)
# ------------------------------------------------------------------

def trace_to_svg(
    image_path: str,
    output_path: str | None = None,
    *,
    colormode: str = "binary",
    filter_speckle: int = 4,
    color_precision: int = 6,
    layer_difference: int = 16,
    corner_threshold: int = 60,
    length_threshold: float = 4.0,
    max_iterations: int = 10,
    splice_threshold: int = 45,
    path_precision: int = 3,
) -> str:
    """
    Convert a raster image to an outline SVG.

    Tries vtracer first; falls back to potrace.

    Returns the path to the generated SVG file.
    """
    src = Path(image_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if src.suffix.lower() not in _OUTLINE_RASTER:
        raise ValueError(
            f"Unsupported format for outline tracing: {src.suffix}. "
            f"Use {_OUTLINE_RASTER}, or use hatch_to_svg() for WebP/GIF/TIFF."
        )

    dst = str(Path(output_path) if output_path else src.with_suffix(".svg"))

    vtracer_error: str | None = None
    try:
        return _trace_vtracer(
            str(src), dst,
            colormode=colormode,
            filter_speckle=filter_speckle,
            color_precision=color_precision,
            layer_difference=layer_difference,
            corner_threshold=corner_threshold,
            length_threshold=length_threshold,
            max_iterations=max_iterations,
            splice_threshold=splice_threshold,
            path_precision=path_precision,
        )
    except _TracerNotFound as e:
        vtracer_error = str(e)

    # vtracer unavailable or crashed — fall back to potrace
    try:
        return _trace_potrace(str(src), dst)
    except _TracerNotFound:
        detail = f" (vtracer error: {vtracer_error})" if vtracer_error and "not installed" not in vtracer_error else ""
        raise RuntimeError(
            f"No working outline tracer found{detail}.\n"
            "Install one:\n"
            "  pip install vtracer\n"
            "  OR: brew install potrace"
        )


# ------------------------------------------------------------------
# vtracer backend — run in a subprocess to isolate Rust segfaults
# ------------------------------------------------------------------

def _trace_vtracer(src: str, dst: str, **kwargs) -> str:
    """
    Run vtracer in an isolated subprocess. If vtracer is not installed, or if
    the subprocess crashes (segfault, non-zero exit), raise _TracerNotFound so
    the caller falls back to potrace.
    """
    import sys
    colormode = kwargs.pop("colormode", "binary")

    # Quick import check in the current process — avoids spawning if not installed
    try:
        import vtracer as _vt  # noqa: F401
    except ImportError:
        raise _TracerNotFound("vtracer")

    # Build a small inline script so vtracer runs in its own process.
    # A Rust segfault there won't kill the GUI.
    script = (
        "import sys, vtracer\n"
        "vtracer.convert_image_to_svg_py("
        f"  {src!r}, {dst!r}, colormode={colormode!r}"
        ")\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise _TracerNotFound(
            f"vtracer subprocess failed (exit {result.returncode}): {stderr or 'unknown error'}"
        )
    return dst


# ------------------------------------------------------------------
# potrace backend (subprocess)
# ------------------------------------------------------------------

def _trace_potrace(src: str, dst: str) -> str:
    potrace = _find_executable("potrace")
    if not potrace:
        raise _TracerNotFound("potrace")

    with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
        bmp_path = tmp.name

    try:
        Image.open(src).convert("L").save(bmp_path, format="BMP")
        subprocess.run(
            [potrace, "--svg", "-o", dst, bmp_path],
            check=True,
            capture_output=True,
        )
    finally:
        os.unlink(bmp_path)

    return dst


def _find_executable(name: str) -> str | None:
    result = subprocess.run(["which", name], capture_output=True, text=True)
    path = result.stdout.strip()
    return path if path else None


class _TracerNotFound(Exception):
    pass
