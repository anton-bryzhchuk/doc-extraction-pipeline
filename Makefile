.PHONY: install test lint run evaluate demo generate clean

VENV ?= .venv
PY := $(VENV)/bin/python

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(VENV)/bin/ruff check .

run:
	$(PY) -m docpipe serve

generate:
	$(PY) -m docpipe generate

evaluate:
	$(PY) -m docpipe evaluate --profile good

demo:
	$(PY) -m docpipe demo-failures

clean:
	rm -rf reports/*.json reports/*.md .pytest_cache .ruff_cache *.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
