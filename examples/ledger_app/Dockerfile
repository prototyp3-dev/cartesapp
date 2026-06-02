# syntax=docker.io/docker/dockerfile:1

ARG CARTESAPP_ROOTFS_IMAGE=ghcr.io/prototyp3-dev/cartesapp-rootfs
ARG CARTESAPP_ROOTFS_VERSION=latest
FROM --platform=linux/riscv64 ${CARTESAPP_ROOTFS_IMAGE}:${CARTESAPP_ROOTFS_VERSION} AS state-builder

WORKDIR /opt/state

COPY ledger_app/settings.py .

COPY <<EOF /opt/state/build_state.py
from cartesapplib.ledger.utils import initialize_ledger
from settings import LEDGER_CONFIG

LEDGER_CONFIG["mem_file"] = "state.bin"
initialize_ledger(LEDGER_CONFIG)
EOF

ENV PYTHONPATH="${PYTHONPATH}:/opt/python_libs"

RUN /usr/local/bin/python3 build_state.py

FROM --platform=linux/riscv64 scratch AS state

COPY --from=state-builder /opt/state/state.bin /
