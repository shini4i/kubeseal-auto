.DEFAULT_GOAL := help

.PHONY: help
help: ## Print this help
	@echo "Usage: make [target]"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: run
run: ## Run the application with enabled debug mode
	@poetry run kubeseal-auto --debug

.PHONY: test
test: ## Run the tests
	@poetry run pytest

.PHONY: test-coverage
test-coverage: ## Run the tests with coverage
	@poetry run pytest --cov=src --cov-report=term-missing --junitxml=junit.xml -o junit_family=legacy

.PHONY: build
build: ## Package the application using poetry
	@poetry build

.PHONY: bump-patch
bump-patch: ## Bump the patch version
	@bump2version patch --allow-dirty

.PHONY: bump-minor
bump-minor: ## Bump the minor version
	@bump2version minor --allow-dirty
