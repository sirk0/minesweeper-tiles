#!/bin/bash
# SessionStart hook: provision a virtualenv with the test/lint dependencies
# so `make test` and `make lint` work in Claude Code on the web sessions.
set -euo pipefail

# Only run in remote (Claude Code on the web) sessions; local dev keeps
# using `make venv`.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

VENV=.venv

# Create the virtualenv if it isn't there yet. The project targets Python
# 3.13 (.python-version), which cloud images already ship, so no interpreter
# download is needed.
if [ ! -x "$VENV/bin/python" ]; then
  uv venv --python 3.13 "$VENV"
fi

# Install the test + lint dependencies (pytest, ruff, pygame-ce) from the
# locked file. These resolve from PyPI, which is reachable.
VIRTUAL_ENV="$VENV" uv pip install -r requirements-test.txt

echo "session-start: environment ready ($($VENV/bin/python --version))" >&2
