# syntax=docker.io/docker/dockerfile:1
ARG IMAGE_NAME=riscv64/python
ARG IMAGE_TAG=3.12.12-alpine3.22
# ARG IMAGE_TAG=3.13.11-alpine3.22
ARG CARTESAPP_VERSION=latest
ARG MACHINE_GUEST_TOOLS_VERSION=0.17.1-r1
FROM ${IMAGE_NAME}:${IMAGE_TAG} AS base

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    gcompat=1.1.0-r4 sqlite=3.49.2-r1
EOF


# Install tools
ARG MACHINE_GUEST_TOOLS_VERSION
ADD --chmod=644 https://edubart.github.io/linux-packages/apk/keys/cartesi-apk-key.rsa.pub /etc/apk/keys/cartesi-apk-key.rsa.pub
RUN echo "https://edubart.github.io/linux-packages/apk/stable" >> /etc/apk/repositories
RUN apk update && apk add cartesi-machine-guest-tools=$MACHINE_GUEST_TOOLS_VERSION

FROM base AS cartesapp

ARG CARTESAPP_REPO=.
ADD ${CARTESAPP_REPO} /opt/cartesapp

FROM base AS builder-env

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    busybox-static=1.37.0-r20 git=2.49.1-r0 \
    libffi-dev=3.4.8-r0 build-base=0.5-r3 patchelf=0.18.0-r3 ccache=4.11.3-r1
EOF
# gcc=14.2.0-r4

# RUN pip install --upgrade pip wheel build
ARG NUITKA_VERSION=4.0.6
ARG ZSTANDARD_VERSION=0.25.0
RUN pip install nuitka[onefile]==${NUITKA_VERSION} zstandard==${ZSTANDARD_VERSION} --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/

ENV PYTHONPATH="/usr/local/lib/python3.12/:/usr/local/lib/python3.12/site-packages:${PYTHONPATH}"
ENV NUITKA_CACHE_DIR=/opt/nuitka-cache

FROM builder-env AS builder

COPY --from=cartesapp /opt/cartesapp /opt/cartesapp
RUN pip install /opt/cartesapp[machine] --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/

WORKDIR /opt/cartesapp

RUN python3 -m nuitka --python-flag=no_asserts --lto=yes \
    --module cartesapp --include-package=cartesapp \
    --follow-import-to=cartesi --include-package=cartesi --include-package=eth_abi_lite \
    --include-module=pycmt --include-module=Crypto --include-module=eth_typing_lite \
    --include-module=eth_utils_lite --include-module=parsimonious_lite --include-module=six_lite \
    --include-package=requests --include-package=urllib3 --include-package=idna \
    --include-package=packaging --include-package=pony --include-package=pydantic \
    --include-package=typing_extensions --include-package=certifi \
    --output-dir=/opt/cartesapp_module

# RUN python3 -m nuitka --python-flag=no_asserts --lto=yes  --output-dir=/opt/cartesapp-dist --onefile run_cartesapp  --follow-import-to=cartesapp

# RUN python3 -m nuitka --python-flag=no_asserts \
#     --lto=yes  --output-dir=/opt/cartesapp-dist --onefile --plugin-enable=pylint-warnings \
#     /opt/cartesapp/cartesapp/manager.py
# # --mode=standalone --follow-imports / --onefile / --include-plugin-directory=/usr/local/lib/python3.12/site-packages

FROM base AS debug

RUN <<EOF
set -e
apk update
apk add --no-interactive \
    busybox-static=1.37.0-r20 git=2.49.1-r0 \
    build-base=0.5-r3
EOF

COPY --from=cartesapp /opt/cartesapp /opt/cartesapp

RUN pip install /opt/cartesapp[machine,cartesapplib] --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/

FROM base AS dist

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

RUN pip install pycmt==0.0.1 pycryptodome==3.19.1 --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/

COPY --from=builder /opt/cartesapp_module/cartesapp.cpython-312-riscv64-linux-musl.so /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/run_cartesapp /usr/local/bin/run_cartesapp

# COPY --from=builder /opt/cartesapp-dist/manager.dist/ /usr/local/cartesapp-manager
# RUN ln -s /usr/local/cartesapp-manager/manager.bin /usr/local/bin/run_cartesapp

FROM --platform=linux/riscv64 ghcr.io/prototyp3-dev/cartesapp-rootfs:${CARTESAPP_VERSION}
