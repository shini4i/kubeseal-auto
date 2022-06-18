.PHONY: run
run:
	@poetry run kubeseal-auto --debug

.PHONY: build
build:
	@poetry build

.PHONY: publish
publish: build
	@poetry publish
