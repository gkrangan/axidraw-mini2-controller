"""CLI commands for AxiDraw Mini 2 controller."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.plotter import Plotter, PlotterConfig, PlotterError
from core.image_trace import is_raster, trace_to_svg, hatch_to_svg, fit_svg_to_bounds
from core.config_io import load_config
from core import shapes


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="axidraw",
        description="AxiDraw Mini 2 controller CLI",
    )
    # All flags default to None so we can detect which were explicitly passed
    # and let the .cfg file supply the real defaults for the rest.
    p.add_argument("--port", default=None,
                   help="Serial port (default: from config file, then auto-detect)")
    p.add_argument("--speed-down", type=int, default=None, metavar="N",
                   dest="speed_pendown", help="Pen-down speed 1–100")
    p.add_argument("--speed-up", type=int, default=None, metavar="N",
                   dest="speed_penup", help="Pen-up speed 1–100")
    p.add_argument("--pen-angle", type=int, default=None, dest="pen_angle",
                   choices=[45, 90],
                   help="Pen mount angle (45 or 90 degrees); loads position preset")
    p.add_argument("--pen-down", type=int, default=None, dest="pen_pos_down",
                   help="Pen-down servo position 0–100 (overrides angle preset)")
    p.add_argument("--pen-up", type=int, default=None, dest="pen_pos_up",
                   help="Pen-up servo position 0–100 (overrides angle preset)")
    p.add_argument("--x-max", type=float, default=None, dest="x_max_mm",
                   help="X-axis travel limit in mm, max 150")
    p.add_argument("--y-max", type=float, default=None, dest="y_max_mm",
                   help="Y-axis travel limit in mm, max 100")

    sub = p.add_subparsers(dest="command", required=True)

    # plot
    sp = sub.add_parser("plot", help="Plot an SVG, JPEG, PNG, or BMP file")
    sp.add_argument("file", help="Path to file")

    # trace
    sp = sub.add_parser("trace", help="Convert raster image to SVG (no plotting)")
    sp.add_argument("file", help="Path to image (JPG/PNG/BMP/WebP/GIF/TIFF)")
    sp.add_argument("-o", "--output", help="Output SVG path (default: same dir as input)")
    sp.add_argument("--backend", choices=["hatchsvg", "outline"], default="outline",
                    help="Tracing backend: outline (vtracer/potrace, default) or hatchsvg (hatched)")
    sp.add_argument("--scale-pct", type=float, default=90.0, metavar="PCT",
                    help="Scale traced SVG to fill PCT%% of the plotter travel area, centred (1–100, default 90)")
    # hatchsvg options
    sp.add_argument("--hatch-angle", type=float, default=45.0,
                    help="Hatch line angle in degrees (default: 45)")
    sp.add_argument("--line-step", type=int, default=4,
                    help="Spacing between hatch lines in px (default: 4)")
    sp.add_argument("--max-palette", type=int, default=12,
                    help="Max colour layers for hatchsvg (default: 12)")
    sp.add_argument("--stroke-width", type=float, default=0.5,
                    help="SVG stroke width (default: 0.5)")
    sp.add_argument("--scale", type=float, default=1.0,
                    help="Image scale factor (default: 1.0)")
    sp.add_argument("--arc-radius", type=float, default=2.0,
                    help="Arc smoothing radius at U-turns (default: 2.0)")
    sp.add_argument("--no-continuous", action="store_true",
                    help="Disable serpentine continuous paths")
    sp.add_argument("--skip-bg", action="store_true",
                    help="Skip background colour layer")
    sp.add_argument("--no-optimize", action="store_true",
                    help="Disable layer travel order optimisation")
    # outline options
    sp.add_argument("--colormode", choices=["binary", "color", "layered"],
                    default="binary", help="Outline trace color mode (outline backend only)")

    # pen
    sp = sub.add_parser("pen", help="Raise or lower the pen")
    sp.add_argument("action", choices=["up", "down"])

    # motors
    sp = sub.add_parser("motors", help="Enable or disable stepper motors")
    sp.add_argument("action", choices=["on", "off"])

    # home
    sub.add_parser("home", help="Move pen to the user-defined home position")

    # origin
    sub.add_parser("origin", help="Move pen to machine origin (0, 0) — where carriage was on connect")

    # set-home
    sub.add_parser("set-home", help="Mark the current pen position as the home position")

    # move
    sp = sub.add_parser("move", help="Move pen to an absolute position (pen up)")
    sp.add_argument("x", type=float, help="X position in mm")
    sp.add_argument("y", type=float, help="Y position in mm")

    # jog
    sp = sub.add_parser("jog", help="Move pen relative to current position (pen up)")
    sp.add_argument("dx", type=float, help="X offset in mm (negative = left)")
    sp.add_argument("dy", type=float, help="Y offset in mm (negative = up)")

    # draw-shape
    sp = sub.add_parser("draw-shape", help="Draw a shape and plot it")
    shape_sub = sp.add_subparsers(dest="shape", required=True)

    # Shared unit flag added to every shape parser
    def _add_unit(p):
        p.add_argument("--unit", choices=["mm", "in"], default="mm",
                       help="Unit for all dimensions (default: mm)")
        return p

    rp = _add_unit(shape_sub.add_parser("rect", help="Rectangle (top-left x y, width w, height h)"))
    rp.add_argument("x", type=float); rp.add_argument("y", type=float)
    rp.add_argument("w", type=float); rp.add_argument("h", type=float)

    sqp = _add_unit(shape_sub.add_parser("square", help="Square (top-left x y, side length)"))
    sqp.add_argument("x", type=float); sqp.add_argument("y", type=float)
    sqp.add_argument("side", type=float)

    cp = _add_unit(shape_sub.add_parser("circle", help="Circle (centre cx cy, radius r)"))
    cp.add_argument("cx", type=float); cp.add_argument("cy", type=float)
    cp.add_argument("r", type=float)

    ep = _add_unit(shape_sub.add_parser("ellipse", help="Ellipse (centre cx cy, x-radius rx, y-radius ry)"))
    ep.add_argument("cx", type=float); ep.add_argument("cy", type=float)
    ep.add_argument("rx", type=float); ep.add_argument("ry", type=float)

    trp = _add_unit(shape_sub.add_parser("triangle", help="Equilateral triangle (centre cx cy, side length)"))
    trp.add_argument("cx", type=float); trp.add_argument("cy", type=float)
    trp.add_argument("side", type=float)

    pp = _add_unit(shape_sub.add_parser("polygon", help="Regular polygon (centre cx cy, circumradius r, sides)"))
    pp.add_argument("cx", type=float); pp.add_argument("cy", type=float)
    pp.add_argument("r", type=float); pp.add_argument("sides", type=int)

    stp = _add_unit(shape_sub.add_parser("star", help="Star (centre cx cy, outer-radius, inner-radius, points)"))
    stp.add_argument("cx", type=float); stp.add_argument("cy", type=float)
    stp.add_argument("r_outer", type=float); stp.add_argument("r_inner", type=float)
    stp.add_argument("points", type=int)

    lp = _add_unit(shape_sub.add_parser("line", help="Straight line (x1 y1 x2 y2)"))
    lp.add_argument("x1", type=float); lp.add_argument("y1", type=float)
    lp.add_argument("x2", type=float); lp.add_argument("y2", type=float)

    tp = _add_unit(shape_sub.add_parser("text", help="Draw text at position (x y)"))
    tp.add_argument("text"); tp.add_argument("x", type=float); tp.add_argument("y", type=float)
    tp.add_argument("--size", type=float, default=12, help="Font size in pt (default: 12)")
    tp.add_argument("--font", default="futural",
                    choices=["futural","futuram","cursive","gothgbt","gothgrt","scripts","cyrillic"],
                    help="Hershey stroke font (default: futural)")

    return p


def make_config(args) -> PlotterConfig:
    """Load config from .cfg file, then apply any CLI overrides."""
    from core.plotter import PEN_ANGLE_PRESETS
    cfg = load_config()

    # Apply angle first so explicit --pen-down/up can still override the preset
    if args.pen_angle is not None:
        cfg.pen_angle = args.pen_angle
        cfg.apply_angle_preset()

    overrides = {
        "speed_pendown": args.speed_pendown,
        "speed_penup":   args.speed_penup,
        "pen_pos_down":  args.pen_pos_down,
        "pen_pos_up":    args.pen_pos_up,
        "x_max_mm":      args.x_max_mm,
        "y_max_mm":      args.y_max_mm,
        "port":          args.port,
    }
    for field, value in overrides.items():
        if value is not None:
            setattr(cfg, field, value)
    cfg._validate_limits()
    return cfg


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

    if cmd == "pen":
        if args.action == "up":
            plotter.pen_up(); print("Pen up.")
        else:
            plotter.pen_down(); print("Pen down.")

    elif cmd == "motors":
        if args.action == "on":
            plotter.enable_motors(); print("Motors enabled.")
        else:
            plotter.disable_motors()
            print("Motors disabled — carriage can now be moved by hand.")

    elif cmd == "home":
        plotter.go_home()
        x_mm, y_mm = plotter.position_mm
        print(f"Moved to home ({x_mm:.2f}, {y_mm:.2f}) mm.")

    elif cmd == "origin":
        plotter.go_origin()
        print("Moved to machine origin (0.00, 0.00) mm.")

    elif cmd == "set-home":
        x_mm, y_mm = plotter.set_home()
        print(f"Home set to current position ({x_mm:.2f}, {y_mm:.2f}) mm.")

    elif cmd == "move":
        plotter.move_to_mm(args.x, args.y)
        print(f"Moved to ({args.x:.2f}, {args.y:.2f}) mm.")

    elif cmd == "jog":
        plotter.jog(args.dx, args.dy)
        x_mm, y_mm = plotter.position_mm
        print(f"Jogged ({args.dx:+.2f}, {args.dy:+.2f}) mm → now at ({x_mm:.2f}, {y_mm:.2f}) mm.")

    elif cmd == "plot":
        _cmd_plot(args, plotter)

    elif cmd == "draw-shape":
        _cmd_draw_shape(args, plotter)


def _cmd_plot(args, plotter: Plotter):
    path = args.file
    if is_raster(path):
        print(f"Raster detected — tracing with hatchsvg: {path}…")
        path = hatch_to_svg(path)
        print(f"SVG saved to: {path}")
    print(f"Plotting {path}…")
    plotter.plot_svg(path)
    print("Done.")


def _cmd_trace(args):
    scale_pct = args.scale_pct
    if not (1 <= scale_pct <= 100):
        print(f"Error: --scale-pct must be between 1 and 100 (got {scale_pct})", file=sys.stderr)
        sys.exit(1)

    src = args.file
    if args.backend == "hatchsvg":
        out = hatch_to_svg(
            src,
            args.output,
            hatch_angle=args.hatch_angle,
            line_step=args.line_step,
            max_palette=args.max_palette,
            stroke_width=args.stroke_width,
            scale=args.scale,
            arc_radius=args.arc_radius,
            continuous_paths=not args.no_continuous,
            skip_bg=args.skip_bg,
            optimize_travel=not args.no_optimize,
        )
    else:
        out = trace_to_svg(src, args.output, colormode=args.colormode)

    cfg = load_config()
    fit_svg_to_bounds(out, x_max_mm=cfg.x_max_mm, y_max_mm=cfg.y_max_mm, scale_pct=scale_pct)
    print(f"SVG written and fitted to {scale_pct:.0f}% of travel area: {out}")


def _cmd_draw_shape(args, plotter: Plotter):
    import tempfile, os

    shape = args.shape
    kw = {
        "unit": args.unit,
        "x_max_mm": plotter.config.x_max_mm,
        "y_max_mm": plotter.config.y_max_mm,
    }

    try:
        if shape == "rect":
            svg = shapes.rect_svg(args.x, args.y, args.w, args.h, **kw)
        elif shape == "square":
            svg = shapes.square_svg(args.x, args.y, args.side, **kw)
        elif shape == "circle":
            svg = shapes.circle_svg(args.cx, args.cy, args.r, **kw)
        elif shape == "ellipse":
            svg = shapes.ellipse_svg(args.cx, args.cy, args.rx, args.ry, **kw)
        elif shape == "triangle":
            svg = shapes.triangle_svg(args.cx, args.cy, args.side, **kw)
        elif shape == "polygon":
            svg = shapes.polygon_svg(args.cx, args.cy, args.r, args.sides, **kw)
        elif shape == "star":
            svg = shapes.star_svg(args.cx, args.cy, args.r_outer, args.r_inner, args.points, **kw)
        elif shape == "line":
            svg = shapes.line_svg(args.x1, args.y1, args.x2, args.y2, **kw)
        elif shape == "text":
            svg = shapes.text_svg(args.text, args.x, args.y, args.size, args.font, **kw)
        else:
            print(f"Unknown shape: {shape}", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
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
