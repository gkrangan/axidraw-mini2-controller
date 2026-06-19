#!/usr/bin/env bash
# AxiDraw Mini 2 Controller — first-time setup script
# Creates a virtual environment and installs all dependencies.
# Run once: bash setup.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="${PYTHON:-python3}"

echo "========================================"
echo " AxiDraw Mini 2 Controller — Setup"
echo "========================================"
echo ""

# ---- Check Python version ----
PYTHON_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_MAJOR=3
REQUIRED_MINOR=11

echo "Python found: $PYTHON ($PYTHON_VERSION)"

if ! "$PYTHON" -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo ""
    echo "ERROR: Python 3.11 or later is required (found $PYTHON_VERSION)."
    echo "Install it from https://www.python.org/downloads/ or via Homebrew:"
    echo "  brew install python@3.11"
    exit 1
fi

# ---- Create virtual environment ----
if [ -d "$VENV_DIR" ]; then
    echo ""
    echo "Virtual environment already exists at .venv — skipping creation."
else
    echo ""
    echo "Creating virtual environment in .venv ..."
    "$PYTHON" -m venv "$VENV_DIR"
    echo "Done."
fi

# ---- Activate venv ----
source "$VENV_DIR/bin/activate"
echo ""
echo "Virtual environment activated."

# ---- Upgrade pip silently ----
pip install --upgrade pip --quiet

# ---- Install dependencies ----
echo ""
echo "Installing dependencies from requirements.txt ..."
pip install -r "$PROJECT_DIR/requirements.txt"
echo ""
echo "All dependencies installed."

# ---- Check for optional potrace CLI ----
echo ""
if command -v potrace &>/dev/null; then
    echo "✓ potrace found: $(command -v potrace)"
else
    echo "⚠  potrace not found (optional — used as fallback outline tracer)."
    echo "   Install with: brew install potrace"
fi

# ---- Write run.sh convenience launcher ----
LAUNCHER="$PROJECT_DIR/run.sh"
cat > "$LAUNCHER" << 'EOF'
#!/usr/bin/env bash
# Launch the AxiDraw Mini 2 Controller.
# Activates the virtual environment then starts the app.
# Usage:
#   ./run.sh           — launch GUI
#   ./run.sh <args>    — run CLI command, e.g: ./run.sh plot drawing.svg

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/.venv/bin/activate"
python3 "$DIR/main.py" "$@"
EOF
chmod +x "$LAUNCHER"

# ---- Done ----
echo ""
echo "========================================"
echo " Setup complete!"
echo "========================================"
echo ""
echo "To launch the app:"
echo ""
echo "  GUI:  ./run.sh"
echo "  CLI:  ./run.sh plot drawing.svg"
echo "        ./run.sh trace photo.jpg"
echo "        ./run.sh home"
echo ""
echo "Or manually:"
echo "  source .venv/bin/activate"
echo "  python3 main.py"
echo ""
