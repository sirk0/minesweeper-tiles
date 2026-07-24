"""Render the app icons for the web build and wire them into index.html.

Writes the browser tab favicon plus an iOS "Add to Home Screen" icon (the
same flat teal mine-in-hexagon plate as the macOS dock) and adds the
`apple-touch-icon` <link> pygbag's template omits, so an iPhone
home-screen shortcut shows the app icon instead of a screenshot of the
page.

Usage: PYTHONPATH=. python scripts/make_web_icons.py <web-output-dir>
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from minesweeper.gui import make_icon  # noqa: E402

APPLE_ICON = "apple-touch-icon.png"
APPLE_LINK = f'<link rel="apple-touch-icon" href="{APPLE_ICON}">'


def add_apple_link(index: Path) -> None:
    """Insert the apple-touch-icon <link> into index.html (idempotent)."""
    if not index.is_file():
        return
    html = index.read_text(encoding="utf-8")
    if "apple-touch-icon" in html:
        return
    index.write_text(
        html.replace("</head>", f"    {APPLE_LINK}\n</head>", 1),
        encoding="utf-8",
    )


def main() -> int:
    out = Path(sys.argv[1])
    pygame.init()
    pygame.display.set_mode((1, 1))
    # Browser tab favicon: the dock icon as-is (rounded teal plate on a
    # transparent margin), which browsers render at small sizes fine.
    pygame.image.save(make_icon(256), str(out / "favicon.png"))
    # iOS masks the home-screen icon into its own rounded square and paints
    # transparency black, so render the plate full-bleed and let iOS do the
    # rounding — the result matches the macOS dock icon.
    pygame.image.save(make_icon(180, bleed=True), str(out / APPLE_ICON))
    add_apple_link(out / "index.html")
    print(f"web icons written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
