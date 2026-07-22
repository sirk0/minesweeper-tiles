"""Load the shared JSON config both front-ends read (``data/*.json``).

The pygame and TypeScript apps read the same geometry configuration so it is
never written twice. These files are the single source of truth; ``catalog.py``
and ``presets.py`` load them here. See ``scripts/export_data.py`` and
``docs/plans/typescript-rewrite-same-repo.md``.

The data directory sits at the repo root next to ``minesweeper/``. That holds in
both the dev checkout and the pygbag web stage (``make web-prepare`` copies
``data/`` alongside the package), so ``parents[2]`` resolves it in each.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Parse ``data/<name>.json`` (cached)."""
    return json.loads((_DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
