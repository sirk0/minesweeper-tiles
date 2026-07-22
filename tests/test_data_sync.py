"""Guard the shared JSON config (data/*.json) against drift.

catalog.py / presets.py load these files, and the TypeScript app reads the same
ones, so they are the single source of truth. These tests assert the committed
JSON is canonical (re-running the exporter is a no-op) and that the Python side
reconstructs it faithfully.
"""

import json
from pathlib import Path

import scripts.export_data as export_data
from minesweeper.boards._data import load
from minesweeper.boards.core import DIFFICULTIES

DATA = Path(__file__).resolve().parent.parent / "data"


def _committed(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def test_catalog_json_is_canonical():
    # Re-emitting from the loaded catalog API must reproduce the committed file
    # byte-for-byte structure (run scripts/export_data.py to refresh).
    assert export_data.build_catalog() == _committed("catalog")


def test_presets_json_round_trips():
    assert export_data.build_presets() == _committed("presets")


def test_difficulties_match_catalog():
    assert list(DIFFICULTIES) == load("catalog")["difficulties"]


def test_regular_tilings_declared_nonchiral():
    # The three regular tilings are reflective (non-chiral); the declaration in
    # data/catalog.json must say so.
    for row in load("catalog")["regularTilings"]:
        assert row["chiral"] is False
