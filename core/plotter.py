"""AxiDraw plotter wrapper using the official axidraw Python API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from pyaxidraw import axidraw
    AXIDRAW_AVAILABLE = True
except ImportError:
    AXIDRAW_AVAILABLE = False


@dataclass
class PlotterConfig:
    speed_pendown: int = 25       # pen-down move speed (1–100)
    speed_penup: int = 75         # pen-up move speed (1–100)
    pen_pos_down: int = 40        # servo position when pen is down (0–100)
    pen_pos_up: int = 60          # servo position when pen is up (0–100)
    pen_delay_down: int = 0       # ms delay after lowering pen
    pen_delay_up: int = 0         # ms delay after raising pen
    const_speed: bool = False     # constant speed mode
    model: int = 2                # AxiDraw model (2 = Mini)
    port: Optional[str] = None    # serial port; None = auto-detect


class PlotterError(Exception):
    pass


class Plotter:
    """High-level interface to the AxiDraw Mini 2."""

    def __init__(self, config: Optional[PlotterConfig] = None):
        if not AXIDRAW_AVAILABLE:
            raise PlotterError(
                "pyaxidraw is not installed. Run: pip install pyaxidraw"
            )
        self.config = config or PlotterConfig()
        self._ad: Optional[axidraw.AxiDraw] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open connection to the AxiDraw."""
        self._ad = axidraw.AxiDraw()
        self._ad.interactive()
        self._apply_config()
        if not self._ad.connect():
            self._ad = None
            raise PlotterError("Could not connect to AxiDraw. Check USB cable and port.")

    def disconnect(self) -> None:
        if self._ad:
            self._ad.disconnect()
            self._ad = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    @property
    def connected(self) -> bool:
        return self._ad is not None

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _apply_config(self) -> None:
        c = self.config
        ad = self._ad
        ad.options.speed_pendown = c.speed_pendown
        ad.options.speed_penup = c.speed_penup
        ad.options.pen_pos_down = c.pen_pos_down
        ad.options.pen_pos_up = c.pen_pos_up
        ad.options.pen_delay_down = c.pen_delay_down
        ad.options.pen_delay_up = c.pen_delay_up
        ad.options.const_speed = c.const_speed
        ad.options.model = c.model
        if c.port:
            ad.options.port = c.port

    def update_config(self, **kwargs) -> None:
        """Update config fields at runtime (re-applies to active session if connected)."""
        for k, v in kwargs.items():
            if not hasattr(self.config, k):
                raise ValueError(f"Unknown config field: {k}")
            setattr(self.config, k, v)
        if self._ad:
            self._apply_config()

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self._ad:
            raise PlotterError("Not connected. Call connect() first.")

    def pen_up(self) -> None:
        self._require_connection()
        self._ad.penup()

    def pen_down(self) -> None:
        self._require_connection()
        self._ad.pendown()

    def move_to(self, x: float, y: float) -> None:
        """Move to absolute position (inches) with pen up."""
        self._require_connection()
        self._ad.moveto(x, y)

    def line_to(self, x: float, y: float) -> None:
        """Draw to absolute position (inches) with pen down."""
        self._require_connection()
        self._ad.lineto(x, y)

    def go_home(self) -> None:
        """Return pen to home (0, 0)."""
        self._require_connection()
        self._ad.moveto(0, 0)

    def draw_path(self, points: list[tuple[float, float]]) -> None:
        """Draw a polyline through a list of (x, y) inch coordinates."""
        if not points:
            return
        self._require_connection()
        self.move_to(*points[0])
        self.pen_down()
        for x, y in points[1:]:
            self._ad.lineto(x, y)
        self.pen_up()

    # ------------------------------------------------------------------
    # SVG plotting
    # ------------------------------------------------------------------

    def plot_svg(self, svg_path: str) -> None:
        """Plot an SVG file using the axidraw plot API."""
        if not os.path.isfile(svg_path):
            raise FileNotFoundError(f"SVG file not found: {svg_path}")

        ad = axidraw.AxiDraw()
        ad.plot_setup(svg_path)
        self._apply_options_on(ad)
        ad.plot_run()

    def _apply_options_on(self, ad) -> None:
        c = self.config
        ad.options.speed_pendown = c.speed_pendown
        ad.options.speed_penup = c.speed_penup
        ad.options.pen_pos_down = c.pen_pos_down
        ad.options.pen_pos_up = c.pen_pos_up
        ad.options.pen_delay_down = c.pen_delay_down
        ad.options.pen_delay_up = c.pen_delay_up
        ad.options.const_speed = c.const_speed
        ad.options.model = c.model
        if c.port:
            ad.options.port = c.port

    # ------------------------------------------------------------------
    # Motor control
    # ------------------------------------------------------------------

    def enable_motors(self) -> None:
        self._require_connection()
        self._ad.enable_motors()

    def disable_motors(self) -> None:
        self._require_connection()
        self._ad.disable_motors()
