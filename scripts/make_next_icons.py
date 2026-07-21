"""Render the PWA icons for the TypeScript ("/next/") web app.

Reuses the in-game mine-in-hexagon plate (`minesweeper.gui.make_icon`) so the
TS app's browser tab, install icon and iOS home-screen icon match the Python
build and the macOS dock. Outputs go under `web/public/`:

    icons/icon-192.png icons/icon-512.png icons/maskable-512.png
    apple-touch-icon.png favicon.svg

Usage: PYTHONPATH=. python scripts/make_next_icons.py
"""

import base64
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from minesweeper.gui import make_icon  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "web" / "public"


def _png_bytes(surface: pygame.Surface) -> bytes:
    tmp = OUT / "_tmp.png"
    pygame.image.save(surface, str(tmp))
    data = tmp.read_bytes()
    tmp.unlink()
    return data


def main() -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    (OUT / "icons").mkdir(parents=True, exist_ok=True)

    # Standard install icons (rounded plate on transparent margin).
    pygame.image.save(make_icon(192), str(OUT / "icons" / "icon-192.png"))
    pygame.image.save(make_icon(512), str(OUT / "icons" / "icon-512.png"))
    # Maskable + apple-touch: full-bleed so the platform mask does the rounding.
    pygame.image.save(make_icon(512, bleed=True), str(OUT / "icons" / "maskable-512.png"))
    pygame.image.save(make_icon(180, bleed=True), str(OUT / "apple-touch-icon.png"))

    # favicon.svg: embed the 256px plate as a data URI inside a tiny SVG so the
    # browser tab icon stays crisp without an extra raster request.
    b64 = base64.b64encode(_png_bytes(make_icon(256))).decode("ascii")
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" '
        'viewBox="0 0 256 256">'
        f'<image width="256" height="256" href="data:image/png;base64,{b64}"/>'
        "</svg>\n",
        encoding="utf-8",
    )
    print(f"next PWA icons written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
