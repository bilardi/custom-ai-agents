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

.PHONY: major minor patch # update version, CHANGELOG.md and push with also tags
major:
	$(MAKE) release PART=major

minor:
	$(MAKE) release PART=minor

patch:
	$(MAKE) release PART=patch

release:
	uv run bump-my-version bump $(PART)
	$(MAKE) changelog
	@echo "To publish the release to remote, run:"
	@echo "  git push && git push --tags --force"

.PHONY: changelog # update CHANGELOG.md and amend it on the commit
changelog:
	uv run git-cliff --config pyproject.toml --output CHANGELOG.md
	sed -i 's/<!-- [0-9]* -->//g' CHANGELOG.md
	git add CHANGELOG.md uv.lock
	TAG=$$(git tag --points-at HEAD); \
	git commit --amend --no-edit; \
	[ -n "$$TAG" ] && git tag -f $$TAG $$(git rev-parse HEAD) || true
