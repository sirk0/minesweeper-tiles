"""Browser entry point, packaged by pygbag (https://pygame-web.github.io).

On the desktop use ``python -m minesweeper`` instead.
"""

import asyncio

# pygbag decides which wasm packages to provision by scanning main.py's
# top-level imports, so pygame must be imported here even though the game
# code lives in the minesweeper package
import pygame  # noqa: F401

from minesweeper.gui import App


async def main() -> None:
    await App().run_async()


asyncio.run(main())
