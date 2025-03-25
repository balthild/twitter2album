.PHONY: run
run:
	uv run twitter2album-bot

.PHONY: dev
dev:
	uv run watchexec --restart --watch src --exts py twitter2album-bot
