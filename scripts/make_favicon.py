"""Render the app icon (mine in a hexagon) as a PNG for the web build.

Usage: PYTHONPATH=. python scripts/make_favicon.py <output.png>
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from minesweeper.gui import make_icon  # noqa: E402


def main() -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    pygame.image.save(make_icon(256), sys.argv[1])
    print(f"favicon written to {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
