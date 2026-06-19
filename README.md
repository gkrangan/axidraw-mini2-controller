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
  - [Settings Tab](#settings-tab)
  - [Log Tab](#log-tab)
- [CLI Reference](#cli-reference)
  - [Global Flags](#global-flags)
  - [plot](#plot)
  - [trace](#trace)
  - [draw-shape](#draw-shape)
  - [pen](#pen)
  - [home](#home)
  - [motors](#motors)
- [Image Tracing Backends](#image-tracing-backends)
  - [hatchsvg (default)](#hatchsvg-default)
  - [vtracer / potrace (outline)](#vtracer--potrace-outline)
- [Supported File Formats](#supported-file-formats)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Plot SVG files** directly to the AxiDraw Mini 2
- **Convert raster images** (JPG, PNG, BMP, WebP, GIF, TIFF) to plotter-ready SVG using:
  - **hatchsvg** — hatched, pen-lift-minimised paths (default)
  - **vtracer** — colour/binary outline tracing
  - **potrace** — greyscale outline tracing (CLI fallback)
- **Draw shapes programmatically** — rectangles, circles, polygons, and text
- **Pen control** — raise/lower pen, return to home, enable/disable motors
- **Configurable axis limits** — X max 150 mm, Y max 100 mm
- **Pen angle presets** — 45° angled mount or 90° vertical mount
- **Persistent config** stored in `axidraw-mini2-plotter.cfg`
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
| `pyaxidraw` | Official AxiDraw Python API |
| `customtkinter` | Dark-themed desktop GUI |
| `Pillow` | Image decoding and pre-processing |
| `vtracer` | Raster → outline SVG tracing |
| `hatchsvg` | Raster → hatched plotter SVG |

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/gkrangan/axidraw-mini2-controller.git
cd axidraw-mini2-controller
```

**2. Create and activate a virtual environment (recommended)**

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

> **Note:** `potrace` is an optional CLI fallback for outline tracing and is not installed via pip. On macOS: `brew install potrace`. On Linux: `sudo apt install potrace`.

---

## Project Structure

```
axidraw-mini2-controller/
├── main.py                      # Entry point — GUI by default, CLI when args given
├── axidraw-mini2-plotter.cfg    # Persistent plotter configuration
├── requirements.txt
├── core/
│   ├── plotter.py               # Plotter class and PlotterConfig dataclass
│   ├── image_trace.py           # hatch_to_svg() and trace_to_svg() backends
│   ├── config_io.py             # load_config() / save_config() for .cfg file
│   └── shapes.py                # Programmatic SVG shape generators
├── gui/
│   └── app.py                   # customtkinter GUI application
└── cli/
    └── commands.py              # argparse CLI commands
```

---

## Configuration

### axidraw-mini2-plotter.cfg

All plotter settings are stored in `axidraw-mini2-plotter.cfg` at the project root. This file is loaded automatically on every startup by both the GUI and CLI. Changes made in the GUI **Settings** tab are saved back to this file when you click **Apply & Save Settings**.

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
x_max_mm = 140           # X-axis travel limit in mm (max: 150)
y_max_mm = 90            # Y-axis travel limit in mm (max: 100)

[device]
model = 2                # AxiDraw model (2 = Mini)
port  =                  # Serial port — leave blank for auto-detection
```

You can edit this file directly in a text editor, or use the **Settings** tab in the GUI.

---

### Pen Angle Presets

The `pen_angle` setting selects a preset for `pen_pos_down` and `pen_pos_up` suited to your pen mount:

| Angle | pen_pos_down | pen_pos_up | Use case |
|---|---|---|---|
| `45` | `5` | `30` | Angled mount (default) |
| `90` | `40` | `60` | Vertical mount |

Selecting an angle in the GUI **Settings** tab auto-fills the position fields. You can then fine-tune the values manually before saving.

---

### Axis Travel Limits

The AxiDraw Mini 2 has hard physical limits of **150 mm (X)** and **100 mm (Y)**. The configurable defaults are:

- `x_max_mm = 140` — leaves a 10 mm safety margin on the X axis
- `y_max_mm = 90` — leaves a 10 mm safety margin on the Y axis

Any motion command that would exceed the configured limit raises an error before sending a command to the plotter. The hard caps (150 mm / 100 mm) cannot be exceeded even if you set a higher value in the config.

---

## Running the App

### GUI Mode

Launch with no arguments to open the graphical interface:

```bash
python main.py
```

### CLI Mode

Pass any subcommand to use the CLI instead:

```bash
python main.py <command> [options]
```

---

## GUI Reference

### Sidebar

The left sidebar is always visible and provides quick access to connection and plotter controls.

| Control | Description |
|---|---|
| **Connect / Disconnect** | Opens or closes the USB connection to the AxiDraw |
| **Status indicator** | Green = connected, Red = disconnected |
| **Pen Up / Pen Down** | Raise or lower the pen immediately |
| **Go Home (0, 0)** | Move the pen carriage to the home position |
| **Motors OFF** | Disable stepper motors so you can move the carriage by hand |
| **Load File…** | Open an SVG, JPG, PNG, or BMP file for plotting |
| **▶ Plot** | Plot the currently loaded file |
| **Appearance** | Toggle Dark / Light / System theme |

---

### Draw Shapes Tab

Generate and plot basic shapes directly without loading a file.

#### Rectangle
| Field | Description |
|---|---|
| X, Y (in) | Top-left corner position in inches |
| W, H (in) | Width and height in inches |

#### Circle
| Field | Description |
|---|---|
| CX, CY (in) | Centre position in inches |
| R (in) | Radius in inches |

#### Regular Polygon
| Field | Description |
|---|---|
| CX, CY (in) | Centre position in inches |
| R (in) | Circumradius in inches |
| Sides | Number of sides (e.g. 6 for hexagon) |

#### Text
| Field | Description |
|---|---|
| Text field | The string to draw |
| X, Y (in) | Position in inches |
| Size (pt) | Font size in points |

> **Note:** Text is rendered as SVG `<text>` elements. For best results with the plotter, convert text to paths in Inkscape before plotting.

Click the corresponding **Plot** button to generate the SVG and send it to the plotter immediately.

---

### Image Trace Tab

Convert raster images to SVG before plotting.

**1. Open Image** — click the button to select a JPG, PNG, BMP, WebP, GIF, or TIFF file.

**2. Select a backend:**

#### hatchsvg (hatched) — default

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

#### vtracer / potrace (outline)

Produces clean outline/vector SVG. Best for logos, line art, or simple graphics.

| Option | Default | Description |
|---|---|---|
| Color mode | binary | `binary` (black/white), `color`, or `layered` |
| Filter speckle (px) | 4 | Remove noise smaller than N pixels |

**3. Click an action:**

| Button | Description |
|---|---|
| **Trace to SVG** | Convert the image and save the SVG (no plotting) |
| **Trace & Plot** | Convert then immediately send to the plotter |

---

### Settings Tab

Configure all plotter parameters. Values are pre-filled from `axidraw-mini2-plotter.cfg` on startup.

| Setting | Description |
|---|---|
| **Pen mount angle** | `45°` or `90°` — auto-fills pen position presets |
| **Pen pos down (0–100)** | Servo position when pen touches paper |
| **Pen pos up (0–100)** | Servo position when pen is raised |
| **Speed (pen down)** | Movement speed while drawing (1–100) |
| **Speed (pen up)** | Movement speed while travelling (1–100) |
| **Pen delay down (ms)** | Wait time after lowering pen before moving |
| **Pen delay up (ms)** | Wait time after raising pen before moving |
| **X-axis limit mm** | Configurable X travel limit (max 150 mm) |
| **Y-axis limit mm** | Configurable Y travel limit (max 100 mm) |
| **Serial port** | Leave blank for auto-detection |
| **Constant speed mode** | Disable acceleration/deceleration |

Click **Apply & Save Settings** to apply changes immediately (if connected) and write them back to `axidraw-mini2-plotter.cfg`.

---

### Log Tab

Displays a timestamped activity log of all actions, traces, plot events, and errors. Click **Clear Log** to reset it.

---

## CLI Reference

### Global Flags

These flags apply to all commands and override the corresponding values in `axidraw-mini2-plotter.cfg`.

```
--port PORT           Serial port (default: auto-detect)
--speed-down N        Pen-down speed 1–100
--speed-up N          Pen-up speed 1–100
--pen-angle {45,90}   Pen mount angle — loads position preset
--pen-down N          Pen-down servo position 0–100 (overrides angle preset)
--pen-up N            Pen-up servo position 0–100 (overrides angle preset)
--x-max MM            X-axis travel limit in mm (max 150)
--y-max MM            Y-axis travel limit in mm (max 100)
```

---

### plot

Plot an SVG, JPG, PNG, BMP, WebP, GIF, or TIFF file. Raster images are automatically converted to SVG via hatchsvg before plotting.

```bash
python main.py plot <file>
```

**Examples:**

```bash
# Plot an SVG file
python main.py plot drawing.svg

# Plot a photo (auto-traced with hatchsvg)
python main.py plot photo.jpg

# Plot with custom speed and pen angle
python main.py --speed-down 15 --pen-angle 90 plot drawing.svg
```

---

### trace

Convert a raster image to SVG without plotting.

```bash
python main.py trace [options] <file>
```

**Options:**

```
-o, --output PATH          Output SVG path (default: same directory as input)
--backend {hatchsvg,outline}  Tracing backend (default: hatchsvg)

hatchsvg options:
  --hatch-angle DEGREES    Hatch line angle (default: 45.0)
  --line-step PX           Hatch line spacing in pixels (default: 4)
  --max-palette N          Max colour layers (default: 12)
  --stroke-width N         SVG stroke width (default: 0.5)
  --scale N                Image scale factor (default: 1.0)
  --arc-radius N           U-turn arc smoothing radius (default: 2.0)
  --no-continuous          Disable serpentine continuous paths
  --skip-bg                Skip background colour layer
  --no-optimize            Disable layer travel order optimisation

outline options:
  --colormode {binary,color,layered}  Trace colour mode (default: binary)
```

**Examples:**

```bash
# Hatch-trace a photo (default)
python main.py trace photo.jpg

# Hatch-trace with custom angle and density
python main.py trace photo.jpg --hatch-angle 30 --line-step 6

# Save to a specific output path
python main.py trace photo.png -o /tmp/output.svg

# Outline trace using vtracer/potrace
python main.py trace logo.png --backend outline --colormode color

# Skip background, optimise travel
python main.py trace photo.jpg --skip-bg --hatch-angle 45
```

---

### draw-shape

Draw a basic shape directly to the plotter.

```bash
python main.py draw-shape <shape> [dimensions]
```

#### rect

```bash
python main.py draw-shape rect <x> <y> <width> <height>
```

All values in inches.

```bash
# Draw a 3×2 inch rectangle at position (0.5, 0.5)
python main.py draw-shape rect 0.5 0.5 3.0 2.0
```

#### circle

```bash
python main.py draw-shape circle <cx> <cy> <radius>
```

```bash
# Draw a circle centred at (2, 1.5) with radius 1 inch
python main.py draw-shape circle 2.0 1.5 1.0
```

#### polygon

```bash
python main.py draw-shape polygon <cx> <cy> <radius> <sides>
```

```bash
# Draw a hexagon
python main.py draw-shape polygon 2.0 1.5 1.0 6

# Draw a triangle
python main.py draw-shape polygon 2.0 1.5 1.0 3
```

#### text

```bash
python main.py draw-shape text "<string>" <x> <y> [--size PT]
```

```bash
# Draw text at (0.5, 1.0) at 24pt
python main.py draw-shape text "Hello World" 0.5 1.0 --size 24
```

---

### pen

Raise or lower the pen without moving.

```bash
python main.py pen up
python main.py pen down
```

---

### home

Move the pen carriage to the home position (0, 0).

```bash
python main.py home
```

---

### motors

Enable or disable the stepper motors. Disabling the motors lets you move the carriage by hand.

```bash
python main.py motors off
python main.py motors on
```

---

## Image Tracing Backends

### hatchsvg (default)

[hatchsvg](https://pypi.org/project/hatchsvg/) converts raster images into hatched SVG files optimised for pen plotters. It quantizes the image into colour layers and fills each with parallel hatch lines using serpentine paths to minimise pen lifts.

**Best for:** photographs, illustrations, images with colour areas.

Key parameters:
- **Hatch angle** — direction of hatch lines (45° is a good default)
- **Line step** — spacing between lines; lower values = denser, more detail, longer plot time
- **Continuous paths** — serpentine row-by-row movement; dramatically reduces pen lifts
- **Arc radius** — softens U-turns at row ends to reduce carriage vibration/ringing

### vtracer / potrace (outline)

Outline tracers convert raster images to vector outlines without fill. `vtracer` is a Python library; `potrace` is a separate CLI tool used as a fallback.

**Best for:** logos, line art, silhouettes, QR codes.

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
- Check the USB cable is plugged in and the AxiDraw is powered on
- Try specifying the port manually: `--port /dev/tty.usbmodem*` (macOS/Linux) or `--port COM3` (Windows)
- On macOS, you may need to install the EiBotBoard USB driver from Evil Mad Scientist

**`pyaxidraw` not found**
```bash
pip install pyaxidraw
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

**Motion out of range error**
- The pen is being asked to move beyond the configured axis limit
- Check `x_max_mm` and `y_max_mm` in `axidraw-mini2-plotter.cfg` or in the Settings tab
- Hard limits are 150 mm (X) and 100 mm (Y) and cannot be exceeded

**Pen not touching paper / lifting too far**
- Adjust `pen_pos_down` and `pen_pos_up` in the Settings tab
- For a 45° angled mount: `pen_pos_down = 5`, `pen_pos_up = 30`
- For a 90° vertical mount: `pen_pos_down = 40`, `pen_pos_up = 60`
- Use the **Pen Up** / **Pen Down** sidebar buttons to test positions live

**GUI won't launch**
```bash
pip install customtkinter
```
