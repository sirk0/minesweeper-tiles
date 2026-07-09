import asyncio
import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from minesweeper.gui import App  # noqa: E402


def test_app_loop_runs_and_exits_on_quit():
    """The async main loop (shared by desktop and the pygbag browser
    build) must process events and return on QUIT."""
    pygame.init()
    pygame.display.set_mode((1, 1))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    asyncio.run(asyncio.wait_for(App().run_async(), timeout=10))
