# syntax=docker.io/docker/dockerfile:1.4
FROM riscv64/python:3.12.10-alpine3.21 AS base

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    gcompat=1.1.0-r4 sqlite=3.48.0-r2
EOF

FROM base AS builder

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    busybox-static=1.37.0-r12 git=2.47.2-r0 \
    libffi-dev=3.4.7-r0  build-base=0.5-r3 patchelf=0.18.0-r3
EOF
# gcc=14.2.0-r4

# RUN pip install --upgrade pip wheel build

RUN pip install nuitka --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/

ARG CARTESAPP_REPO=.
ADD ${CARTESAPP_REPO} /opt/cartesapp

RUN pip install /opt/cartesapp --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/
ENV NUITKA_CACHE_DIR=/opt/nuitka-cache
RUN python3.12 -m nuitka --python-flag=no_asserts --python-flag=dont_write_bytecode \
    --lto=yes  --output-dir=/opt/cartesapp-dist --onefile \
    /opt/cartesapp/cartesapp/manager.py
# --mode=standalone --follow-imports / --onefile

FROM base AS dist

ARG MACHINE_GUEST_TOOLS_VERSION=0.17.1-r1

# Install guest tools

ADD --chmod=644 https://edubart.github.io/linux-packages/apk/keys/cartesi-apk-key.rsa.pub /etc/apk/keys/cartesi-apk-key.rsa.pub
RUN echo "https://edubart.github.io/linux-packages/apk/stable" >> /etc/apk/repositories

RUN apk update && apk add cartesi-machine-guest-tools=$MACHINE_GUEST_TOOLS_VERSION

# TODO: Remove getting installing python modules
RUN apk add --no-interactive git=2.47.2-r0
ARG CARTESAPP_REPO=.
ADD ${CARTESAPP_REPO} /opt/cartesapp
RUN pip install /opt/cartesapp --no-cache --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/
RUN rm -rf /opt/cartesapp
RUN apk del --purge git

# # Remove unneeded packages to shrink image
# # pip uninstall -y pip wheel build
# RUN <<EOF
# set -e
# apk del --purge apk-tools alpine-release alpine-keys ca-certificates-bundle libc-utils
# find /usr/local/lib -type d -name __pycache__ -exec rm -r {} +
# rm -rf /var/cache/apk /etc/apk /lib/apk /var/log/* /var/cache/* /tmp/*
# EOF

# TODO: Revert getting binary
# COPY --from=builder /opt/cartesapp-dist/manager.dist/ /usr/local/cartesapp-manager
# RUN ln -s /usr/local/cartesapp-manager/manager.bin /usr/local/bin/run_cartesapp
