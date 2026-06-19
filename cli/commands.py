"""CLI commands for AxiDraw Mini 2 controller."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.plotter import Plotter, PlotterConfig, PlotterError
from core.image_trace import is_raster, trace_to_svg
from core import shapes


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="axidraw",
        description="AxiDraw Mini 2 controller CLI",
    )
    p.add_argument("--port", help="Serial port (default: auto-detect)")
    p.add_argument("--speed-down", type=int, default=25, metavar="N",
                   help="Pen-down speed 1–100 (default: 25)")
    p.add_argument("--speed-up", type=int, default=75, metavar="N",
                   help="Pen-up speed 1–100 (default: 75)")
    p.add_argument("--pen-down", type=int, default=40, dest="pen_pos_down",
                   help="Pen-down servo position 0–100 (default: 40)")
    p.add_argument("--pen-up", type=int, default=60, dest="pen_pos_up",
                   help="Pen-up servo position 0–100 (default: 60)")
    p.add_argument("--x-max", type=float, default=140.0, dest="x_max_mm",
                   help="X-axis travel limit in mm, max 150 (default: 140)")
    p.add_argument("--y-max", type=float, default=90.0, dest="y_max_mm",
                   help="Y-axis travel limit in mm, max 100 (default: 90)")

    sub = p.add_subparsers(dest="command", required=True)

    # plot
    sp = sub.add_parser("plot", help="Plot an SVG, JPEG, PNG, or BMP file")
    sp.add_argument("file", help="Path to file")

    # trace
    sp = sub.add_parser("trace", help="Convert raster image to SVG (no plotting)")
    sp.add_argument("file", help="Path to JPEG/PNG/BMP")
    sp.add_argument("-o", "--output", help="Output SVG path (default: same dir as input)")
    sp.add_argument("--colormode", choices=["binary", "color", "layered"],
                    default="binary", help="Trace color mode")

    # home
    sub.add_parser("home", help="Move pen to home position (0, 0)")

    # pen
    sp = sub.add_parser("pen", help="Raise or lower the pen")
    sp.add_argument("action", choices=["up", "down"])

    # motors
    sp = sub.add_parser("motors", help="Enable or disable motors")
    sp.add_argument("action", choices=["on", "off"])

    # draw-shape
    sp = sub.add_parser("draw-shape", help="Draw a basic shape")
    shape_sub = sp.add_subparsers(dest="shape", required=True)

    rp = shape_sub.add_parser("rect", help="Draw a rectangle")
    rp.add_argument("x", type=float); rp.add_argument("y", type=float)
    rp.add_argument("w", type=float); rp.add_argument("h", type=float)

    cp = shape_sub.add_parser("circle", help="Draw a circle")
    cp.add_argument("cx", type=float); cp.add_argument("cy", type=float)
    cp.add_argument("r", type=float)

    pp = shape_sub.add_parser("polygon", help="Draw a regular polygon")
    pp.add_argument("cx", type=float); pp.add_argument("cy", type=float)
    pp.add_argument("r", type=float); pp.add_argument("sides", type=int)

    tp = shape_sub.add_parser("text", help="Draw text")
    tp.add_argument("text"); tp.add_argument("x", type=float); tp.add_argument("y", type=float)
    tp.add_argument("--size", type=float, default=24, help="Font size in pt")

    return p


def make_config(args) -> PlotterConfig:
    return PlotterConfig(
        speed_pendown=args.speed_down,
        speed_penup=args.speed_up,
        pen_pos_down=args.pen_pos_down,
        pen_pos_up=args.pen_pos_up,
        x_max_mm=args.x_max_mm,
        y_max_mm=args.y_max_mm,
        port=getattr(args, "port", None),
    )


def run(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    config = make_config(args)

    # trace command does not need a connection
    if args.command == "trace":
        _cmd_trace(args)
        return

    plotter = Plotter(config)
    try:
        plotter.connect()
        print("Connected to AxiDraw Mini 2.")
    except PlotterError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        _dispatch(args, plotter)
    except PlotterError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        plotter.disconnect()
        print("Disconnected.")


def _dispatch(args, plotter: Plotter):
    cmd = args.command

    if cmd == "home":
        plotter.go_home()
        print("Moved to home.")

    elif cmd == "pen":
        if args.action == "up":
            plotter.pen_up(); print("Pen up.")
        else:
            plotter.pen_down(); print("Pen down.")

    elif cmd == "motors":
        if args.action == "on":
            plotter.enable_motors(); print("Motors enabled.")
        else:
            plotter.disable_motors(); print("Motors disabled.")

    elif cmd == "plot":
        _cmd_plot(args, plotter)

    elif cmd == "draw-shape":
        _cmd_draw_shape(args, plotter)


def _cmd_plot(args, plotter: Plotter):
    path = args.file
    if is_raster(path):
        print(f"Raster detected — tracing {path}…")
        path = trace_to_svg(path)
        print(f"SVG saved to: {path}")
    print(f"Plotting {path}…")
    plotter.plot_svg(path)
    print("Done.")


def _cmd_trace(args):
    src = args.file
    out = trace_to_svg(src, args.output, colormode=args.colormode)
    print(f"SVG written to: {out}")


def _cmd_draw_shape(args, plotter: Plotter):
    import tempfile, os

    shape = args.shape
    if shape == "rect":
        svg = shapes.rect_svg(args.x, args.y, args.w, args.h)
    elif shape == "circle":
        svg = shapes.circle_svg(args.cx, args.cy, args.r)
    elif shape == "polygon":
        svg = shapes.polygon_svg(args.cx, args.cy, args.r, args.sides)
    elif shape == "text":
        svg = shapes.text_svg(args.text, args.x, args.y, args.size)
    else:
        print(f"Unknown shape: {shape}", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w") as f:
        f.write(svg)
        tmp = f.name
    try:
        print(f"Plotting {shape}…")
        plotter.plot_svg(tmp)
        print("Done.")
    finally:
        os.unlink(tmp)
