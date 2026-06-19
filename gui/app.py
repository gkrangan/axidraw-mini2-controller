"""AxiDraw Mini 2 — customtkinter GUI."""

from __future__ import annotations

import os
import threading
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from core.plotter import Plotter, PlotterConfig, PlotterError, PEN_ANGLE_PRESETS
from core.image_trace import is_raster, trace_to_svg, hatch_to_svg, fit_svg_to_bounds, SUPPORTED_RASTER
from core.config_io import load_config, save_config, config_path
from core import shapes

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_RASTER_TYPES = [("Image files", " ".join(f"*{e}" for e in sorted(SUPPORTED_RASTER)))]
_SVG_TYPES = [("SVG files", "*.svg")]
_ALL_TYPES = [
    ("Supported files", "*.svg *.jpg *.jpeg *.png *.bmp"),
    ("SVG", "*.svg"),
    ("Images", "*.jpg *.jpeg *.png *.bmp"),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AxiDraw Mini 2 Controller")
        self.geometry("900x680")
        self.resizable(True, True)

        self._plotter: Optional[Plotter] = None
        self._cfg = load_config()
        self._file_path: Optional[str] = None   # currently loaded file
        self._svg_path: Optional[str] = None    # SVG ready to plot (may be traced)
        self._cancel_event = threading.Event()  # set to request job cancellation
        self._job_running = False               # True while a plot/shape job is active

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- left sidebar ----
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(sidebar, text="AxiDraw Mini 2", font=("", 18, "bold")).grid(
            row=0, column=0, padx=16, pady=(20, 4), sticky="w"
        )
        ctk.CTkLabel(sidebar, text="Drawing Robot Controller", font=("", 11)).grid(
            row=1, column=0, padx=16, pady=(0, 20), sticky="w"
        )

        # Connection
        self._btn_connect = ctk.CTkButton(sidebar, text="Connect", command=self._toggle_connect)
        self._btn_connect.grid(row=2, column=0, padx=16, pady=6, sticky="ew")

        self._lbl_status = ctk.CTkLabel(sidebar, text="● Disconnected", text_color="red")
        self._lbl_status.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkFrame(sidebar, height=1, fg_color="#444").grid(
            row=4, column=0, padx=12, pady=4, sticky="ew"
        )

        # Pen controls
        ctk.CTkLabel(sidebar, text="Pen", font=("", 13, "bold")).grid(
            row=5, column=0, padx=16, pady=(8, 2), sticky="w"
        )
        pen_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        pen_row.grid(row=6, column=0, padx=16, pady=4, sticky="ew")
        ctk.CTkButton(pen_row, text="Up", width=80, command=self._pen_up).pack(side="left", padx=(0, 4))
        ctk.CTkButton(pen_row, text="Down", width=80, command=self._pen_down).pack(side="left")

        # Movement
        ctk.CTkLabel(sidebar, text="Movement", font=("", 13, "bold")).grid(
            row=7, column=0, padx=16, pady=(12, 2), sticky="w"
        )
        ctk.CTkButton(sidebar, text="Go Home (0, 0)", command=self._go_home).grid(
            row=8, column=0, padx=16, pady=4, sticky="ew"
        )
        ctk.CTkButton(sidebar, text="Motors OFF", command=self._motors_off).grid(
            row=9, column=0, padx=16, pady=4, sticky="ew"
        )

        ctk.CTkFrame(sidebar, height=1, fg_color="#444").grid(
            row=10, column=0, padx=12, pady=4, sticky="ew"
        )

        # Plot controls
        ctk.CTkLabel(sidebar, text="Plot", font=("", 13, "bold")).grid(
            row=11, column=0, padx=16, pady=(8, 2), sticky="w"
        )
        ctk.CTkButton(sidebar, text="Load File…", command=self._load_file).grid(
            row=12, column=0, padx=16, pady=4, sticky="ew"
        )
        self._lbl_file = ctk.CTkLabel(sidebar, text="No file loaded", wraplength=190,
                                       font=("", 10), text_color="gray")
        self._lbl_file.grid(row=13, column=0, padx=16, pady=(0, 4), sticky="w")

        self._btn_plot = ctk.CTkButton(
            sidebar, text="▶  Plot", fg_color="green", hover_color="#1a7a1a",
            command=self._plot_file
        )
        self._btn_plot.grid(row=14, column=0, padx=16, pady=6, sticky="ew")

        self._btn_cancel = ctk.CTkButton(
            sidebar, text="⬛  Cancel Job",
            fg_color="#8b0000", hover_color="#5a0000",
            command=self._cancel_job,
            state="disabled",
        )
        self._btn_cancel.grid(row=15, column=0, padx=16, pady=(0, 6), sticky="ew")

        # Theme toggle at bottom
        ctk.CTkLabel(sidebar, text="Appearance").grid(row=21, column=0, padx=16, pady=(0, 2), sticky="w")
        ctk.CTkOptionMenu(sidebar, values=["Dark", "Light", "System"],
                          command=ctk.set_appearance_mode).grid(
            row=22, column=0, padx=16, pady=(0, 16), sticky="ew"
        )

        # ---- main area (tabs) ----
        tabs = ctk.CTkTabview(self)
        tabs.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        tabs.add("Draw Shapes")
        tabs.add("Image Trace")
        tabs.add("Manual Control")
        tabs.add("Settings")
        tabs.add("Log")

        self._build_shapes_tab(tabs.tab("Draw Shapes"))
        self._build_trace_tab(tabs.tab("Image Trace"))
        self._build_manual_tab(tabs.tab("Manual Control"))
        self._build_settings_tab(tabs.tab("Settings"))
        self._build_log_tab(tabs.tab("Log"))

    # ------------------------------------------------------------------
    # Shapes tab
    # ------------------------------------------------------------------

    # Defaults for each unit — (mm_val, in_val)
    _SHAPE_DEFAULTS = {
        "X":      ("10",   "0.4"),
        "Y":      ("10",   "0.4"),
        "W":      ("50",   "2.0"),
        "H":      ("30",   "1.2"),
        "Side":   ("40",   "1.6"),
        "CX":     ("50",   "2.0"),
        "CY":     ("45",   "1.8"),
        "R":      ("20",   "0.8"),
        "RX":     ("25",   "1.0"),
        "RY":     ("15",   "0.6"),
        "Sides":  ("6",    "6"),
        "Points": ("5",    "5"),
        "R Out":  ("20",   "0.8"),
        "R In":   ("10",   "0.4"),
        "X1":     ("10",   "0.4"),
        "Y1":     ("10",   "0.4"),
        "X2":     ("80",   "3.1"),
        "Y2":     ("60",   "2.4"),
        "X (pos)": ("10",  "0.4"),
        "Y (pos)": ("10",  "0.4"),
        "Size (pt)": ("12", "12"),
    }

    def _build_shapes_tab(self, parent):
        # Wrap in a scrollable frame so all shapes fit
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure((0, 1, 2, 3), weight=1)
        p = scroll  # shorthand

        row = 0
        ctk.CTkLabel(p, text="Generate & Plot Shapes", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=4, pady=(8, 4), sticky="w", padx=8
        )

        # Unit toggle
        row += 1
        unit_frame = ctk.CTkFrame(p, fg_color="transparent")
        unit_frame.grid(row=row, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")
        ctk.CTkLabel(unit_frame, text="Units:", font=("", 12)).pack(side="left", padx=(0, 6))
        self._shape_unit = ctk.CTkSegmentedButton(
            unit_frame, values=["mm", "in"],
            command=self._on_shape_unit_change, width=100
        )
        self._shape_unit.set("mm")
        self._shape_unit.pack(side="left")

        # Holds (CTkLabel widget, field_key) so we can relabel on unit change
        self._shape_unit_labels: list[tuple] = []
        # Holds (CTkEntry widget, field_key) so we can swap defaults on unit change
        self._shape_unit_entries: list[tuple] = []

        def section(title, top_pad=12):
            nonlocal row
            row += 1
            ctk.CTkFrame(p, height=1, fg_color="#444").grid(
                row=row, column=0, columnspan=4, padx=8, pady=(top_pad, 0), sticky="ew"
            )
            row += 1
            ctk.CTkLabel(p, text=title, font=("", 12, "bold")).grid(
                row=row, column=0, columnspan=4, padx=8, pady=(4, 2), sticky="w"
            )

        def fields(keys: list[str], cols=4) -> dict:
            """Add a row of labelled entry fields; returns {key: CTkEntry}."""
            nonlocal row
            row += 1
            entries: dict[str, ctk.CTkEntry] = {}
            for col_idx, key in enumerate(keys):
                col = col_idx % cols
                if col_idx > 0 and col == 0:
                    row += 1
                unit = self._shape_unit.get()
                defs = self._SHAPE_DEFAULTS.get(key, ("", ""))
                default = defs[0] if unit == "mm" else defs[1]
                suffix = "" if key in ("Sides", "Points", "Size (pt)") else f" ({unit})"
                lbl_text = key + suffix
                lbl = ctk.CTkLabel(p, text=lbl_text, font=("", 10))
                lbl.grid(row=row, column=col, padx=(8, 2), pady=(4, 0), sticky="w")
                row += 1
                e = ctk.CTkEntry(p, width=80)
                e.insert(0, default)
                e.grid(row=row, column=col, padx=(8, 2), pady=(0, 4), sticky="ew")
                entries[key] = e
                if key not in ("Sides", "Points", "Size (pt)"):
                    self._shape_unit_labels.append((lbl, key))
                    self._shape_unit_entries.append((e, key))
                row -= 1  # stay on same row for next col
            row += 1      # advance past entry row
            return entries

        def plot_btn(text, cmd):
            nonlocal row
            row += 1
            ctk.CTkButton(p, text=text, command=cmd).grid(
                row=row, column=0, columnspan=4, padx=8, pady=(2, 6), sticky="ew"
            )

        # ---- Rectangle ----
        section("Rectangle", top_pad=4)
        self._rect = fields(["X", "Y", "W", "H"])
        plot_btn("Plot Rectangle", self._plot_rect)

        # ---- Square ----
        section("Square")
        self._sqr = fields(["X", "Y", "Side"])
        plot_btn("Plot Square", self._plot_square)

        # ---- Circle ----
        section("Circle")
        self._circ = fields(["CX", "CY", "R"])
        plot_btn("Plot Circle", self._plot_circle)

        # ---- Ellipse ----
        section("Ellipse")
        self._ellipse = fields(["CX", "CY", "RX", "RY"])
        plot_btn("Plot Ellipse", self._plot_ellipse)

        # ---- Triangle ----
        section("Equilateral Triangle")
        self._tri = fields(["CX", "CY", "Side"])
        plot_btn("Plot Triangle", self._plot_triangle)

        # ---- Regular Polygon ----
        section("Regular Polygon")
        self._poly = fields(["CX", "CY", "R", "Sides"])
        plot_btn("Plot Polygon", self._plot_polygon)

        # ---- Star ----
        section("Star")
        self._star = fields(["CX", "CY", "R Out", "R In", "Points"])
        plot_btn("Plot Star", self._plot_star)

        # ---- Line ----
        section("Line")
        self._line = fields(["X1", "Y1", "X2", "Y2"])
        plot_btn("Plot Line", self._plot_line)

        # ---- Text ----
        section("Text")
        row += 1
        self._text_entry = ctk.CTkEntry(p, placeholder_text="Text to draw")
        self._text_entry.grid(row=row, column=0, columnspan=4, padx=8, pady=4, sticky="ew")
        self._txt = fields(["X (pos)", "Y (pos)", "Size (pt)"])
        _HERSHEY_FONTS = ["futural", "futuram", "cursive", "gothgbt", "gothgrt", "scripts", "cyrillic"]
        row += 1
        ctk.CTkLabel(p, text="Font", font=("", 10)).grid(row=row, column=0, padx=(8,2), sticky="w")
        self._txt_font = ctk.CTkOptionMenu(p, values=_HERSHEY_FONTS, width=140)
        self._txt_font.set("futural")
        self._txt_font.grid(row=row, column=1, columnspan=2, padx=4, pady=4, sticky="w")
        plot_btn("Plot Text", self._plot_text)

    def _on_shape_unit_change(self, unit: str):
        """Update all field labels and swap defaults when unit toggle changes."""
        for lbl, key in self._shape_unit_labels:
            lbl.configure(text=f"{key} ({unit})")
        defs_idx = 0 if unit == "mm" else 1
        for e, key in self._shape_unit_entries:
            defs = self._SHAPE_DEFAULTS.get(key, ("", ""))
            e.delete(0, "end")
            e.insert(0, defs[defs_idx])

    def _field_row(self, parent, row, labels, defaults, start_col=0):
        entries = {}
        for i, (lbl, val) in enumerate(zip(labels, defaults)):
            col = start_col + i
            ctk.CTkLabel(parent, text=lbl, font=("", 10)).grid(
                row=row, column=col, padx=(8, 2), sticky="w"
            )
            e = ctk.CTkEntry(parent, width=70)
            e.insert(0, val)
            e.grid(row=row + 1 if start_col == 0 else row, column=col, padx=(8, 2), pady=2)
            entries[lbl] = e
        return entries

    # ------------------------------------------------------------------
    # Image trace tab
    # ------------------------------------------------------------------

    def _build_trace_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        row = 0

        ctk.CTkLabel(parent, text="Raster → SVG Trace", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(8, 8), sticky="w", padx=8
        )
        row += 1

        ctk.CTkButton(
            parent,
            text="Open Image (JPG/PNG/BMP/WebP/GIF/TIFF)…",
            command=self._open_raster,
        ).grid(row=row, column=0, columnspan=2, padx=8, pady=4, sticky="ew")
        row += 1

        self._lbl_trace_src = ctk.CTkLabel(parent, text="No image selected",
                                            font=("", 10), text_color="gray")
        self._lbl_trace_src.grid(row=row, column=0, columnspan=2, padx=8,
                                  pady=(0, 10), sticky="w")
        row += 1

        # ---- Scale to plotter area ----
        ctk.CTkLabel(parent, text="Scale to plotter area", font=("", 12, "bold")).grid(
            row=row, column=0, padx=8, pady=(4, 2), sticky="w"
        )
        row += 1
        scale_frame = ctk.CTkFrame(parent, fg_color="transparent")
        scale_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        scale_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(scale_frame, text="Fill % of travel area", font=("", 10)).grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )
        self._trace_scale_pct = ctk.CTkEntry(scale_frame, width=60)
        self._trace_scale_pct.insert(0, "90")
        self._trace_scale_pct.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(scale_frame, text="% (1–100)  — image centred, aspect ratio preserved",
                     font=("", 10), text_color="gray").grid(row=0, column=2, padx=8, sticky="w")
        row += 1

        # ---- Backend selector ----
        ctk.CTkLabel(parent, text="Tracing backend", font=("", 12, "bold")).grid(
            row=row, column=0, padx=8, pady=(4, 2), sticky="w"
        )
        self._trace_backend = ctk.CTkOptionMenu(
            parent,
            values=["vtracer / potrace (outline)", "hatchsvg (hatched)"],
            command=self._on_trace_backend_changed,
        )
        self._trace_backend.set("vtracer / potrace (outline)")
        self._trace_backend.grid(row=row, column=1, padx=8, pady=(4, 2), sticky="ew")
        row += 1

        # ---- outline tracer options (shown by default) ----
        self._outline_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._outline_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=4)
        self._outline_frame.grid_columnconfigure(1, weight=1)
        self._build_outline_options(self._outline_frame)
        row += 1

        # ---- hatchsvg options (hidden by default) ----
        self._hatch_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._hatch_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=4)
        self._hatch_frame.grid_columnconfigure(1, weight=1)
        self._build_hatch_options(self._hatch_frame)
        self._hatch_frame.grid_remove()   # hidden until backend switches
        row += 1

        # ---- action buttons ----
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=row, column=0, columnspan=2, padx=8, pady=10, sticky="ew")
        ctk.CTkButton(btn_row, text="Trace to SVG",
                      command=self._run_trace).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Trace & Plot", fg_color="green",
                      command=self._trace_and_plot).pack(side="left")
        row += 1

        self._lbl_trace_out = ctk.CTkLabel(parent, text="", font=("", 10), text_color="gray")
        self._lbl_trace_out.grid(row=row, column=0, columnspan=2, padx=8, sticky="w")

    def _build_hatch_options(self, parent):
        fields = [
            ("Hatch angle (°)",      "_hatch_angle",    "45.0"),
            ("Line step (px)",       "_hatch_line_step", "4"),
            ("Max palette colours",  "_hatch_palette",  "12"),
            ("Stroke width",         "_hatch_stroke",   "0.5"),
            ("Scale",                "_hatch_scale",    "1.0"),
            ("Arc radius (U-turns)", "_hatch_arc",      "2.0"),
        ]
        for i, (label, attr, default) in enumerate(fields):
            ctk.CTkLabel(parent, text=label).grid(row=i, column=0, padx=8, pady=4, sticky="w")
            e = ctk.CTkEntry(parent)
            e.insert(0, default)
            e.grid(row=i, column=1, padx=8, pady=4, sticky="ew")
            setattr(self, attr, e)

        r = len(fields)
        self._hatch_continuous = ctk.CTkCheckBox(parent, text="Continuous paths (fewer pen lifts)")
        self._hatch_continuous.select()
        self._hatch_continuous.grid(row=r, column=0, columnspan=2, padx=8, pady=4, sticky="w")

        self._hatch_skip_bg = ctk.CTkCheckBox(parent, text="Skip background colour")
        self._hatch_skip_bg.grid(row=r + 1, column=0, columnspan=2, padx=8, pady=4, sticky="w")

        self._hatch_optimize = ctk.CTkCheckBox(parent, text="Optimise layer travel order")
        self._hatch_optimize.select()
        self._hatch_optimize.grid(row=r + 2, column=0, columnspan=2, padx=8, pady=4, sticky="w")

    def _build_outline_options(self, parent):
        ctk.CTkLabel(parent, text="Color mode").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self._colormode = ctk.CTkOptionMenu(parent, values=["binary", "color", "layered"])
        self._colormode.grid(row=0, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(parent, text="Filter speckle (px)").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        self._speckle = ctk.CTkEntry(parent, width=80)
        self._speckle.insert(0, "4")
        self._speckle.grid(row=1, column=1, padx=8, pady=4, sticky="w")

    def _on_trace_backend_changed(self, choice: str):
        if "hatchsvg" in choice:
            self._hatch_frame.grid()
            self._outline_frame.grid_remove()
        else:
            self._outline_frame.grid()
            self._hatch_frame.grid_remove()

    # ------------------------------------------------------------------
    # Manual Control tab
    # ------------------------------------------------------------------

    def _build_manual_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(parent, text="Manual Control", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(8, 4), sticky="w", padx=8
        )
        row += 1

        # ---- Position & home display ----
        pos_frame = ctk.CTkFrame(parent)
        pos_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
        pos_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(pos_frame, text="Position", font=("", 11, "bold")).grid(
            row=0, column=0, columnspan=2, padx=8, pady=(6, 2), sticky="w"
        )
        ctk.CTkLabel(pos_frame, text="Home", font=("", 11, "bold")).grid(
            row=0, column=2, columnspan=2, padx=8, pady=(6, 2), sticky="w"
        )
        for col, lbl in enumerate(["X (mm)", "Y (mm)", "Home X (mm)", "Home Y (mm)"]):
            ctk.CTkLabel(pos_frame, text=lbl, font=("", 10), text_color="gray").grid(
                row=1, column=col, padx=8, sticky="w"
            )
        self._lbl_pos_x    = ctk.CTkLabel(pos_frame, text="0.00", font=("Courier", 12))
        self._lbl_pos_y    = ctk.CTkLabel(pos_frame, text="0.00", font=("Courier", 12))
        self._lbl_home_x   = ctk.CTkLabel(pos_frame, text="0.00", font=("Courier", 12))
        self._lbl_home_y   = ctk.CTkLabel(pos_frame, text="0.00", font=("Courier", 12))
        self._lbl_pos_x.grid (row=2, column=0, padx=8, pady=(0, 8), sticky="w")
        self._lbl_pos_y.grid (row=2, column=1, padx=8, pady=(0, 8), sticky="w")
        self._lbl_home_x.grid(row=2, column=2, padx=8, pady=(0, 8), sticky="w")
        self._lbl_home_y.grid(row=2, column=3, padx=8, pady=(0, 8), sticky="w")
        row += 1

        # ---- Pen control ----
        ctk.CTkLabel(parent, text="Pen", font=("", 12, "bold")).grid(
            row=row, column=0, columnspan=2, padx=8, pady=(4, 2), sticky="w"
        )
        row += 1
        pen_frame = ctk.CTkFrame(parent, fg_color="transparent")
        pen_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        self._btn_pen_up   = ctk.CTkButton(pen_frame, text="Pen Up",   width=120,
                                            fg_color="#1f538d",
                                            command=self._manual_pen_up)
        self._btn_pen_down = ctk.CTkButton(pen_frame, text="Pen Down", width=120,
                                            fg_color="#8d1f1f",
                                            command=self._manual_pen_down)
        self._btn_pen_up.pack(side="left", padx=(0, 8))
        self._btn_pen_down.pack(side="left")
        row += 1

        # ---- Motor control ----
        ctk.CTkLabel(parent, text="Motors", font=("", 12, "bold")).grid(
            row=row, column=0, columnspan=2, padx=8, pady=(4, 2), sticky="w"
        )
        row += 1
        motor_frame = ctk.CTkFrame(parent, fg_color="transparent")
        motor_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        ctk.CTkButton(motor_frame, text="Enable Motors",  width=140,
                      fg_color="green", hover_color="#1a7a1a",
                      command=self._manual_motors_on).pack(side="left", padx=(0, 8))
        ctk.CTkButton(motor_frame, text="Disable Motors", width=140,
                      fg_color="#555", hover_color="#333",
                      command=self._manual_motors_off).pack(side="left")
        row += 1

        # ---- Home control ----
        ctk.CTkLabel(parent, text="Home Position", font=("", 12, "bold")).grid(
            row=row, column=0, columnspan=2, padx=8, pady=(4, 2), sticky="w"
        )
        row += 1
        home_frame = ctk.CTkFrame(parent, fg_color="transparent")
        home_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        ctk.CTkButton(home_frame, text="Set Home Here", width=150,
                      command=self._manual_set_home).pack(side="left", padx=(0, 8))
        ctk.CTkButton(home_frame, text="Go to Home",    width=130,
                      fg_color="green", hover_color="#1a7a1a",
                      command=self._manual_go_home).pack(side="left", padx=(0, 8))
        ctk.CTkButton(home_frame, text="Go to Origin (0,0)", width=160,
                      fg_color="#555", hover_color="#333",
                      command=self._manual_go_origin).pack(side="left")
        row += 1

        # ---- Jog controls ----
        ctk.CTkLabel(parent, text="Jog", font=("", 12, "bold")).grid(
            row=row, column=0, columnspan=2, padx=8, pady=(4, 2), sticky="w"
        )
        row += 1

        # Step size selector
        step_frame = ctk.CTkFrame(parent, fg_color="transparent")
        step_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")
        ctk.CTkLabel(step_frame, text="Step size (mm):").pack(side="left", padx=(0, 8))
        self._jog_step = ctk.CTkOptionMenu(
            step_frame, values=["0.1", "0.5", "1", "5", "10", "20"], width=80
        )
        self._jog_step.set("1")
        self._jog_step.pack(side="left")
        row += 1

        # Directional pad
        jog_pad = ctk.CTkFrame(parent, fg_color="transparent")
        jog_pad.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 8))

        btn_cfg = dict(width=52, height=52)
        ctk.CTkButton(jog_pad, text="↖", **btn_cfg, command=lambda: self._jog(-1, -1)).grid(row=0, column=0, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="↑", **btn_cfg, command=lambda: self._jog( 0, -1)).grid(row=0, column=1, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="↗", **btn_cfg, command=lambda: self._jog( 1, -1)).grid(row=0, column=2, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="←", **btn_cfg, command=lambda: self._jog(-1,  0)).grid(row=1, column=0, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="⌂", **btn_cfg, fg_color="green",
                      command=self._manual_go_home).grid(row=1, column=1, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="→", **btn_cfg, command=lambda: self._jog( 1,  0)).grid(row=1, column=2, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="↙", **btn_cfg, command=lambda: self._jog(-1,  1)).grid(row=2, column=0, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="↓", **btn_cfg, command=lambda: self._jog( 0,  1)).grid(row=2, column=1, padx=2, pady=2)
        ctk.CTkButton(jog_pad, text="↘", **btn_cfg, command=lambda: self._jog( 1,  1)).grid(row=2, column=2, padx=2, pady=2)
        row += 1

        # ---- Move to XY ----
        ctk.CTkLabel(parent, text="Move to Position (mm)", font=("", 12, "bold")).grid(
            row=row, column=0, columnspan=2, padx=8, pady=(4, 2), sticky="w"
        )
        row += 1
        xy_frame = ctk.CTkFrame(parent, fg_color="transparent")
        xy_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(xy_frame, text="X:").pack(side="left", padx=(0, 4))
        self._move_x = ctk.CTkEntry(xy_frame, width=70, placeholder_text="mm")
        self._move_x.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(xy_frame, text="Y:").pack(side="left", padx=(0, 4))
        self._move_y = ctk.CTkEntry(xy_frame, width=70, placeholder_text="mm")
        self._move_y.pack(side="left", padx=(0, 12))
        ctk.CTkButton(xy_frame, text="Move", width=80,
                      command=self._manual_move_to).pack(side="left")

    # ------------------------------------------------------------------
    # Manual control actions
    # ------------------------------------------------------------------

    def _update_position_display(self) -> None:
        if self._plotter:
            x_mm, y_mm = self._plotter.position_mm
            hx_mm, hy_mm = self._plotter.home_mm
            self._lbl_pos_x.configure(text=f"{x_mm:.2f}")
            self._lbl_pos_y.configure(text=f"{y_mm:.2f}")
            self._lbl_home_x.configure(text=f"{hx_mm:.2f}")
            self._lbl_home_y.configure(text=f"{hy_mm:.2f}")

    def _manual_pen_up(self) -> None:
        self._run_action(lambda: self._plotter.pen_up(), "Pen raised.")
        self._btn_pen_up.configure(fg_color="#2a6db5")
        self._btn_pen_down.configure(fg_color="#8d1f1f")

    def _manual_pen_down(self) -> None:
        self._run_action(lambda: self._plotter.pen_down(), "Pen lowered.")
        self._btn_pen_down.configure(fg_color="#b52a2a")
        self._btn_pen_up.configure(fg_color="#1f538d")

    def _manual_motors_on(self) -> None:
        self._run_action(lambda: self._plotter.enable_motors(), "Motors enabled.")

    def _manual_motors_off(self) -> None:
        self._run_action(lambda: self._plotter.disable_motors(),
                         "Motors disabled — carriage can be moved by hand.")

    def _manual_set_home(self) -> None:
        if not self._require_connection():
            return
        x_mm, y_mm = self._plotter.set_home()
        self._log(f"Home set to ({x_mm:.2f}, {y_mm:.2f}) mm.")
        self._update_position_display()

    def _manual_go_home(self) -> None:
        def _action():
            self._plotter.go_home()
            self.after(0, self._update_position_display)
        self._run_action(_action, "Moved to home position.")

    def _manual_go_origin(self) -> None:
        def _action():
            self._plotter.go_origin()
            self.after(0, self._update_position_display)
        self._run_action(_action, "Moved to machine origin (0, 0).")

    def _jog(self, dx_dir: int, dy_dir: int) -> None:
        if not self._require_connection():
            return
        try:
            step = float(self._jog_step.get())
        except ValueError:
            step = 1.0
        dx = dx_dir * step
        dy = dy_dir * step
        def _action():
            self._plotter.jog(dx, dy)
            self.after(0, self._update_position_display)
        self._run_action(_action, f"Jogged ({dx:+.1f}, {dy:+.1f}) mm.")

    def _manual_move_to(self) -> None:
        if not self._require_connection():
            return
        try:
            x_mm = float(self._move_x.get())
            y_mm = float(self._move_y.get())
        except ValueError:
            mb.showerror("Input Error", "Enter valid X and Y values in mm.")
            return
        def _action():
            self._plotter.move_to_mm(x_mm, y_mm)
            self.after(0, self._update_position_display)
        self._run_action(_action, f"Moved to ({x_mm:.2f}, {y_mm:.2f}) mm.")

    # ------------------------------------------------------------------
    # Settings tab
    # ------------------------------------------------------------------

    def _build_settings_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)

        c = self._config
        row = 0

        # ---- Pen angle selector ----
        ctk.CTkLabel(parent, text="Pen mount angle", font=("", 12, "bold")).grid(
            row=row, column=0, padx=12, pady=(10, 2), sticky="w"
        )
        angle_options = [f"{a}°" for a in sorted(PEN_ANGLE_PRESETS)]
        self._pen_angle_var = ctk.StringVar(value=f"{c.pen_angle}°")
        angle_menu = ctk.CTkOptionMenu(
            parent,
            values=angle_options,
            variable=self._pen_angle_var,
            command=self._on_angle_changed,
        )
        angle_menu.grid(row=row, column=1, padx=12, pady=(10, 2), sticky="w")

        preset_hint = ctk.CTkLabel(
            parent,
            text="Selecting an angle loads preset positions — edit below to fine-tune.",
            font=("", 10),
            text_color="gray",
        )
        preset_hint.grid(row=row + 1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="w")
        row += 2

        # ---- All other numeric/text fields ----
        fields = [
            ("Pen pos down (0–100)",       "pen_pos_down",   str(c.pen_pos_down)),
            ("Pen pos up (0–100)",         "pen_pos_up",     str(c.pen_pos_up)),
            ("Speed (pen down)",           "speed_pendown",  str(c.speed_pendown)),
            ("Speed (pen up)",             "speed_penup",    str(c.speed_penup)),
            ("Pen delay down (ms)",        "pen_delay_down", str(c.pen_delay_down)),
            ("Pen delay up (ms)",          "pen_delay_up",   str(c.pen_delay_up)),
            ("X-axis limit mm  (max 150)", "x_max_mm",       str(c.x_max_mm)),
            ("Y-axis limit mm  (max 100)", "y_max_mm",       str(c.y_max_mm)),
            ("Serial port (blank=auto)",   "port",           c.port or ""),
        ]
        self._settings_entries: dict[str, ctk.CTkEntry] = {}
        for label, key, default in fields:
            ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=12, pady=5, sticky="w")
            e = ctk.CTkEntry(parent)
            e.insert(0, default)
            e.grid(row=row, column=1, padx=12, pady=5, sticky="ew")
            self._settings_entries[key] = e
            row += 1

        self._const_speed = ctk.CTkCheckBox(parent, text="Constant speed mode")
        if c.const_speed:
            self._const_speed.select()
        self._const_speed.grid(row=row, column=0, columnspan=2, padx=12, pady=8, sticky="w")
        row += 1

        ctk.CTkLabel(
            parent,
            text=f"Config file: {config_path().name}",
            font=("", 10),
            text_color="gray",
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(0, 4), sticky="w")
        row += 1

        ctk.CTkButton(parent, text="Apply & Save Settings", command=self._apply_settings).grid(
            row=row, column=0, columnspan=2, padx=12, pady=8, sticky="ew"
        )

    def _on_angle_changed(self, choice: str) -> None:
        """Auto-fill pen_pos_down/up preset when the angle selector changes."""
        angle = int(choice.rstrip("°"))
        down, up = PEN_ANGLE_PRESETS[angle]
        for key, val in [("pen_pos_down", down), ("pen_pos_up", up)]:
            entry = self._settings_entries[key]
            entry.delete(0, "end")
            entry.insert(0, str(val))
        self._log(f"Pen angle set to {angle}° — preset positions loaded (down={down}, up={up}).")

    # ------------------------------------------------------------------
    # Log tab
    # ------------------------------------------------------------------

    def _build_log_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        self._log_box = ctk.CTkTextbox(parent, state="disabled", font=("Courier", 11))
        self._log_box.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        ctk.CTkButton(parent, text="Clear Log", command=self._clear_log).grid(
            row=1, column=0, padx=4, pady=4, sticky="e"
        )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _toggle_connect(self):
        if self._plotter and self._plotter.connected:
            self._plotter.disconnect()
            self._plotter = None
            self._lbl_status.configure(text="● Disconnected", text_color="red")
            self._btn_connect.configure(text="Connect")
            self._log("Disconnected from AxiDraw.")
        else:
            self._apply_settings()
            self._plotter = Plotter(self._config)
            try:
                self._plotter.connect()
                self._lbl_status.configure(text="● Connected", text_color="green")
                self._btn_connect.configure(text="Disconnect")
                self._log("Connected to AxiDraw Mini 2.")
                self._update_position_display()
            except PlotterError as e:
                self._plotter = None
                mb.showerror("Connection Error", str(e))
                self._log(f"ERROR: {e}")

    # ------------------------------------------------------------------
    # Pen / motor actions
    # ------------------------------------------------------------------

    def _pen_up(self):
        self._run_action(lambda: self._plotter.pen_up(), "Pen up.")

    def _pen_down(self):
        self._run_action(lambda: self._plotter.pen_down(), "Pen down.")

    def _go_home(self):
        self._run_action(lambda: self._plotter.go_home(), "Moved to home (0, 0).")

    def _motors_off(self):
        self._run_action(lambda: self._plotter.disable_motors(), "Motors disabled.")

    def _run_action(self, fn, success_msg: str):
        if not self._require_connection():
            return
        try:
            fn()
            self._log(success_msg)
        except PlotterError as e:
            mb.showerror("Plotter Error", str(e))
            self._log(f"ERROR: {e}")

    def _require_connection(self) -> bool:
        if not (self._plotter and self._plotter.connected):
            mb.showwarning("Not Connected", "Connect to the AxiDraw first.")
            return False
        return True

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _load_file(self):
        path = fd.askopenfilename(filetypes=_ALL_TYPES)
        if not path:
            return
        self._file_path = path
        self._svg_path = None
        self._lbl_file.configure(text=Path(path).name)
        self._log(f"Loaded: {path}")

        if is_raster(path):
            self._log("Raster detected — trace it in the Image Trace tab, or use Trace & Plot.")

    # ------------------------------------------------------------------
    # Plot file
    # ------------------------------------------------------------------

    def _plot_file(self):
        if not self._file_path:
            mb.showwarning("No File", "Load a file first.")
            return
        if not self._require_connection():
            return

        svg = self._svg_path
        if svg is None:
            if is_raster(self._file_path):
                self._log("Tracing raster image before plotting…")
                svg = self._do_trace(self._file_path)
                if svg is None:
                    return
                self._svg_path = svg
            else:
                svg = self._file_path

        self._log(f"Plotting: {svg}")
        self._run_in_thread(lambda: self._plotter.plot_svg(svg),
                            "Plot complete.", "Plot failed")

    # ------------------------------------------------------------------
    # Shape plotting
    # ------------------------------------------------------------------

    def _plot_shape_svg(self, svg_str: str, label: str):
        if not self._require_connection():
            return
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w") as f:
            f.write(svg_str)
            tmp = f.name
        self._log(f"Plotting {label}…")
        self._run_in_thread(lambda: self._plotter.plot_svg(tmp), f"{label} done.", f"{label} failed")

    def _shape_kwargs(self) -> dict:
        """Return unit and plotter limits to pass to every shape function."""
        unit = self._shape_unit.get()
        cfg = self._plotter.config if self._plotter else self._cfg
        return {"unit": unit, "x_max_mm": cfg.x_max_mm, "y_max_mm": cfg.y_max_mm}

    def _shape_error(self, err: Exception, shape: str):
        mb.showerror("Shape Error", f"{shape}: {err}")

    def _fv(self, d: dict, key: str) -> float:
        return float(d[key].get())

    def _plot_rect(self):
        try:
            kw = self._shape_kwargs()
            svg = shapes.rect_svg(
                self._fv(self._rect, "X"), self._fv(self._rect, "Y"),
                self._fv(self._rect, "W"), self._fv(self._rect, "H"), **kw
            )
            self._plot_shape_svg(svg, "Rectangle")
        except Exception as e:
            self._shape_error(e, "Rectangle")

    def _plot_square(self):
        try:
            kw = self._shape_kwargs()
            svg = shapes.square_svg(
                self._fv(self._sqr, "X"), self._fv(self._sqr, "Y"),
                self._fv(self._sqr, "Side"), **kw
            )
            self._plot_shape_svg(svg, "Square")
        except Exception as e:
            self._shape_error(e, "Square")

    def _plot_circle(self):
        try:
            kw = self._shape_kwargs()
            svg = shapes.circle_svg(
                self._fv(self._circ, "CX"), self._fv(self._circ, "CY"),
                self._fv(self._circ, "R"), **kw
            )
            self._plot_shape_svg(svg, "Circle")
        except Exception as e:
            self._shape_error(e, "Circle")

    def _plot_ellipse(self):
        try:
            kw = self._shape_kwargs()
            svg = shapes.ellipse_svg(
                self._fv(self._ellipse, "CX"), self._fv(self._ellipse, "CY"),
                self._fv(self._ellipse, "RX"), self._fv(self._ellipse, "RY"), **kw
            )
            self._plot_shape_svg(svg, "Ellipse")
        except Exception as e:
            self._shape_error(e, "Ellipse")

    def _plot_triangle(self):
        try:
            kw = self._shape_kwargs()
            svg = shapes.triangle_svg(
                self._fv(self._tri, "CX"), self._fv(self._tri, "CY"),
                self._fv(self._tri, "Side"), **kw
            )
            self._plot_shape_svg(svg, "Triangle")
        except Exception as e:
            self._shape_error(e, "Triangle")

    def _plot_polygon(self):
        try:
            kw = self._shape_kwargs()
            sides = int(self._poly["Sides"].get())
            svg = shapes.polygon_svg(
                self._fv(self._poly, "CX"), self._fv(self._poly, "CY"),
                self._fv(self._poly, "R"), sides, **kw
            )
            self._plot_shape_svg(svg, f"{sides}-sided Polygon")
        except Exception as e:
            self._shape_error(e, "Polygon")

    def _plot_star(self):
        try:
            kw = self._shape_kwargs()
            pts = int(self._star["Points"].get())
            svg = shapes.star_svg(
                self._fv(self._star, "CX"), self._fv(self._star, "CY"),
                self._fv(self._star, "R Out"), self._fv(self._star, "R In"),
                pts, **kw
            )
            self._plot_shape_svg(svg, f"{pts}-point Star")
        except Exception as e:
            self._shape_error(e, "Star")

    def _plot_line(self):
        try:
            kw = self._shape_kwargs()
            svg = shapes.line_svg(
                self._fv(self._line, "X1"), self._fv(self._line, "Y1"),
                self._fv(self._line, "X2"), self._fv(self._line, "Y2"), **kw
            )
            self._plot_shape_svg(svg, "Line")
        except Exception as e:
            self._shape_error(e, "Line")

    def _plot_text(self):
        text = self._text_entry.get().strip()
        if not text:
            mb.showwarning("No Text", "Enter text to draw.")
            return
        try:
            kw = self._shape_kwargs()
            svg = shapes.text_svg(
                text,
                self._fv(self._txt, "X (pos)"), self._fv(self._txt, "Y (pos)"),
                self._fv(self._txt, "Size (pt)"),
                self._txt_font.get(), **kw
            )
            self._plot_shape_svg(svg, "Text")
        except Exception as e:
            self._shape_error(e, "Text")

    # ------------------------------------------------------------------
    # Image trace
    # ------------------------------------------------------------------

    def _open_raster(self):
        path = fd.askopenfilename(filetypes=_RASTER_TYPES)
        if path:
            self._file_path = path
            self._svg_path = None
            self._lbl_trace_src.configure(text=Path(path).name)
            self._log(f"Image loaded for tracing: {path}")

    def _do_trace(self, src: str) -> str | None:
        try:
            scale_pct = float(self._trace_scale_pct.get())
            if not (1 <= scale_pct <= 100):
                raise ValueError("Fill % must be between 1 and 100.")
        except ValueError as e:
            mb.showerror("Invalid Scale", str(e))
            return None

        try:
            if "hatchsvg" in self._trace_backend.get():
                out = hatch_to_svg(
                    src,
                    hatch_angle=float(self._hatch_angle.get()),
                    line_step=int(self._hatch_line_step.get()),
                    max_palette=int(self._hatch_palette.get()),
                    stroke_width=float(self._hatch_stroke.get()),
                    scale=float(self._hatch_scale.get()),
                    arc_radius=float(self._hatch_arc.get()),
                    continuous_paths=bool(self._hatch_continuous.get()),
                    skip_bg=bool(self._hatch_skip_bg.get()),
                    optimize_travel=bool(self._hatch_optimize.get()),
                )
            else:
                out = trace_to_svg(
                    src,
                    colormode=self._colormode.get(),
                    filter_speckle=int(self._speckle.get()),
                )

            # Scale and centre the SVG to fit within the plotter travel area
            cfg = self._plotter.config if self._plotter else self._cfg
            fit_svg_to_bounds(out, x_max_mm=cfg.x_max_mm, y_max_mm=cfg.y_max_mm,
                              scale_pct=scale_pct)

            self._log(f"Traced SVG saved and fitted to {scale_pct:.0f}% of travel area: {out}")
            self._lbl_trace_out.configure(text=f"SVG: {Path(out).name}")
            return out
        except Exception as e:
            mb.showerror("Trace Error", str(e))
            self._log(f"Trace ERROR: {e}")
            return None

    def _run_trace(self):
        if not self._file_path or not is_raster(self._file_path):
            mb.showwarning("No Image", "Load a raster image in the Image Trace tab first.")
            return
        self._do_trace(self._file_path)

    def _trace_and_plot(self):
        if not self._file_path or not is_raster(self._file_path):
            mb.showwarning("No Image", "Load a raster image first.")
            return
        if not self._require_connection():
            return
        svg = self._do_trace(self._file_path)
        if svg:
            self._svg_path = svg
            self._log(f"Plotting traced SVG: {svg}")
            self._run_in_thread(lambda: self._plotter.plot_svg(svg),
                                "Trace & plot complete.", "Plot failed")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _apply_settings(self):
        e = self._settings_entries
        try:
            self._config.pen_angle = int(self._pen_angle_var.get().rstrip("°"))
            self._config.pen_pos_down = int(e["pen_pos_down"].get())
            self._config.pen_pos_up = int(e["pen_pos_up"].get())
            self._config.speed_pendown = int(e["speed_pendown"].get())
            self._config.speed_penup = int(e["speed_penup"].get())
            self._config.pen_delay_down = int(e["pen_delay_down"].get())
            self._config.pen_delay_up = int(e["pen_delay_up"].get())
            self._config.x_max_mm = float(e["x_max_mm"].get())
            self._config.y_max_mm = float(e["y_max_mm"].get())
            self._config.const_speed = bool(self._const_speed.get())
            port_val = e["port"].get().strip()
            self._config.port = port_val if port_val else None
            # raises ValueError if limits are out of range
            self._config._validate_limits()
        except ValueError as ex:
            mb.showerror("Settings Error", str(ex))
            return

        if self._plotter and self._plotter.connected:
            self._plotter.update_config(**{
                k: getattr(self._config, k)
                for k in ["pen_angle", "pen_pos_down", "pen_pos_up",
                          "speed_pendown", "speed_penup",
                          "pen_delay_down", "pen_delay_up",
                          "x_max_mm", "y_max_mm", "const_speed", "port"]
            })

        save_config(self._config)
        self._log(f"Settings saved to {config_path().name}.")

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def _set_job_running(self, running: bool):
        """Enable/disable the Cancel button and track job state (call from any thread)."""
        self._job_running = running
        state = "normal" if running else "disabled"
        self.after(0, lambda: self._btn_cancel.configure(state=state))

    def _cancel_job(self):
        """
        Emergency stop: signal the running job to abort, then recover —
        pen up and move to home — in a background thread so the GUI stays live.
        """
        if not self._job_running:
            return
        self._log("⬛ Cancel requested — stopping job and recovering…")
        self._cancel_event.set()

        def recover():
            try:
                # Disconnect interrupts any blocking plot_run() call
                if self._plotter and self._plotter.connected:
                    self._plotter.disconnect()

                # Reconnect just long enough to raise the pen and go home
                if self._plotter:
                    self._plotter.connect()
                    try:
                        self._plotter.pen_up()
                        self._plotter.go_home()
                    finally:
                        # Leave connection open so the user can keep working
                        pass

                self.after(0, lambda: self._log("✓ Job cancelled — pen up, returned to home."))
                self.after(0, self._update_position_display)
            except Exception as e:
                self.after(0, lambda: self._log(f"Recovery error: {e}"))
            finally:
                self._cancel_event.clear()
                self._set_job_running(False)

        threading.Thread(target=recover, daemon=True).start()

    # ------------------------------------------------------------------
    # Threading helper
    # ------------------------------------------------------------------

    def _run_in_thread(self, fn, success: str, fail_prefix: str):
        self._cancel_event.clear()
        self._set_job_running(True)

        def worker():
            try:
                fn()
                if not self._cancel_event.is_set():
                    self.after(0, lambda: self._log(success))
            except Exception as e:
                if not self._cancel_event.is_set():
                    msg = str(e)
                    self.after(0, lambda: self._log(f"{fail_prefix}: {msg}"))
                    self.after(0, lambda: mb.showerror("Error", msg))
            finally:
                if not self._cancel_event.is_set():
                    self._set_job_running(False)

        threading.Thread(target=worker, daemon=True).start()


def launch():
    app = App()
    app.mainloop()
