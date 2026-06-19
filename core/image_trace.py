"""Raster image (JPEG/PNG/BMP) → SVG conversion via vtracer or potrace."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

SUPPORTED_RASTER = {".jpg", ".jpeg", ".png", ".bmp"}


def is_raster(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_RASTER


def trace_to_svg(
    image_path: str,
    output_path: str | None = None,
    *,
    # vtracer options
    colormode: str = "binary",   # "binary" | "color" | "layered"
    filter_speckle: int = 4,     # remove noise specks smaller than N px
    color_precision: int = 6,
    layer_difference: int = 16,
    corner_threshold: int = 60,
    length_threshold: float = 4.0,
    max_iterations: int = 10,
    splice_threshold: int = 45,
    path_precision: int = 3,
) -> str:
    """
    Convert a raster image to SVG.

    Returns the path to the generated SVG file.
    Tries vtracer first; falls back to potrace (requires separate install).
    """
    src = Path(image_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if src.suffix.lower() not in SUPPORTED_RASTER:
        raise ValueError(f"Unsupported format: {src.suffix}. Use {SUPPORTED_RASTER}")

    if output_path is None:
        output_path = str(src.with_suffix(".svg"))

    try:
        return _trace_vtracer(
            str(src),
            output_path,
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
        return _trace_potrace(str(src), output_path)
    except _TracerNotFound:
        raise RuntimeError(
            "No tracer found. Install one:\n"
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
    vtracer.convert_image_to_svg_py(
        src,
        dst,
        colormode=colormode,
        **kwargs,
    )
    return dst


# ------------------------------------------------------------------
# potrace backend (subprocess)
# ------------------------------------------------------------------

def _trace_potrace(src: str, dst: str) -> str:
    potrace = _find_executable("potrace")
    if not potrace:
        raise _TracerNotFound("potrace")

    # potrace needs BMP input
    with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
        bmp_path = tmp.name

    try:
        img = Image.open(src).convert("L")  # greyscale
        img.save(bmp_path, format="BMP")

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
