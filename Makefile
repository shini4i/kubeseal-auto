.PHONY: run
run:
	@poetry run kubeseal-auto

.PHONY: build
build:
	@poetry build

.PHONY: publish
publish: build
	@poetry publish
