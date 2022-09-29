.DEFAULT_GOAL := help

.PHONY: help
help: ## Print this help
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: run
run: ## Run the application with enabled debug mode
	@poetry run kubeseal-auto --debug

.PHONY: build
build: ## Package the application using poetry
	@poetry build

.PHONY: bump-patch
bump-patch: ## Bump the patch version
	@bump2version patch --allow-dirty

.PHONY: bump-minor
bump-minor: ## Bump the minor version
	@bump2version minor --allow-dirty
