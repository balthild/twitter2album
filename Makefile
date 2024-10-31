.PHONY: run
run:
	hatch run production:twitter2album-bot

.PHONY: dev
dev:
	hatch run watchexec --restart --watch src --exts py twitter2album-bot
