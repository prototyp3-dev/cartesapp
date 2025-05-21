# syntax=docker.io/docker/dockerfile:1.4
FROM cartesi/python:3.12.9-slim-noble

ARG MACHINE_GUEST_TOOLS_VERSION=0.17.0-1

ARG DEBIAN_FRONTEND=noninteractive
RUN <<EOF
set -e
apt-get update
apt-get install -y --no-install-recommends \
    busybox-static=1:1.36.1-6ubuntu3.1 \
    git=1:2.43.0-1ubuntu7.2 ca-certificates=20240203 \
    sqlite3=3.45.1-1ubuntu2.1
rm -rf /var/lib/apt/lists/* /var/log/* /var/cache/*
useradd --create-home --user-group dapp
EOF

ADD --chmod=644 https://edubart.github.io/linux-packages/apt/keys/cartesi-deb-key.gpg.bin /etc/apt/trusted.gpg.d/cartesi-deb-key.gpg
ADD --chmod=644 https://edubart.github.io/linux-packages/apt/stable/sources.list /etc/apt/sources.list.d/cartesi-deb-apt.list

RUN <<EOF
set -e
apt-get update
apt-get install -y --no-install-recommends \
    cartesi-machine-guest-tools=${MACHINE_GUEST_TOOLS_VERSION}
EOF

ENV PATH="/opt/cartesi/bin:${PATH}"

RUN pip install --upgrade pip

ARG CARTESAPP_REPO=.
ADD ${CARTESAPP_REPO} /opt/cartesapp
RUN pip install /opt/cartesapp --no-cache --find-links https://prototyp3-dev.github.io/pip-wheels-riscv/wheels/
RUN rm -rf /opt/cartesapp

RUN <<EOF
set -e
apt remove -y build-essential git ca-certificates && apt -y autoremove
find /usr/local/lib -type d -name __pycache__ -exec rm -r {} +
rm -rf /var/lib/apt/lists/* /var/log/* /var/cache/* /opt/cartesi/install
EOF

# build with these commands
# docker build --platform=linux/riscv64 -f .build-cm/rootfs.Dockerfile --build-arg CARTESAPP_REPO=. --build-arg MACHINE_GUEST_TOOLS_VERSION=0.17.0-1 --output type=tar,dest=.cartesi/root.tar .
# bsdtar -cf .cartesi/root-retar.tar -C .cartesi --format=gnutar root.tar
# xgenext2fs -fzB 4096 -i 4096 -r +4096 -a .cartesi/root.tar -L rootfs .cartesi/root.ext2 # +16MB
# xgenext2fs -fzB 4096 -i 4096 -r +4096 .cartesi/data.ext2 # +16MB from dir: -d data
# resize2fs -f .cartesi/rootfs.ext2 512M # optional

# then customize image
# cartesi-machine --network --volume=.:/mnt --workdir=/mnt --flash-drive=label:root,filename:.cartesi/root.ext2,shared --flash-drive=label:data,filename:.cartesi/data.ext2,shared -u=root -it -- bash

# finally generate the snapshot (shouldn't be necessary)
# cartesi-machine --env=ROLLUP_HTTP_SERVER_URL=http://127.0.0.1:5004 --flash-drive=label:root,filename:.cartesi/root.ext2 --flash-drive=label:data,filename:.cartesi/data.ext2 --store=.cartesi/image --assert-rolling-template -- rollup-init /init
