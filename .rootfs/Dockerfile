# syntax=docker.io/docker/dockerfile:1.4
ARG IMAGE_NAME=riscv64/python
ARG IMAGE_TAG=3.12.10-alpine3.21
ARG CARTESAPP_VERSION=latest
FROM ${IMAGE_NAME}:${IMAGE_TAG} AS base

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    gcompat=1.1.0-r4 sqlite=3.48.0-r4
EOF

FROM base AS builder

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    busybox-static=1.37.0-r14 git=2.47.3-r0 \
    libffi-dev=3.4.7-r0  build-base=0.5-r3 patchelf=0.18.0-r3
EOF
# gcc=14.2.0-r4

# RUN pip install --upgrade pip wheel build

RUN pip install nuitka --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/

ARG CARTESAPP_REPO=.
ADD ${CARTESAPP_REPO} /opt/cartesapp
RUN <<EOF
echo 'import sys
sys.path.append("/usr/local/lib/python3.12/site-packages/")
' >> /opt/cartesapp/cartesapp/__init__.py
EOF

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

ARG CARTESAPPLIB_VERSION=0.1.0
RUN mkdir -p /opt/python_libs
RUN wget -qO- https://github.com/prototyp3-dev/cartesapplib/archive/refs/tags/v${CARTESAPPLIB_VERSION}.tar.gz | \
    tar zxf - --strip-components 1 -C /opt/python_libs cartesapplib-${CARTESAPPLIB_VERSION}/cartesapplib

RUN chown -R dapp:dapp /opt/python_libs

# Remove unneeded packages to shrink image
# pip uninstall -y pip wheel build
# apk del --purge apk-tools alpine-release alpine-keys ca-certificates-bundle wget vi libc-utils
RUN <<EOF
set -e
find /usr/local/lib -type d -name __pycache__ -exec rm -r {} +
rm -rf /var/cache/apk /var/log/* /var/cache/* /tmp/*
EOF

COPY --from=builder /opt/cartesapp-dist/manager.dist/ /usr/local/cartesapp-manager
RUN ln -s /usr/local/cartesapp-manager/manager.bin /usr/local/bin/run_cartesapp

FROM --platform=linux/riscv64 ghcr.io/prototyp3-dev/cartesapp-rootfs:${CARTESAPP_VERSION}
