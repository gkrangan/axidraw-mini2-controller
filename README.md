# AxiDraw Mini 2 Controller

A Python application for controlling the **CNS AxiDraw Mini 2** drawing robot. Provides both a graphical desktop interface (GUI) and a command-line interface (CLI) for plotting SVG files, converting raster images to plotter-ready SVG, and drawing shapes programmatically.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
  - [axidraw-mini2-plotter.cfg](#axidraw-mini2-plottercfg)
  - [Pen Angle Presets](#pen-angle-presets)
  - [Axis Travel Limits](#axis-travel-limits)
- [Running the App](#running-the-app)
  - [GUI Mode](#gui-mode)
  - [CLI Mode](#cli-mode)
- [GUI Reference](#gui-reference)
  - [Sidebar](#sidebar)
  - [Draw Shapes Tab](#draw-shapes-tab)
  - [Image Trace Tab](#image-trace-tab)
  - [Manual Control Tab](#manual-control-tab)
  - [Settings Tab](#settings-tab)
  - [Log Tab](#log-tab)
- [CLI Reference](#cli-reference)
  - [Global Flags](#global-flags)
  - [plot](#plot)
  - [trace](#trace)
  - [draw-shape](#draw-shape)
  - [pen](#pen)
  - [motors](#motors)
  - [set-home](#set-home)
  - [home](#home)
  - [origin](#origin)
  - [move](#move)
  - [jog](#jog)
- [Image Tracing Backends](#image-tracing-backends)
- [Supported File Formats](#supported-file-formats)
- [Troubleshooting](#troubleshooting)
- [Resources & References](#resources--references)

---

## Features

- **Plot SVG files** directly to the AxiDraw Mini 2
- **Convert raster images** (JPG, PNG, BMP, WebP, GIF, TIFF) to plotter-ready SVG using:
  - **vtracer / potrace** — clean outline/vector tracing (default)
  - **hatchsvg** — hatched, pen-lift-minimised paths
- **Draw shapes programmatically** — rectangle, square, circle, ellipse, equilateral triangle, regular polygon, star, line, and text — in **mm or inches**
- **Out-of-bounds protection** — every shape and traced image is checked against the configured travel limits and the hard physical caps before any motion command is sent
- **Image scale-to-fit** — traced images are automatically scaled and centred within the plottable area; scale percentage is configurable
- **Text rendering via Hershey stroke fonts** — single-stroke fonts designed for pen plotters, converted directly to `<path>` elements (pyaxidraw ignores SVG `<text>` elements)
- **Manual Control tab** — jog pad, pen up/down, motor enable/disable, set/go-to home, move to XY
- **Emergency cancel** — Cancel Job button stops any active plot immediately, raises the pen, and returns the carriage to home
- **Reliable pen control** — `update()` called before every interactive command to prevent the EiBotBoard dropping commands after the first call
- **Pen angle presets** — 45° angled mount or 90° vertical mount
- **Configurable axis limits** — X max 150 mm hard cap, Y max 100 mm hard cap; configurable defaults 140 × 90 mm
- **Persistent config** stored in `axidraw-mini2-plotter.cfg`
- **Virtual environment** — one-command setup via `setup.sh`
- **Dark-themed GUI** built with customtkinter
- **CLI** for scripting and automation

---

## Requirements

- Python 3.11+
- AxiDraw Mini 2 connected via USB
- macOS / Linux / Windows

Python dependencies (installed via `pip`):

| Package | Purpose |
|---|---|
| `pyaxidraw` | Official AxiDraw Python API (installed from Evil Mad Scientist CDN) |
| `customtkinter` | Dark-themed desktop GUI |
| `Pillow` | Image decoding and pre-processing |
| `vtracer` | Raster → outline SVG tracing |
| `hatchsvg` | Raster → hatched plotter SVG |
| `hershey-fonts` | Single-stroke stroke fonts for plotter text rendering |

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/gkrangan/axidraw-mini2-controller.git
cd axidraw-mini2-controller
```

**2. Run the setup script (first time only)**

```bash
bash setup.sh
```

`setup.sh` will:
- Verify Python 3.11+ is available
- Create a `.venv` virtual environment
- Install `pyaxidraw` directly from the Evil Mad Scientist CDN
- Install all remaining dependencies from `requirements.txt`
- Check for the optional `potrace` CLI and warn if missing
- Generate a `run.sh` convenience launcher

**3. Launch the app**

```bash
./run.sh            # GUI mode
./run.sh plot drawing.svg   # CLI mode
```

That's it. Every subsequent session just needs `./run.sh`.

---

### Manual setup (alternative)

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
pip install https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip
pip install -r requirements.txt
python3 main.py
```

> **Note:** `potrace` is an optional CLI fallback for outline tracing. On macOS: `brew install potrace`. On Linux: `sudo apt install potrace`.

---

## Project Structure

```
axidraw-mini2-controller/
├── main.py                      # Entry point — GUI by default, CLI when args given
├── setup.sh                     # First-time setup: creates .venv and installs deps
├── run.sh                       # Generated by setup.sh — activates venv and launches app
├── axidraw-mini2-plotter.cfg    # Persistent plotter configuration
├── requirements.txt
├── core/
│   ├── plotter.py               # Plotter class and PlotterConfig dataclass
│   ├── image_trace.py           # hatch_to_svg(), trace_to_svg(), fit_svg_to_bounds()
│   ├── config_io.py             # load_config() / save_config() for .cfg file
│   └── shapes.py                # Programmatic SVG shape generators (mm/in, bounds-checked)
├── gui/
│   └── app.py                   # customtkinter GUI application
└── cli/
    └── commands.py              # argparse CLI commands
```

> `run.sh` and `.venv/` are gitignored — generated per machine by `setup.sh`.

---

## Configuration

### axidraw-mini2-plotter.cfg

All plotter settings are stored in `axidraw-mini2-plotter.cfg` at the project root. Loaded automatically on every startup. Changes made in the GUI **Settings** tab are written back when you click **Apply & Save Settings**.

```ini
[motion]
speed_pendown  = 25      # Pen-down movement speed (1–100)
speed_penup    = 75      # Pen-up movement speed (1–100)
pen_delay_down = 0       # Delay (ms) after lowering pen
pen_delay_up   = 0       # Delay (ms) after raising pen
const_speed    = false   # Constant speed mode (true/false)

[pen]
pen_angle    = 45        # Mount angle: 45 or 90 degrees
pen_pos_down = 5         # Servo position when pen is down (0–100)
pen_pos_up   = 30        # Servo position when pen is up (0–100)

[travel]
x_max_mm = 140           # X-axis travel limit in mm (hard cap: 150)
y_max_mm = 90            # Y-axis travel limit in mm (hard cap: 100)

[device]
model = 2                # AxiDraw model (2 = Mini)
port  =                  # Serial port — leave blank for auto-detection
```

---

### Pen Angle Presets

| Angle | pen_pos_down | pen_pos_up | Use case |
|---|---|---|---|
| `45` (default) | `5` | `30` | Angled mount |
| `90` | `40` | `60` | Vertical mount |

Selecting an angle in the **Settings** tab auto-fills the position fields. You can then fine-tune them manually before saving.

---

### Axis Travel Limits

The AxiDraw Mini 2 has hard physical caps of **150 mm (X)** and **100 mm (Y)**. The configurable defaults are:

- `x_max_mm = 140` — 10 mm safety margin on X
- `y_max_mm = 90` — 10 mm safety margin on Y

Every shape, text, and motion command checks the full bounding box against these limits before sending anything to the plotter. The hard caps cannot be exceeded regardless of config values.

---

## Running the App

### GUI Mode

```bash
./run.sh
```

### CLI Mode

```bash
./run.sh <command> [options]
```

---

## GUI Reference

### Sidebar

Always visible. Provides quick access to connection and core controls.

| Control | Description |
|---|---|
| **Connect / Disconnect** | Opens or closes the USB connection to the AxiDraw |
| **Status indicator** | Green = connected, Red = disconnected |
| **Pen Up / Pen Down** | Raise or lower the pen immediately |
| **Go Home (0, 0)** | Move the pen carriage to the home position |
| **Motors OFF** | Disable stepper motors — carriage can be moved freely by hand |
| **Load File…** | Open an SVG, JPG, PNG, or other supported raster file |
| **▶ Plot** | Plot the currently loaded file |
| **⬛ Cancel Job** | Emergency stop — halts the active job, raises the pen, returns to home. Enabled only while a job is running. |
| **Appearance** | Toggle Dark / Light / System theme |

---

### Draw Shapes Tab

Generate and plot shapes directly without loading a file.

#### Units

A **mm / in toggle** at the top of the tab applies to all shape fields. Switching the unit relabels every field and swaps the default values automatically.

#### Shapes

| Shape | Fields | Notes |
|---|---|---|
| **Rectangle** | X, Y (top-left corner), W (width), H (height) | |
| **Square** | X, Y (top-left corner), Side | Equal width and height |
| **Circle** | CX, CY (centre), R (radius) | |
| **Ellipse** | CX, CY (centre), RX (x-radius), RY (y-radius) | |
| **Equilateral Triangle** | CX, CY (centre), Side (side length) | Flat base, apex pointing up |
| **Regular Polygon** | CX, CY (centre), R (circumradius), Sides | e.g. Sides=6 for hexagon |
| **Star** | CX, CY (centre), R Out, R In, Points | R In ≈ 0.4–0.5 × R Out for a classic star |
| **Line** | X1, Y1, X2, Y2 | Straight line between two points |
| **Text** | Text string, X, Y (baseline start), Size (pt), Font | Rendered as Hershey stroke font paths |

#### Text fonts

Hershey stroke fonts are single-stroke vector fonts designed specifically for pen plotters. Available fonts:

| Font name | Style |
|---|---|
| `futural` (default) | Sans-serif, lightweight |
| `futuram` | Sans-serif, bold |
| `cursive` | Italic cursive |
| `gothgbt` | Gothic |
| `gothgrt` | Gothic rounded |
| `scripts` | Script |
| `cyrillic` | Cyrillic alphabet |

#### Bounds checking

Every shape calculates its full bounding box (all vertices for polygons and stars) before generating SVG. If any edge exceeds the configured travel limits or the hard physical caps, a clear error is shown and nothing is sent to the plotter.

---

### Image Trace Tab

Convert raster images to SVG before plotting.

**1. Open Image** — select a JPG, PNG, BMP, WebP, GIF, or TIFF file.

**2. Set Fill %** — the traced image will be scaled to fill this percentage of the plotter's travel area and centred automatically. Range: 1–100 (default: 90). The scale factor is capped so the output can never exceed the configured travel limits.

**3. Select a backend:**

#### vtracer / potrace (outline) — default

Produces clean outline/vector SVG. Best for logos, line art, and simple graphics.

| Option | Default | Description |
|---|---|---|
| Color mode | binary | `binary` (black/white), `color`, or `layered` |
| Filter speckle (px) | 4 | Remove noise smaller than N pixels |

> vtracer runs in an isolated subprocess to prevent its native Rust extension from crashing the GUI. If vtracer fails for any reason, the tracer automatically falls back to potrace.

#### hatchsvg (hatched)

Produces plotter-optimised SVG with hatched fill lines, colour layers, and minimised pen lifts. Best for photographic or detailed images.

| Option | Default | Description |
|---|---|---|
| Hatch angle (°) | 45 | Angle of hatch lines |
| Line step (px) | 4 | Spacing between hatch lines; smaller = denser |
| Max palette colours | 12 | Maximum number of colour layers |
| Stroke width | 0.5 | SVG stroke width for hatch lines |
| Scale | 1.0 | Resize image before tracing |
| Arc radius (U-turns) | 2.0 | Smooth arc at row-end reversals; reduces carriage vibration |
| Continuous paths | ✓ | Serpentine paths to minimise pen lifts |
| Skip background colour | ☐ | Omit the dominant background layer |
| Optimise layer travel order | ✓ | Reorder colour layers to reduce total pen-up distance |

**4. Click an action:**

| Button | Description |
|---|---|
| **Trace to SVG** | Convert and save the SVG (no plotting) |
| **Trace & Plot** | Convert, scale-to-fit, then immediately send to the plotter |

---

### Manual Control Tab

Full interactive control without plotting a file.

#### Position Display

Live display of the current **X / Y position** and **Home X / Y position** in mm, updated after every move.

#### Pen

| Button | Description |
|---|---|
| **Pen Up** | Raise the pen off the paper |
| **Pen Down** | Lower the pen onto the paper |

#### Motors

| Button | Description |
|---|---|
| **Enable Motors** | Engage the stepper motors (normal operating state) |
| **Disable Motors** | Release the steppers — carriage can be moved freely by hand |

#### Home Position

> The AxiDraw has no hardware home sensor. The **machine origin (0, 0)** is the physical position of the carriage at the moment you connected. **Set Home Here** defines a logical home anywhere on the work area.

| Button | Description |
|---|---|
| **Set Home Here** | Mark the current carriage position as user home |
| **Go to Home** | Move to the user-defined home position (pen up) |
| **Go to Origin (0, 0)** | Return to the machine origin — where the carriage was at connect time |

#### Jog Pad

Eight-direction jog pad for nudging the carriage:

```
↖  ↑  ↗
←  ⌂  →      ⌂ = Go to Home
↙  ↓  ↘
```

**Step size:** 0.1 / 0.5 / 1 / 5 / 10 / 20 mm per click.

#### Move to Position

Enter an absolute X and Y coordinate in mm and click **Move** to send the carriage there directly (pen up).

---

### Settings Tab

Configure all plotter parameters. Pre-filled from `axidraw-mini2-plotter.cfg` on startup.

| Setting | Description |
|---|---|
| **Pen mount angle** | `45°` or `90°` — auto-fills pen position presets |
| **Pen pos down (0–100)** | Servo position when pen touches paper |
| **Pen pos up (0–100)** | Servo position when pen is raised |
| **Speed (pen down)** | Movement speed while drawing (1–100) |
| **Speed (pen up)** | Movement speed while travelling (1–100) |
| **Pen delay down (ms)** | Wait after lowering pen before moving |
| **Pen delay up (ms)** | Wait after raising pen before moving |
| **X-axis limit mm** | Configurable X travel limit (hard cap: 150 mm) |
| **Y-axis limit mm** | Configurable Y travel limit (hard cap: 100 mm) |
| **Serial port** | Leave blank for auto-detection |
| **Constant speed mode** | Disable acceleration/deceleration |

Click **Apply & Save Settings** to apply immediately and write back to `axidraw-mini2-plotter.cfg`.

---

### Log Tab

Timestamped activity log of all actions, traces, plot events, and errors. Click **Clear Log** to reset.

---

## CLI Reference

### Global Flags

Apply to all commands; override values in `axidraw-mini2-plotter.cfg`.

```
--port PORT           Serial port (default: auto-detect)
--speed-down N        Pen-down speed 1–100
--speed-up N          Pen-up speed 1–100
--pen-angle {45,90}   Pen mount angle — loads position preset
--pen-down N          Pen-down servo position 0–100 (overrides angle preset)
--pen-up N            Pen-up servo position 0–100 (overrides angle preset)
--x-max MM            X-axis travel limit in mm (hard cap: 150)
--y-max MM            Y-axis travel limit in mm (hard cap: 100)
```

---

### plot

Plot an SVG or raster image. Raster images are auto-traced with hatchsvg before plotting.

```bash
./run.sh plot <file>
```

```bash
./run.sh plot drawing.svg
./run.sh plot photo.jpg
./run.sh --speed-down 15 --pen-angle 90 plot drawing.svg
```

---

### trace

Convert a raster image to SVG without plotting. The output SVG is automatically scaled and centred to fit the plotter travel area.

```bash
./run.sh trace [options] <file>
```

**Options:**

```
-o, --output PATH                   Output SVG path (default: same dir as input)
--backend {outline,hatchsvg}        Tracing backend (default: outline)
--scale-pct PCT                     Fill PCT% of travel area after tracing (1–100, default: 90)

outline options:
  --colormode {binary,color,layered}  Colour mode (default: binary)

hatchsvg options:
  --hatch-angle DEGREES             Hatch line angle (default: 45.0)
  --line-step PX                    Hatch spacing in pixels (default: 4)
  --max-palette N                   Max colour layers (default: 12)
  --stroke-width N                  SVG stroke width (default: 0.5)
  --scale N                         Image scale factor before hatch processing (default: 1.0)
  --arc-radius N                    U-turn arc smoothing radius (default: 2.0)
  --no-continuous                   Disable serpentine continuous paths
  --skip-bg                         Skip background colour layer
  --no-optimize                     Disable layer travel order optimisation
```

```bash
# Outline trace (default), fill 90% of travel area
./run.sh trace logo.png

# Outline trace, fill only 70%
./run.sh trace logo.png --scale-pct 70

# Colour outline trace
./run.sh trace logo.png --colormode color

# Hatch trace a photo
./run.sh trace photo.jpg --backend hatchsvg --hatch-angle 30 --line-step 6

# Save to a specific output path
./run.sh trace photo.png -o /tmp/output.svg
```

---

### draw-shape

Draw a shape and plot it. All dimension arguments use the unit specified by `--unit` (default: mm).

```bash
./run.sh draw-shape <shape> [dimensions] [--unit {mm,in}]
```

#### rect

```bash
./run.sh draw-shape rect <x> <y> <w> <h>
./run.sh draw-shape rect 10 10 50 30              # mm (default)
./run.sh draw-shape rect 0.5 0.5 2.0 1.2 --unit in
```

#### square

```bash
./run.sh draw-shape square <x> <y> <side>
./run.sh draw-shape square 10 10 40
```

#### circle

```bash
./run.sh draw-shape circle <cx> <cy> <r>
./run.sh draw-shape circle 70 45 20
```

#### ellipse

```bash
./run.sh draw-shape ellipse <cx> <cy> <rx> <ry>
./run.sh draw-shape ellipse 70 45 30 15
```

#### triangle

Equilateral triangle centred at (cx, cy) with given side length.

```bash
./run.sh draw-shape triangle <cx> <cy> <side>
./run.sh draw-shape triangle 70 45 40
```

#### polygon

Regular polygon centred at (cx, cy) with circumradius r.

```bash
./run.sh draw-shape polygon <cx> <cy> <r> <sides>
./run.sh draw-shape polygon 70 45 25 6      # hexagon
./run.sh draw-shape polygon 70 45 25 3      # triangle
```

#### star

N-pointed star. `r_inner` is typically 0.4–0.5 × `r_outer`.

```bash
./run.sh draw-shape star <cx> <cy> <r_outer> <r_inner> <points>
./run.sh draw-shape star 70 45 25 12 5      # 5-point star
./run.sh draw-shape star 70 45 25 12 8      # 8-point star
```

#### line

```bash
./run.sh draw-shape line <x1> <y1> <x2> <y2>
./run.sh draw-shape line 10 10 130 80
```

#### text

Rendered using Hershey stroke fonts — plotter-native single-stroke paths.

```bash
./run.sh draw-shape text "<string>" <x> <y> [--size PT] [--font NAME] [--unit {mm,in}]
./run.sh draw-shape text "Hello World" 10 40 --size 14
./run.sh draw-shape text "Hello" 10 40 --font cursive --size 18
```

Available `--font` values: `futural` (default), `futuram`, `cursive`, `gothgbt`, `gothgrt`, `scripts`, `cyrillic`.

---

### pen

```bash
./run.sh pen up
./run.sh pen down
```

---

### motors

```bash
./run.sh motors on
./run.sh motors off
```

---

### set-home

Mark the current carriage position as user home.

```bash
./run.sh set-home
```

---

### home

Move to the user-defined home position (pen up).

```bash
./run.sh home
```

---

### origin

Move to the machine origin (0, 0) — the position the carriage was at on connect.

```bash
./run.sh origin
```

---

### move

Move to an absolute position in mm (pen up).

```bash
./run.sh move <x_mm> <y_mm>
./run.sh move 50 30
```

---

### jog

Move relative to current position in mm (pen up). Negative values move left / up.

```bash
./run.sh jog <dx_mm> <dy_mm>
./run.sh jog 5 0       # nudge 5 mm right
./run.sh jog -10 -5    # nudge 10 mm left, 5 mm up
```

---

## Image Tracing Backends

### vtracer / potrace (outline) — default

Converts raster images to clean vector outlines without fill. Best for logos, line art, silhouettes, and QR codes.

- **vtracer** — Python library, runs in an isolated subprocess (prevents native Rust crashes from affecting the GUI). Falls back to potrace automatically if it fails.
- **potrace** — CLI tool, used as the automatic fallback. Install with `brew install potrace` (macOS) or `sudo apt install potrace` (Linux).

### hatchsvg

[hatchsvg](https://pypi.org/project/hatchsvg/) converts raster images into hatched SVG files optimised for pen plotters. It quantises the image into colour layers and fills each with parallel hatch lines using serpentine paths to minimise pen lifts.

Best for photographs, illustrations, and images with colour areas.

Key parameters:
- **Hatch angle** — direction of hatch lines (45° is a good default)
- **Line step** — spacing between lines; lower = denser, more detail, longer plot time
- **Continuous paths** — serpentine row-by-row movement; dramatically reduces pen lifts
- **Arc radius** — softens U-turns at row ends to reduce carriage vibration/ringing

### Scale-to-fit (both backends)

After tracing, the SVG is automatically transformed to:
1. Scale the content uniformly to fill the requested percentage of the plotter travel area (preserving aspect ratio)
2. Centre the image within the travel area
3. Set the SVG canvas to exactly match the plotter limits

This ensures the traced image can never exceed the physical travel limits regardless of the original image size or resolution.

---

## Supported File Formats

| Format | hatchsvg | vtracer / potrace |
|---|---|---|
| `.svg` | — | Direct plot (no tracing needed) |
| `.jpg` / `.jpeg` | ✓ | ✓ |
| `.png` | ✓ | ✓ |
| `.bmp` | ✓ | ✓ |
| `.webp` | ✓ | ✗ |
| `.gif` | ✓ | ✗ |
| `.tiff` / `.tif` | ✓ | ✗ |

---

## Troubleshooting

**AxiDraw not detected on connect**
- Check the USB cable and that the AxiDraw is powered on
- Specify the port manually: `--port /dev/tty.usbmodem*` (macOS/Linux) or `--port COM3` (Windows)
- On macOS, you may need the EiBotBoard USB driver from Evil Mad Scientist

**`pyaxidraw` not found**

`pyaxidraw` is not on PyPI. Install directly from Evil Mad Scientist:
```bash
pip install https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip
```

**`hershey-fonts` not found**
```bash
pip install hershey-fonts
```

**`hatchsvg` not found**
```bash
pip install hatchsvg
```

**`vtracer` not found**
```bash
pip install vtracer
```

**`potrace` not found**
```bash
brew install potrace          # macOS
sudo apt install potrace      # Ubuntu/Debian
```

**Segmentation fault during image trace**

This is caused by vtracer's Rust native extension crashing on certain image inputs. The fix is already in place — vtracer runs in an isolated subprocess, so a crash there cannot affect the GUI. The tracer falls back to potrace automatically. If potrace is also unavailable, install it (see above).

**Pen up/down only works the first time after connecting**

This was a known issue with pyaxidraw's interactive session going stale after the first command. Fixed — `update()` is now called before every interactive command (pen, move, motors) to keep the EiBotBoard session active.

**Cancelling a job mid-plot**

Press **⬛ Cancel Job** in the sidebar at any time during a plot. The app will:
1. Interrupt the active plot by disconnecting from the plotter
2. Immediately reconnect, raise the pen, and move to home
3. Leave the connection open so you can continue working

The connection is automatically re-established after cancel — you do not need to manually reconnect.

**Motion out of range error**
- A shape or move command is trying to exceed the configured axis limit
- Check `x_max_mm` and `y_max_mm` in `axidraw-mini2-plotter.cfg` or in the Settings tab
- Hard limits are 150 mm (X) and 100 mm (Y) and cannot be exceeded under any circumstances

**Shape / text not appearing on paper**
- Adjust `pen_pos_down` in Settings — the pen may not be pressing hard enough
- For a 45° angled mount: `pen_pos_down = 5`, `pen_pos_up = 30`
- For a 90° vertical mount: `pen_pos_down = 40`, `pen_pos_up = 60`
- Use **Pen Down** in the sidebar to test the position live

**Text not plotting**

Text is rendered using Hershey stroke fonts which produce SVG `<path>` elements. This is required because pyaxidraw ignores SVG `<text>` elements entirely. If text is not plotting, check the Log tab for errors from the `hershey-fonts` package.

**GUI won't launch**
```bash
pip install customtkinter
```

---

## Resources & References

### AxiDraw Hardware & Official Software

- [AxiDraw MiniKit 2 — Evil Mad Scientist product page](https://shop.evilmadscientist.com/productsmenu/924)
- [AxiDraw Python Module documentation](https://axidraw.com/doc/py_api/#)
- [EiBotBoard firmware & USB driver](https://evil-mad.github.io/EggBot/ebb.html) — required for USB communication on all platforms
- [AxiDraw CLI & Inkscape extension](https://github.com/evil-mad/axidraw) — official Evil Mad Scientist GitHub

### Python Libraries

| Library | PyPI | Description |
|---|---|---|
| `pyaxidraw` | CDN install (see above) | Official AxiDraw Python API |
| `hatchsvg` | [pypi.org/project/hatchsvg](https://pypi.org/project/hatchsvg/) | Raster → hatched plotter SVG |
| `vtracer` | [pypi.org/project/vtracer](https://pypi.org/project/vtracer/) | Raster → outline SVG tracing |
| `hershey-fonts` | [pypi.org/project/hershey-fonts](https://pypi.org/project/hershey-fonts/) | Single-stroke plotter fonts |
| `customtkinter` | [pypi.org/project/customtkinter](https://pypi.org/project/customtkinter/) | Modern dark-themed tkinter GUI |
| `Pillow` | [pypi.org/project/Pillow](https://pypi.org/project/Pillow/) | Image decoding and processing |

### External Tools

- [potrace](http://potrace.sourceforge.net/) — greyscale bitmap to vector outline tracer (automatic fallback)
- [Inkscape](https://inkscape.org/) — free SVG editor; useful for preparing and converting files before plotting

### Image Tracing References

- [hatchsvg on PyPI](https://pypi.org/project/hatchsvg/) — hatching algorithm, `RenderParams` options, and supported formats
- [vtracer on PyPI](https://pypi.org/project/vtracer/) — colour quantisation and outline tracing parameters
- [Generative SVG for Pen Plotters (Python)](https://tabreturn.github.io/code/python/svg/thonny/2022/02/03/generative_svg_for_pen_plotters_using_python.html) — guide on generating plotter-ready SVG with Python

### Pen Plotter Community

- [DrawingBots.net](https://drawingbots.net/) — community resource for pen plotter tools, tips, and SVG resources
- [r/PlotterArt](https://www.reddit.com/r/PlotterArt/) — Reddit community for pen plotter art and troubleshooting
