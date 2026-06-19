"""Load and save PlotterConfig from/to axidraw-mini2-plotter.cfg."""

from __future__ import annotations

import configparser
from pathlib import Path

from core.plotter import PlotterConfig

# Config file lives alongside main.py at the project root
_CFG_PATH = Path(__file__).parent.parent / "axidraw-mini2-plotter.cfg"


def config_path() -> Path:
    return _CFG_PATH


def load_config(path: Path | str | None = None) -> PlotterConfig:
    """
    Read the .cfg file and return a PlotterConfig.
    Missing keys fall back to PlotterConfig field defaults.
    """
    p = Path(path) if path else _CFG_PATH
    cp = configparser.ConfigParser()
    cp.read(p)

    def _int(section, key, default):
        try:
            return cp.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def _float(section, key, default):
        try:
            return cp.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def _bool(section, key, default):
        try:
            return cp.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def _str(section, key, default):
        try:
            val = cp.get(section, key).strip()
            return val if val else default
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    return PlotterConfig(
        speed_pendown  = _int  ("motion", "speed_pendown",  25),
        speed_penup    = _int  ("motion", "speed_penup",    75),
        pen_delay_down = _int  ("motion", "pen_delay_down",  0),
        pen_delay_up   = _int  ("motion", "pen_delay_up",    0),
        const_speed    = _bool ("motion", "const_speed",  False),
        pen_pos_down   = _int  ("pen",    "pen_pos_down",    5),
        pen_pos_up     = _int  ("pen",    "pen_pos_up",     30),
        x_max_mm       = _float("travel", "x_max_mm",    140.0),
        y_max_mm       = _float("travel", "y_max_mm",     90.0),
        model          = _int  ("device", "model",            2),
        port           = _str  ("device", "port",         None),
    )


def save_config(cfg: PlotterConfig, path: Path | str | None = None) -> None:
    """Write a PlotterConfig back to the .cfg file, preserving section comments."""
    p = Path(path) if path else _CFG_PATH

    cp = configparser.ConfigParser()
    # Read existing file first so we don't clobber unrecognised keys
    cp.read(p)

    def _ensure(section):
        if not cp.has_section(section):
            cp.add_section(section)

    _ensure("motion")
    cp.set("motion", "speed_pendown",  str(cfg.speed_pendown))
    cp.set("motion", "speed_penup",    str(cfg.speed_penup))
    cp.set("motion", "pen_delay_down", str(cfg.pen_delay_down))
    cp.set("motion", "pen_delay_up",   str(cfg.pen_delay_up))
    cp.set("motion", "const_speed",    str(cfg.const_speed).lower())

    _ensure("pen")
    cp.set("pen", "pen_pos_down", str(cfg.pen_pos_down))
    cp.set("pen", "pen_pos_up",   str(cfg.pen_pos_up))

    _ensure("travel")
    cp.set("travel", "x_max_mm", str(cfg.x_max_mm))
    cp.set("travel", "y_max_mm", str(cfg.y_max_mm))

    _ensure("device")
    cp.set("device", "model", str(cfg.model))
    cp.set("device", "port",  cfg.port if cfg.port else "")

    with open(p, "w") as f:
        cp.write(f)
