.PHONY: run
run:
	@poetry run kubeseal-auto --help --debug

.PHONY: build
build:
	@poetry build
