.PHONY: install venv lint format test clean

VENV=.venv
PYTHON=$(VENV)/bin/python

install: venv
	uv pip install -e ".[dev]"
	pre-commit install

venv:
	test -d $(VENV) || uv venv

lint:
	ruff check .
	sqlfluff lint .

format:
	ruff format .
	sqlfluff fix .

test:
	pytest

clean:
	rm -rf .venv
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache
