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
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

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
    except _TracerNotFound:
        pass

    try:
        return _trace_potrace(str(src), dst)
    except _TracerNotFound:
        raise RuntimeError(
            "No outline tracer found. Install one:\n"
            "  pip install vtracer\n"
            "  OR: brew install potrace"
        )


# ------------------------------------------------------------------
# vtracer backend
# ------------------------------------------------------------------

def _trace_vtracer(src: str, dst: str, **kwargs) -> str:
    try:
        import vtracer  # type: ignore
    except ImportError:
        raise _TracerNotFound("vtracer")

    colormode = kwargs.pop("colormode", "binary")
    vtracer.convert_image_to_svg_py(src, dst, colormode=colormode, **kwargs)
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
