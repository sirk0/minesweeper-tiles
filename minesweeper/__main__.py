"""Entry point: GUI when pygame is available, terminal otherwise.

``python -m minesweeper [difficulty]``        GUI (falls back to terminal)
``python -m minesweeper --cli [difficulty]``  force terminal mode
"""

import sys

argv = sys.argv[1:]
if "--cli" in argv:
    argv.remove("--cli")
    from minesweeper.cli import main
else:
    try:
        from minesweeper.gui import main
    except ImportError:
        print("pygame not installed; using terminal mode", file=sys.stderr)
        from minesweeper.cli import main

sys.exit(main(argv))
