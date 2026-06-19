"""AxiDraw plotter wrapper using the official axidraw Python API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Hard physical limits for the AxiDraw Mini 2 travel area (mm)
_X_HARD_MAX_MM: float = 150.0
_Y_HARD_MAX_MM: float = 100.0

MM_PER_INCH: float = 25.4

# Preset servo positions for each supported pen angle.
# pen_pos_down / pen_pos_up — tuned for each mount angle.
PEN_ANGLE_PRESETS: dict[int, tuple[int, int]] = {
    45: (5,  30),   # 45-degree angled mount
    90: (40, 60),   # straight vertical mount
}
SUPPORTED_PEN_ANGLES = tuple(PEN_ANGLE_PRESETS.keys())

try:
    from pyaxidraw import axidraw
    AXIDRAW_AVAILABLE = True
except ImportError:
    AXIDRAW_AVAILABLE = False


@dataclass
class PlotterConfig:
    speed_pendown: int = 25       # pen-down move speed (1–100)
    speed_penup: int = 75         # pen-up move speed (1–100)
    pen_angle: int = 45           # pen mount angle in degrees (45 or 90)
    pen_pos_down: int = 5         # servo position when pen is down (0–100)
    pen_pos_up: int = 30          # servo position when pen is up (0–100)
    pen_delay_down: int = 0       # ms delay after lowering pen
    pen_delay_up: int = 0         # ms delay after raising pen
    const_speed: bool = False     # constant speed mode
    model: int = 2                # AxiDraw model (2 = Mini)
    port: Optional[str] = None    # serial port; None = auto-detect
    x_max_mm: float = 140.0       # configurable X travel limit (mm); hard cap 150
    y_max_mm: float = 90.0        # configurable Y travel limit (mm); hard cap 100

    def __post_init__(self):
        self._validate_pen_angle()
        self._validate_limits()

    def _validate_pen_angle(self):
        if self.pen_angle not in PEN_ANGLE_PRESETS:
            raise ValueError(
                f"pen_angle must be one of {list(PEN_ANGLE_PRESETS)} (got {self.pen_angle})"
            )

    def apply_angle_preset(self) -> None:
        """Overwrite pen_pos_down/up with the preset for the current pen_angle."""
        self.pen_pos_down, self.pen_pos_up = PEN_ANGLE_PRESETS[self.pen_angle]

    def _validate_limits(self):
        if not (0 < self.x_max_mm <= _X_HARD_MAX_MM):
            raise ValueError(
                f"x_max_mm must be > 0 and ≤ {_X_HARD_MAX_MM} mm (got {self.x_max_mm})"
            )
        if not (0 < self.y_max_mm <= _Y_HARD_MAX_MM):
            raise ValueError(
                f"y_max_mm must be > 0 and ≤ {_Y_HARD_MAX_MM} mm (got {self.y_max_mm})"
            )

    @property
    def x_max_in(self) -> float:
        return self.x_max_mm / MM_PER_INCH

    @property
    def y_max_in(self) -> float:
        return self.y_max_mm / MM_PER_INCH


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
        self.config._validate_limits()
        if self._ad:
            self._apply_config()

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self._ad:
            raise PlotterError("Not connected. Call connect() first.")

    def _check_bounds(self, x_in: float, y_in: float) -> None:
        if x_in < 0 or x_in > self.config.x_max_in:
            raise PlotterError(
                f"X={x_in * MM_PER_INCH:.1f} mm is out of range "
                f"(0–{self.config.x_max_mm} mm)"
            )
        if y_in < 0 or y_in > self.config.y_max_in:
            raise PlotterError(
                f"Y={y_in * MM_PER_INCH:.1f} mm is out of range "
                f"(0–{self.config.y_max_mm} mm)"
            )

    def pen_up(self) -> None:
        self._require_connection()
        self._ad.penup()

    def pen_down(self) -> None:
        self._require_connection()
        self._ad.pendown()

    def move_to(self, x: float, y: float) -> None:
        """Move to absolute position (inches) with pen up."""
        self._require_connection()
        self._check_bounds(x, y)
        self._ad.moveto(x, y)

    def line_to(self, x: float, y: float) -> None:
        """Draw to absolute position (inches) with pen down."""
        self._require_connection()
        self._check_bounds(x, y)
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
