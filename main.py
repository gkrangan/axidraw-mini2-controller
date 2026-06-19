#!/usr/bin/env python3
"""
AxiDraw Mini 2 Controller
Entry point — launches GUI by default, or routes to CLI when given arguments.
"""

import sys


def main():
    # If any CLI arguments are given (other than the script name), use CLI mode.
    if len(sys.argv) > 1:
        from cli.commands import run
        run()
    else:
        from gui.app import launch
        launch()


if __name__ == "__main__":
    main()
