# Custom AI Agents makefile

.PHONY: help # print this help list
help:
	grep PHONY Makefile | sed 's/.PHONY: /make /' | grep -v grep

.PHONY: clean # remove cache files
clean:
	rm -rf */__pycache__ */*/__pycache__; rm -rf .pytest_cache .ruff_cache

.PHONY: sync # install/refresh dev dependencies via uv sync
sync:
	uv sync

.PHONY: test # run unit tests
test:
	uv run pytest

.PHONY: lint # run ruff check
lint:
	uv run ruff check --no-fix .

.PHONY: format # run ruff format
format:
	uv run ruff format .

.PHONY: typecheck # run pyright
typecheck:
	uv run pyright
