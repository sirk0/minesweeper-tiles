VENV ?= .venv
PY ?= $(VENV)/bin/python

WEB_STAGE = build/minesweeper
WEB_OUT = $(WEB_STAGE)/build/web

.PHONY: help venv install lock test lint run \
        web-prepare web-package web-run clean

help:            ## list available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/' | sort

venv:            ## create .venv and install every dependency group
	python3 -m venv $(VENV)
	$(PY) -m pip install -r requirements-all.txt

install:         ## install every dependency group into $(PY)
	$(PY) -m pip install -r requirements-all.txt

lock:            ## regenerate the lock files from pyproject.toml
	uv pip compile pyproject.toml -o requirements.txt --universal
	uv pip compile pyproject.toml --extra web -o requirements-web.txt --universal
	uv pip compile pyproject.toml --extra test -o requirements-test.txt --universal
	uv pip compile pyproject.toml --all-extras -o requirements-all.txt --universal

test:            ## run the test suite
	$(PY) -m pytest -q

lint:            ## ruff over the code and tests
	$(PY) -m ruff check minesweeper tests main.py

run:             ## run the desktop game
	$(PY) -m minesweeper

web-prepare:     ## stage the browser app files into $(WEB_STAGE)
	rm -rf $(WEB_STAGE)
	mkdir -p $(WEB_STAGE)
	cp main.py $(WEB_STAGE)/
	cp -r minesweeper $(WEB_STAGE)/minesweeper

web-package: web-prepare  ## build the browser bundle into $(WEB_OUT)
	$(PY) -m pygbag --ume_block 0 --build $(WEB_STAGE)
	PYTHONPATH=. $(PY) scripts/make_favicon.py $(WEB_OUT)/favicon.png

web-run: web-prepare  ## serve the web version at http://localhost:8000
	@# pygbag regenerates its default favicon at server start; swap in
	@# ours once the server is up
	( sleep 5 && PYTHONPATH=. $(PY) scripts/make_favicon.py $(WEB_OUT)/favicon.png ) &
	$(PY) -m pygbag --ume_block 0 $(WEB_STAGE)

clean:           ## remove build artifacts
	rm -rf build
