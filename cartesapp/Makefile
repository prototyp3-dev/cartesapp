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
	cartesapp build $(ARGS)

build-reader-node: ; $(value setup_venv)
	cartesapp build-reader-image $(ARGS)

build-dev-node: ; $(value setup_venv)
	cartesapp build-dev-image $(ARGS)

build-%: ${ENVFILE}.% --check-envs-% ; $(value setup_venv)
	. $< && cartesapp build $(ARGS)
	# You can add build args or env from the envfile
	#   add docker build-args with: --config build-args=ENV1=${ENV1},ENV2=${ENV2}
	#   add docker cm envs with: --config envs=ENV3=${ENV3},ENV4=${ENV4}

# Run targets
run: --load-env --check-roladdr-env ; $(value setup_venv)
	cartesapp node $(ARGS)

run-dev: --load-env --check-roladdr-env ; $(value setup_venv)
	ROLLUP_HTTP_SERVER_URL=${ROLLUP_HTTP_SERVER_URL} cartesapp node --mode dev $(ARGS)

run-reader: ; $(value setup_venv)
	cartesapp node --mode reader $(ARGS)

run-dev-%: ${ENVFILE}.% --check-testnet-envs-% --check-dev-envs-% rivemu ; $(value setup_venv)
	. $< && ROLLUP_HTTP_SERVER_URL=${ROLLUP_HTTP_SERVER_URL} \
	 cartesapp node --mode dev --rpc-url=${RPC_URL} --contracts-application-address=${APP_CONTRACT} --contracts-input-box-block=${DAPP_DEPLOY_BLOCK} $(ARGS)

run-reader-%: ${ENVFILE}.% --check-testnet-envs-% ; $(value setup_venv)
	. $< && cartesapp node --mode reader --rpc-url=${RPC_URL} --contracts-application-address=${APP_CONTRACT} --contracts-input-box-block=${DAPP_DEPLOY_BLOCK} $(ARGS)

# Test targets
test-verbose: ; $(value setup_venv)
	echo pytest --capture=no --log-cli-level=DEBUG --maxfail=1 --order-dependencies


# Aux env targets
--load-env: ${ENVFILE}
	$(eval include include $(PWD)/${ENVFILE})

${ENVFILE}:
	@test ! -f $@ && echo "$(ENVFILE) not found. Creating with default values"
	echo ROLLUP_HTTP_SERVER_URL=http://localhost:5004/rollup >> $(ENVFILE)

--load-env-%: ${ENVFILE}.%
	@$(eval include include $^)

${ENVFILE}.%:
	test ! -f $@ && $(error "file $@ doesn't exist")

--check-roladdr-env:
	@test ! -z '${ROLLUP_HTTP_SERVER_URL}' || echo "Must define ROLLUP_HTTP_SERVER_URL in env" && test ! -z '${ROLLUP_HTTP_SERVER_URL}'

--check-envs-%: --load-env-%
	@echo "check envs"
	# @test ! -z '${OPERATOR_ADDRESS}' || echo 'Must define OPERATOR_ADDRESS in env' && test ! -z '${OPERATOR_ADDRESS}'

--check-dev-envs-%: --load-env-%
	@test ! -z '${ROLLUP_HTTP_SERVER_URL}' || echo "Must define ROLLUP_HTTP_SERVER_URL in env" && test ! -z '${ROLLUP_HTTP_SERVER_URL}'

--check-testnet-envs-%: --load-env-%
	@test ! -z '${RPC_URL}' || echo "Must define RPC_URL in env" && test ! -z '${RPC_URL}'
	@test ! -z '${APP_CONTRACT}' || echo "Must define APP_CONTRACT in env" && test ! -z '${APP_CONTRACT}'
	@test ! -z '${DAPP_DEPLOY_BLOCK}' || echo "Must define DAPP_DEPLOY_BLOCK in env" && test ! -z '${DAPP_DEPLOY_BLOCK}'
