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
# 3.14 (.python-version), so prefer it. In cloud sessions the
# python-build-standalone tarballs are fetched from github.com, which the
# egress policy may block (HTTP 403); fall back to the newest interpreter uv
# can find so tests can still run. The code uses no 3.14-only syntax, so the
# suite passes on 3.13.
if [ ! -x "$VENV/bin/python" ]; then
  if ! uv venv --python 3.14 "$VENV" 2>/dev/null; then
    echo "session-start: Python 3.14 unavailable, falling back to 3.13" >&2
    uv venv --python 3.13 "$VENV"
  fi
fi

# Install the test + lint dependencies (pytest, ruff, pygame-ce) from the
# locked file. These resolve from PyPI, which is reachable.
VIRTUAL_ENV="$VENV" uv pip install -r requirements-test.txt

echo "session-start: environment ready ($($VENV/bin/python --version))" >&2
