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

# Install the TypeScript app's dependencies so `npm run test`/`typecheck`/
# `build`/`e2e` work in cloud sessions (npm registry is reachable). Playwright
# is pinned to the version whose bundled Chromium build matches the one
# preinstalled in the image (/opt/pw-browsers/chromium-<build>), so `npm run
# e2e` resolves it automatically; PLAYWRIGHT_CHROMIUM_EXECUTABLE is only a
# fallback if the image ships a different build.
if [ -f web/package-lock.json ] && command -v npm >/dev/null 2>&1; then
  (cd web && npm ci) || echo "session-start: web npm ci failed (non-fatal)" >&2
fi

echo "session-start: environment ready ($($VENV/bin/python --version))" >&2
