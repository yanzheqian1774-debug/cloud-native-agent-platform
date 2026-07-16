.PHONY: help tree status lint test

help:
	@echo "Available commands:"
	@echo "  make tree    Show project structure"
	@echo "  make status  Show git status"
	@echo "  make lint    Run lint checks"
	@echo "  make test    Run tests"

tree:
	tree -L 3

status:
	git status

lint:
	@echo "Lint tools will be configured in a later sprint."

test:
	@echo "Tests will be configured in a later sprint."
