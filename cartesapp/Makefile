# Makefile

ENVFILE := .env

SHELL := /bin/bash

define setup_venv =
@if [ ! -d .venv ]; then python3 -m venv .venv; fi
@if [[ "VIRTUAL_ENV" != "" ]]; then . .venv/bin/activate; fi
@if [ -z "$(pip freeze)" ]; then
	if [ -f requirements.txt ]; then 
		pip install -r requirements.txt;
	else
		pip install git+https://github.com/prototyp3-dev/cartesapp@main --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/
		echo --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/ >> requirements.txt
		pip freeze >> requirements.txt
		pip install git+https://github.com/prototyp3-dev/cartesapp@main#egg=cartesapp[dev] --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/
	fi
fi
endef

.ONESHELL:

all: build build-reader-node

setup-env: ; $(value setup_venv)

# build targets
build: ; $(value setup_venv)
	cartesapp build

build-reader-node: ; $(value setup_venv)
	cartesapp build-reader-image

build-dev-node: ; $(value setup_venv)
	cartesapp build-dev-image

build-%: --load-env-% ; $(value setup_venv)
	cartesapp build

# Run targets
run: --load-env --check-roladdr-env ; $(value setup_venv)
	cartesapp node

run-dev: --load-env --check-roladdr-env ; $(value setup_venv)
	ROLLUP_HTTP_SERVER_URL=${ROLLUP_HTTP_SERVER_URL} cartesapp node --mode dev

run-reader: ; $(value setup_venv)
	cartesapp node --mode reader

# Test targets
test-verbose: ; $(value setup_venv)
	echo pytest --capture=no --log-cli-level=DEBUG --maxfail=1 --order-dependencies


# Aux env targets
--load-env: ${ENVFILE}
	$(eval include include $(PWD)/${ENVFILE})

${ENVFILE}:
	@test ! -f $@ && echo "$(ENVFILE) not found. Creating with default values" 
	echo ROLLUP_HTTP_SERVER_URL=http://localhost:8080/rollup >> $(ENVFILE)

--load-env-%: ${ENVFILE}.%
	@$(eval include include $^)

${ENVFILE}.%:
	test ! -f $@ && $(error "file $@ doesn't exist")

--check-roladdr-env:
	@test ! -z '${ROLLUP_HTTP_SERVER_URL}' || echo "Must define ROLLUP_HTTP_SERVER_URL in env" && test ! -z '${ROLLUP_HTTP_SERVER_URL}'

