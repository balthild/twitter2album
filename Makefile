.PHONY: help
help:
	@echo 'Usage: make [run|lint|fmt]'

.PHONY: run
run:
	uv run twitter2album-bot

.PHONY: lint
lint:
	uvx ruff check

.PHONY: fmt
fmt:
	uvx ruff format
