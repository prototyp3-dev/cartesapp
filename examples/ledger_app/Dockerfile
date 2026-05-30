# syntax=docker.io/docker/dockerfile:1

ARG CARTESAPP_VERSION=latest
FROM --platform=linux/riscv64 ghcr.io/prototyp3-dev/cartesapp-rootfs:${CARTESAPP_VERSION} AS state-builder

WORKDIR /opt/state

COPY app/settings.py .

COPY <<EOF /opt/state/build_state.py
from cartesapplib.ledger import app_ledger
from settings import LEDGER_CONFIG

LEDGER_CONFIG["mem_file"] = "state.bin"

app_ledger.initialize_ledger(LEDGER_CONFIG)
EOF


FROM --platform=linux/riscv64 scratch AS state

COPY --from=state-builder /opt/cartesi/app/data/state.bin /
