# syntax=docker.io/docker/dockerfile:1.4

ARG EMULATOR_VERSION=0.19.0
ARG EMULATOR_VERSION_SUFFIX=-alpha3
ARG KERNEL_VERSION=6.5.13-ctsi-1
ARG MACHINE_LINUX_VERSION=0.20.0
ARG S6_OVERLAY_VERSION=3.2.0.2
ARG TELEGRAF_VERSION=1.32.1
ARG TRAEFIK_VERSION=3.2.0
ARG GOVERSION=1.23.5
ARG GO_BUILD_PATH=/build/cartesi/go
ARG ROLLUPSNODE_VERSION=2.0.0-alpha.4
ARG ROLLUPSNODE_BRANCH=next/2.0
ARG ROLLUPSNODE_DIR=rollups-node
ARG ESPRESSOREADER_VERSION=0.2.3-node-20250128
ARG ESPRESSOREADER_BRANCH=main
ARG ESPRESSOREADER_DIR=rollups-espresso-reader
ARG ESPRESSO_DEV_NODE_TAG=20241120-patch6
ARG FOUNDRY_DIR=/foundry
ARG TARGETARCH=amd64
ARG XGENEXT2_VERSION=1.5.6

# =============================================================================
# STAGE: node builder
#
# =============================================================================

FROM cartesi/machine-emulator:${EMULATOR_VERSION}${EMULATOR_VERSION_SUFFIX} AS common-env

USER root

RUN <<EOF
apt update
apt install -y --no-install-recommends \
    build-essential \
    wget ca-certificates \
    git
EOF

USER cartesi

# =============================================================================
# STAGE: foundry-installer
#
# =============================================================================

FROM common-env AS foundry-installer

USER root

RUN <<EOF
apt update
apt install -y --no-install-recommends \
    curl
EOF

# install foundry
ARG FOUNDRY_DIR
ENV FOUNDRY_DIR=${FOUNDRY_DIR}
RUN mkdir -p ${FOUNDRY_DIR}
RUN curl -L https://foundry.paradigm.xyz | bash
RUN ${FOUNDRY_DIR}/bin/foundryup -i stable

# =============================================================================
# STAGE: go-installer and projects builder
#
# =============================================================================

FROM common-env AS go-installer

USER root

ARG GOVERSION
ARG TARGETARCH

RUN wget https://go.dev/dl/go${GOVERSION}.linux-${TARGETARCH}.tar.gz && \
    tar -C /usr/local -xzf go${GOVERSION}.linux-${TARGETARCH}.tar.gz

ENV PATH=/usr/local/go/bin:${PATH}

ARG GO_BUILD_PATH
RUN mkdir -p ${GO_BUILD_PATH} && chown -R cartesi:cartesi ${GO_BUILD_PATH}

USER cartesi

FROM go-installer AS go-builder

ARG GO_BUILD_PATH

WORKDIR ${GO_BUILD_PATH}

ENV GOCACHE=${GO_BUILD_PATH}/.cache
ENV GOENV=${GO_BUILD_PATH}/.config/go/env
ENV GOPATH=${GO_BUILD_PATH}/.go

# ARG ROLLUPSNODE_VERSION
# ARG ROLLUPSNODE_BRANCH
# ARG ROLLUPSNODE_DIR

# RUN mkdir ${GO_BUILD_PATH}/${ROLLUPSNODE_DIR}
# RUN wget -qO- https://github.com/cartesi/rollups-node/archive/refs/tags/v${ROLLUPSNODE_VERSION}.tar.gz | \
#     tar -C ${GO_BUILD_PATH}/${ROLLUPSNODE_DIR} -zxf - --strip-components 1 rollups-node-${ROLLUPSNODE_VERSION}

# RUN git clone --single-branch --branch ${ROLLUPSNODE_BRANCH} \
#     https://github.com/cartesi/rollups-node.git ${GO_BUILD_PATH}/${ROLLUPSNODE_DIR}

# RUN cd ${GO_BUILD_PATH}/${ROLLUPSNODE_DIR} && go mod download
# RUN cd ${GO_BUILD_PATH}/${ROLLUPSNODE_DIR} && make build-go

# ARG ESPRESSOREADER_VERSION
ARG ESPRESSOREADER_DIR
ARG ESPRESSOREADER_BRANCH

# RUN mkdir ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR}
# RUN wget -qO- https://github.com/cartesi/rollups-espresso-reader/archive/refs/tags/v${ESPRESSOREADER_VERSION}.tar.gz | \
#     tar -C ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR} -zxf - --strip-components 1 rollups-espresso-reader-${ESPRESSOREADER_VERSION}

# RUN wget -q https://github.com/cartesi/rollups-espresso-reader/releases/download/v${ESPRESSOREADER_VERSION}/cartesi-rollups-espresso-reader \
#     -O ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR}/cartesi-rollups-espresso-reader

RUN git clone --single-branch --branch ${ESPRESSOREADER_BRANCH} \
    https://github.com/cartesi/rollups-espresso-reader.git ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR}

RUN cd ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR} && go mod download
RUN cd ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR} && \
    go build -o cartesi-rollups-espresso-reader && \
    go build -o cartesi-rollups-espresso-reader-db-migration dev/migrate/main.go

# =============================================================================
# STAGE: base-cartesapp-sdk
#
# =============================================================================

# https://github.com/EspressoSystems/espresso-sequencer/pkgs/container/espresso-sequencer%2Fespresso-dev-node
FROM ghcr.io/espressosystems/espresso-sequencer/espresso-dev-node:${ESPRESSO_DEV_NODE_TAG} AS espresso-dev-node

# FROM debian:12-slim AS base-cartesapp-sdk
FROM postgres:16-bookworm AS base-cartesapp-sdk
# FROM cartesi/machine-emulator:${EMULATOR_VERSION} AS base-cartesapp-sdk
ARG TARGETARCH
ARG BASE_PATH=/mnt
ENV BASE_PATH=${BASE_PATH}

ENV SNAPSHOTS_APPS_PATH=${BASE_PATH}/apps
ENV NODE_PATH=${BASE_PATH}/node
ENV ESPRESSO_PATH=${BASE_PATH}/espresso

RUN useradd --user-group cartesi

# Download system dependencies required at runtime.
ARG DEBIAN_FRONTEND=noninteractive
RUN <<EOF
    set -e
    apt-get update
    apt-get install -y --no-install-recommends \
        ca-certificates curl procps \
        xz-utils nginx postgresql-client \
        lua5.4 libslirp0 libglib2.0-0 libarchive13 \
        squashfs-tools
    rm -rf /var/lib/apt/lists/* /var/log/* /var/cache/*
    mkdir -p ${NODE_PATH}/snapshots ${NODE_PATH}/data ${ESPRESSO_PATH}
    chown -R cartesi:cartesi ${NODE_PATH}
EOF

# install s6 overlay
ARG S6_OVERLAY_VERSION
RUN curl -s -L https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz | \
    tar xJf - -C /
RUN curl -s -L https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-$(uname -m).tar.xz | \
    tar xJf - -C /

# install telegraf
ARG TELEGRAF_VERSION
RUN curl -s -L https://dl.influxdata.com/telegraf/releases/telegraf-${TELEGRAF_VERSION}_linux_${TARGETARCH}.tar.gz | \
    tar xzf - --strip-components 2 -C / ./telegraf-${TELEGRAF_VERSION}

# new cm version
# curl -s -L -o /tmp/cartesi-machine.deb https://github.com/cartesi/machine-emulator/releases/download/v${EMULATOR_VERSION}${EMULATOR_VERSION_SUFFIX}/machine-emulator_${TARGETARCH}.deb
ARG EMULATOR_VERSION
ARG EMULATOR_VERSION_SUFFIX
RUN <<EOF
set -e
curl -s -L -o /tmp/cartesi-machine.deb https://github.com/cartesi/machine-emulator/releases/download/v${EMULATOR_VERSION}${EMULATOR_VERSION_SUFFIX}/cartesi-machine-v${EMULATOR_VERSION}_${TARGETARCH}.deb
dpkg -i /tmp/cartesi-machine.deb
rm /tmp/cartesi-machine.deb
EOF

ARG KERNEL_VERSION
ARG MACHINE_LINUX_VERSION
RUN <<EOF
set -e
curl -s -L -o /usr/share/cartesi-machine/images/linux.bin https://github.com/cartesi/machine-linux-image/releases/download/v${KERNEL_VERSION}/linux-${MACHINE_LINUX_VERSION}-v${KERNEL_VERSION}.bin
EOF

# Install dpkg release of xgenext2fs
ARG XGENEXT2_VERSION
RUN <<EOF
curl -fsSL https://github.com/cartesi/genext2fs/releases/download/v${XGENEXT2_VERSION}/xgenext2fs_${TARGETARCH}.deb \
    -o /tmp/xgenext2fs.deb
dpkg -i /tmp/xgenext2fs.deb
rm /tmp/xgenext2fs.deb
xgenext2fs --version
EOF

ARG ROOTFS=./root.ext2
COPY ${ROOTFS} /usr/share/cartesi-machine/images/rootfs.ext2

ARG ROLLUPSNODE_VERSION
RUN <<EOF
set -e
curl -s -L -o /tmp/cartesi-rollups-node.deb https://github.com/cartesi/rollups-node/releases/download/v${ROLLUPSNODE_VERSION}/cartesi-rollups-node-v${ROLLUPSNODE_VERSION}_${TARGETARCH}.deb
dpkg -i /tmp/cartesi-rollups-node.deb
rm /tmp/cartesi-rollups-node.deb
EOF

# # Copy Go binary.
ARG GO_BUILD_PATH
ARG ROLLUPSNODE_DIR
ARG ESPRESSOREADER_DIR
# COPY --from=go-builder ${GO_BUILD_PATH}/${ROLLUPSNODE_DIR}/cartesi-rollups-* /usr/bin
COPY --from=go-builder ${GO_BUILD_PATH}/${ESPRESSOREADER_DIR}/cartesi-rollups-* /usr/bin

# Install espresso
COPY --from=espresso-dev-node /usr/bin/espresso-dev-node /usr/local/bin/

# install foundry
ARG FOUNDRY_DIR
COPY --from=foundry-installer ${FOUNDRY_DIR}/bin/* /usr/local/bin/

RUN mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d

################################################################################
# configure telegraf
RUN mkdir -p /etc/telegraf
COPY <<EOF /etc/telegraf/telegraf.conf
[agent]
    interval = '60s'
    round_interval = true
    metric_batch_size = 1000
    metric_buffer_limit = 10000
    collection_jitter = '0s'
    flush_interval = '60s'
    flush_jitter = '0s'
    precision = '1ms'
    omit_hostname = true

[[inputs.processes]]

[[inputs.procstat]]

[[outputs.health]]
    service_address = 'http://:9274'

[[inputs.procstat.filter]]
    name = 'rollups-node'
    process_names = ['cartesi-rollups-*', 'jsonrpc-remote-cartesi-*', '*cartesi*', 'telegraf', 'nginx']

[[inputs.prometheus]]
    urls = ["http://localhost:10001","http://localhost:10002","http://localhost:10003","http://localhost:10004"]

[[outputs.prometheus_client]]
    listen = ':9000'
    collectors_exclude = ['process']
EOF

# Configure s6 Telegraf
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/telegraf/data
echo "longrun" > /etc/s6-overlay/s6-rc.d/telegraf/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/telegraf/data/check
#!/command/execlineb -P
wget -qO /dev/null 127.0.0.1:9274/
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/telegraf/run
#!/command/execlineb -P
pipeline -w { sed --unbuffered "s/^/telegraf: /" }
fdmove -c 2 1
/usr/bin/telegraf
EOF

################################################################################
# Configure nginx
RUN <<EOF
mkdir -p /var/log/nginx/
chown -R cartesi:cartesi /var/log/nginx/
mkdir -p /var/cache
chown -R cartesi:cartesi /var/cache
chown -R cartesi:cartesi /var/lib/nginx
EOF

COPY <<EOF /etc/nginx/nginx.conf
user cartesi;
worker_processes  auto;

error_log  /var/log/nginx/error.log notice;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '\$remote_addr - \$upstream_cache_status rt=\$request_time [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for" '
                      'uct="\$upstream_connect_time" uht="\$upstream_header_time" urt="\$upstream_response_time"';

    access_log  /var/log/nginx/access.log  main;

    sendfile        on;
    #tcp_nopush     on;

    keepalive_timeout  65;

    #gzip  on;

    map \$request_method \$purge_method {
        PURGE 1;
        default 0;
    }

    proxy_cache_path /var/cache keys_zone=mycache:200m;

    include /etc/nginx/sites-enabled/*;
}
EOF

RUN rm /etc/nginx/sites-enabled/*

# Configure s6 nginx
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/nginx
touch /etc/s6-overlay/s6-rc.d/user/contents.d/nginx
echo "longrun" > /etc/s6-overlay/s6-rc.d/nginx/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/nginx/run
#!/command/execlineb -P
pipeline -w { sed --unbuffered "s/^/nginx: /" }
fdmove -c 2 1
/usr/sbin/nginx -g "daemon off;"
EOF

# Env variables
ARG CARTESI_INSPECT_PORT=10012
ENV CARTESI_INSPECT_PORT=${CARTESI_INSPECT_PORT}
ENV CARTESI_INSPECT_ADDRESS=localhost:${CARTESI_INSPECT_PORT}
ARG CARTESI_JSONRPC_API_PORT=10011
ENV CARTESI_JSONRPC_API_PORT=${CARTESI_JSONRPC_API_PORT}
ENV CARTESI_JSONRPC_API_ADDRESS=localhost:${CARTESI_JSONRPC_API_PORT}
ARG ESPRESSO_SERVICE_PORT=10030
ENV ESPRESSO_SERVICE_PORT=${ESPRESSO_SERVICE_PORT}
ARG ESPRESSO_SERVICE_ENDPOINT=localhost:${ESPRESSO_SERVICE_PORT}
ENV ESPRESSO_SERVICE_ENDPOINT=${ESPRESSO_SERVICE_ENDPOINT}
ENV CARTESI_SNAPSHOT_DIR=${NODE_PATH}/snapshots

ENV NODE_DB=rollupsdb
ENV ESPRESSONODE_DB=sequencer

ENV CARTESI_LOG_LEVEL=info
ENV CARTESI_BLOCKCHAIN_HTTP_ENDPOINT=http://localhost:8545
ENV CARTESI_BLOCKCHAIN_WS_ENDPOINT=ws://localhost:8545
ENV CARTESI_BLOCKCHAIN_ID=31337
ENV CARTESI_AUTH_KIND=private_key
ENV CARTESI_AUTH_PRIVATE_KEY=ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
ENV CARTESI_BLOCKCHAIN_DEFAULT_BLOCK=latest

ENV CARTESI_FEATURE_RPC_ENABLED=true
ENV CARTESI_FEATURE_MACHINE_HASH_CHECK_ENABLED=

ARG POSTGRES_PASSWORD=password
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ARG POSTGRES_DB=rollupsdb
ENV POSTGRES_DB=${POSTGRES_DB}
ENV CARTESI_DATABASE_CONNECTION=postgres://postgres:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}?sslmode=disable
ENV PGDATA=${BASE_PATH}/database

ENV CARTESI_CONTRACTS_INPUT_BOX_ADDRESS=0xB6b39Fb3dD926A9e3FBc7A129540eEbeA3016a6c
ENV CARTESI_CONTRACTS_AUTHORITY_FACTORY_ADDRESS=0x451f57Ca716046D114Ab9ff23269a2F9F4a1bdaF
ENV CARTESI_CONTRACTS_APPLICATION_FACTORY_ADDRESS=0x2210ad1d9B0bD2D470c2bfA4814ab6253BC421A0
ENV CARTESI_CONTRACTS_SELF_HOSTED_APPLICATION_FACTORY_ADDRESS=0x4a409e1CaB9229711C4e1f68625DdbC75809e721

ENV APP_NAME=
ENV APPLICATION_ADDRESS=
ENV CONSENSUS_ADDRESS=
# ENV APPLICATION_ADDRESS=0x73c04b5b77a28a43c948b1aa34ecaf1fe3e7890f
# ENV CONSENSUS_ADDRESS=0x1d76BDB32803AE72fc5aed528779B3f581f93FED

################################################################################
# Configure s6 create dir
RUN <<EOF
mkdir -p ${BASE_PATH}
chown -R cartesi:cartesi ${BASE_PATH}
mkdir -p /etc/s6-overlay/s6-rc.d/prepare-dirs
echo "oneshot" > /etc/s6-overlay/s6-rc.d/prepare-dirs/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/prepare-dirs/run.sh
#!/command/with-contenv sh
mkdir -p "${SNAPSHOTS_APPS_PATH}"
mkdir -p "${NODE_PATH}"/snapshots
mkdir -p "${NODE_PATH}"/data
mkdir -p "${ESPRESSO_PATH}"
mkdir -p "${PGDATA}"
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/prepare-dirs/up
/etc/s6-overlay/s6-rc.d/prepare-dirs/run.sh
EOF

################################################################################
# Configure s6 Postgres
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/database/dependencies.d
touch /etc/s6-overlay/s6-rc.d/database/dependencies.d/prepare-dirs
touch /etc/s6-overlay/s6-rc.d/user/contents.d/database
echo "longrun" > /etc/s6-overlay/s6-rc.d/database/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/database/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/database: /" }
fdmove -c 2 1
docker-entrypoint.sh postgres
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/database/data/check
#!/command/execlineb -P
pg_isready
EOF

################################################################################
# Configure s6 anvil
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/devnet
echo "longrun" > /etc/s6-overlay/s6-rc.d/devnet/type
EOF

COPY localhost-state.json /etc/s6-overlay/s6-rc.d/devnet/data/

COPY <<EOF /etc/s6-overlay/s6-rc.d/devnet/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/devnet: /" }
fdmove -c 2 1
anvil -q --load-state=/etc/s6-overlay/s6-rc.d/devnet/data/localhost-state.json --host 0.0.0.0 --block-time 1 --slots-in-an-epoch 1
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/database/data/check
#!/command/execlineb -P
curl -s -X POST http://localhost:8545 -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}' >> /dev/null
EOF

################################################################################
# Configure s6 migrate
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/migrate/dependencies.d
touch /etc/s6-overlay/s6-rc.d/migrate/dependencies.d/database
touch /etc/s6-overlay/s6-rc.d/user/contents.d/migrate
echo "oneshot" > /etc/s6-overlay/s6-rc.d/migrate/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/migrate/run.sh
#!/command/with-contenv sh
cartesi-rollups-cli db init
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/migrate/up
/etc/s6-overlay/s6-rc.d/migrate/run.sh
EOF

################################################################################
# Configure s6 node
ENV NODE_ENVFILE=${NODE_PATH}/node-envs

RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/define-node-envs/dependencies.d
touch /etc/s6-overlay/s6-rc.d/define-node-envs/dependencies.d/prepare-dirs
touch /etc/s6-overlay/s6-rc.d/user/contents.d/define-node-envs
echo "oneshot" > /etc/s6-overlay/s6-rc.d/define-node-envs/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/define-node-envs/run.sh
#!/command/with-contenv sh
if [ \${MAIN_SEQUENCER} = espresso ]; then
    echo "CARTESI_FEATURE_INPUT_READER_ENABLED=false" > \${NODE_ENVFILE}
else
    echo "CARTESI_FEATURE_INPUT_READER_ENABLED=true" > \${NODE_ENVFILE}
fi
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/define-node-envs/up
/etc/s6-overlay/s6-rc.d/define-node-envs/run.sh
EOF


RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/cartesi-node/dependencies.d
touch /etc/s6-overlay/s6-rc.d/cartesi-node/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/cartesi-node/dependencies.d/migrate \
    /etc/s6-overlay/s6-rc.d/cartesi-node/dependencies.d/define-node-envs \
    /etc/s6-overlay/s6-rc.d/cartesi-node/dependencies.d/database \
    /etc/s6-overlay/s6-rc.d/cartesi-node/dependencies.d/devnet
touch /etc/s6-overlay/s6-rc.d/user/contents.d/cartesi-node
echo "longrun" > /etc/s6-overlay/s6-rc.d/cartesi-node/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/cartesi-node/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/cartesi-node: /" }
fdmove -c 2 1
importas -S NODE_ENVFILE
envfile \${NODE_ENVFILE}
cartesi-rollups-node
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/cartesi-node/data/check
#!/command/execlineb -P
curl -G -f -H 'Content-Type: application/json' http://127.0.0.1:10000/healthz
EOF

################################################################################
# Configure s6 create espresso db
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/createespressonodedb/dependencies.d
touch /etc/s6-overlay/s6-rc.d/createespressonodedb/dependencies.d/database
echo "oneshot" > /etc/s6-overlay/s6-rc.d/createespressonodedb/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/createespressonodedb/run.sh
#!/command/with-contenv bash
psql \${CARTESI_DATABASE_CONNECTION} -c "create database \${ESPRESSONODE_DB};" && echo "Espresso node database created!" || echo "Espresso node database alredy created"
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/createespressonodedb/up
/etc/s6-overlay/s6-rc.d/createespressonodedb/run.sh
EOF

################################################################################
# Configure s6 espresso dev node

ENV ESPRESSO_ENVFILE=${NODE_PATH}/espresso-envs

RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/define-espresso-envs/dependencies.d
touch /etc/s6-overlay/s6-rc.d/define-espresso-envs/dependencies.d/prepare-dirs
echo "oneshot" > /etc/s6-overlay/s6-rc.d/define-espresso-envs/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/define-espresso-envs/run.sh
#!/command/with-contenv sh
echo "POSTGRES_ESPRESSO_DB_URL=\${CARTESI_DATABASE_CONNECTION}" > \${ESPRESSO_ENVFILE}
sed -i -e "s/\${NODE_DB}/\${ESPRESSONODE_DB}/" \${ESPRESSO_ENVFILE}
sed -i -e "s/?sslmode=disable//" \${ESPRESSO_ENVFILE}
echo "ESPRESSONODE_RUST_LOG=\${CARTESI_LOG_LEVEL}" >> \${ESPRESSO_ENVFILE}
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/define-espresso-envs/up
/etc/s6-overlay/s6-rc.d/define-espresso-envs/run.sh
EOF


RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/espresso-node/dependencies.d
touch /etc/s6-overlay/s6-rc.d/espresso-node/dependencies.d/createespressonodedb \
    /etc/s6-overlay/s6-rc.d/espresso-node/dependencies.d/define-espresso-envs
echo "longrun" > /etc/s6-overlay/s6-rc.d/espresso-node/type
mkdir -p /etc/s6-overlay/s6-rc.d/espresso-node/data
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/espresso-node/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/espresso-node: /" }
fdmove -c 2 1
importas -S ESPRESSO_ENVFILE
envfile \${ESPRESSO_ENVFILE}
multisubstitute {
    importas -S POSTGRES_ESPRESSO_DB_URL
    importas -S ESPRESSONODE_RUST_LOG
}
# foreground {
#     echo 'RUST_LOG=\${ESPRESSONODE_RUST_LOG} espresso-dev-node \${POSTGRES_ESPRESSO_DB_URL} \${ESPRESSONODE_EXTRA_FLAGS}'
# }
export RUST_LOG \${ESPRESSONODE_RUST_LOG}
s6-notifyoncheck -s 2000 -w 1000 -t 500 -n 10
espresso-dev-node \${POSTGRES_ESPRESSO_DB_URL}
EOF
# espresso-dev-node \${POSTGRES_ESPRESSO_DB_URL}

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/espresso-node/data/check
#!/command/execlineb -P
with-contenv
multisubstitute {
    importas -S ESPRESSO_SEQUENCER_API_PORT
}
foreground {
    echo "Check espresso node at http://localhost:\${ESPRESSO_SEQUENCER_API_PORT}/v0/status/block-height"
}
curl --silent --fail http://localhost:\${ESPRESSO_SEQUENCER_API_PORT}/v0/status/block-height
EOF

COPY --chmod=644 <<EOF /etc/s6-overlay/s6-rc.d/espresso-node/notification-fd
3
EOF

################################################################################
# Configure s6 migrate espresso
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/migrate-espresso/dependencies.d
touch /etc/s6-overlay/s6-rc.d/migrate-espresso/dependencies.d/migrate
echo "oneshot" > /etc/s6-overlay/s6-rc.d/migrate-espresso/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/migrate-espresso/run.sh
#!/command/with-contenv sh
cartesi-rollups-espresso-reader-db-migration && echo "Espresso database migrated!" || echo "Espresso database not migrated"
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/migrate-espresso/up
/etc/s6-overlay/s6-rc.d/migrate-espresso/run.sh
EOF

################################################################################
# Configure s6 espresso-reader

RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/test-espresso
echo "oneshot" > /etc/s6-overlay/s6-rc.d/test-espresso/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/test-espresso/test.sh
#!/bin/sh
set -e
sleep 1
echo "Testing Espresso Dev Node at '\${ESPRESSO_BASE_URL}/v0/status/block-height'"
block_height=$(curl -s -f \${ESPRESSO_BASE_URL}/v0/status/block-height )
echo "  Waiting block height \${ESPRESSO_STARTING_BLOCK} (current \${block_height})"
[ "\${block_height}" -ge "\${ESPRESSO_STARTING_BLOCK}" ]
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/test-espresso/run.sh
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/test-espresso: /" }
fdmove -c 2 1
loopwhilex -x 0 sh /etc/s6-overlay/s6-rc.d/test-espresso/test.sh
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/test-espresso/up
/etc/s6-overlay/s6-rc.d/test-espresso/run.sh
EOF

RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/espresso-reader/dependencies.d
touch /etc/s6-overlay/s6-rc.d/espresso-reader/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/espresso-reader/dependencies.d/migrate \
    /etc/s6-overlay/s6-rc.d/espresso-reader/dependencies.d/migrate-espresso \
    /etc/s6-overlay/s6-rc.d/espresso-reader/dependencies.d/test-espresso
echo "longrun" > /etc/s6-overlay/s6-rc.d/espresso-reader/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/espresso-reader/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/espresso-reader: /" }
fdmove -c 2 1
cartesi-rollups-espresso-reader
EOF

################################################################################
# Configure s6 stage 2 hook
RUN mkdir -p /etc/s6-overlay/scripts

ENV S6_STAGE2_HOOK=/etc/s6-overlay/scripts/stage2-hook.sh
COPY --chmod=755 <<EOF /etc/s6-overlay/scripts/stage2-hook.sh
#!/command/with-contenv bash
if [[ \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} != 'http://localhost:8545' ]]; then
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/devnet
fi
# decide which reader to start
if [[ \${MAIN_SEQUENCER} = espresso ]]; then
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/define-espresso-envs
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/espresso-node
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/test-espresso
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/migrate-espresso
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/espresso-reader
fi
if [[ ! -z \${APP_NAME} ]]; then
    if [[ -z \${APPLICATION_ADDRESS} ]]; then
        touch /etc/s6-overlay/s6-rc.d/user/contents.d/deploy-app
    else
        touch /etc/s6-overlay/s6-rc.d/user/contents.d/register-app
    fi
fi
EOF

# TODO: fix dependencies when connecting to outside

################################################################################
# Configure s6 build snapshot


################################################################################
# Configure s6 register and deploy application
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/deploy-app/dependencies.d
touch /etc/s6-overlay/s6-rc.d/deploy-app/dependencies.d/cartesi-node
echo "oneshot" > /etc/s6-overlay/s6-rc.d/deploy-app/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/deploy-app/run.sh
#!/command/with-contenv bash
/deploy.sh /mnt/apps/\${APP_NAME}
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/deploy-app/up
/etc/s6-overlay/s6-rc.d/deploy-app/run.sh
EOF

RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/register-app/dependencies.d
touch /etc/s6-overlay/s6-rc.d/register-app/dependencies.d/cartesi-node
echo "oneshot" > /etc/s6-overlay/s6-rc.d/register-app/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/register-app/run.sh
#!/command/with-contenv bash
/register.sh /mnt/apps/\${APP_NAME}
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/register-app/up
/etc/s6-overlay/s6-rc.d/register-app/run.sh
EOF

# COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/register-app/run.sh
# #!/command/execlineb -P
# with-contenv
# export APP_NAME \${APP_NAME}
# export APPLICATION_ADDRESS \${APPLICATION_ADDRESS}
# export CONSENSUS_ADDRESS \${CONSENSUS_ADDRESS}
# /register.sh /mnt/apps/\${APP_NAME}
# EOF

################################################################################
# deploy script
RUN <<EOF
chown -R cartesi:cartesi /mnt
EOF

COPY --chmod=755 <<EOF /deploy.sh
#!/bin/bash
if [ ! -z \${OWNER} ]; then
    owner_args="-o \${OWNER} -O \${OWNER}"
fi
if [ ! -z \${CONSENSUS_ADDRESS} ]; then
    consensus_arg="-c \${CONSENSUS_ADDRESS}"
fi
if [ ! -z \${EPOCH_LENGTH} ]; then
    epoch_arg="-e \${EPOCH_LENGTH}"
fi
if [ ! -z \${SALT} ]; then
    salt_arg="--salt \${SALT}"
fi
if [ ! -z \${APPLICATION_FACTORY_ADDRESS} ]; then
    app_fac_arg="--app-factory \${APPLICATION_FACTORY_ADDRESS}"
fi
if [ ! -z \${AUTHORITY_FACTORY_ADDRESS} ]; then
    auth_fac_arg="--authority-factory \${AUTHORITY_FACTORY_ADDRESS}"
fi
if [[ \${MAIN_SEQUENCER} = espresso ]]; then
    da_arg="-D \$(cast calldata 'InputBoxAndEspresso(address,uint256,uint32)' \$CARTESI_CONTRACTS_INPUT_BOX_ADDRESS \$ESPRESSO_STARTING_BLOCK \$ESPRESSO_NAMESPACE)"
fi
cartesi-rollups-cli app deploy -n \${APP_NAME} --blockchain-http-endpoint \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} \${owner_args} \${consensus_arg} \${epoch_arg} \${salt_arg} \${app_fac_arg} \${auth_fac_arg} \${da_arg} \${EXTRA_ARGS} -t \$1 || echo 'Not deployed'
EOF


COPY --chmod=755 <<EOF /register.sh
#!/bin/bash
if [[ \${MAIN_SEQUENCER} = espresso ]]; then
    da_arg="-D \$(cast calldata 'InputBoxAndEspresso(address,uint256,uint32)' \$CARTESI_CONTRACTS_INPUT_BOX_ADDRESS \$ESPRESSO_STARTING_BLOCK \$ESPRESSO_NAMESPACE)"
fi
cartesi-rollups-cli app register -n \${APP_NAME} --blockchain-http-endpoint \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} -a \${APPLICATION_ADDRESS} -c \${CONSENSUS_ADDRESS} \${da_arg} \${EXTRA_ARGS} -t \$1 || echo 'Not registered'
EOF

WORKDIR /opt/cartesi

RUN <<EOF
chown -R cartesi:cartesi /opt/cartesi
chown -R cartesi:cartesi /etc/s6-overlay/s6-rc.d
EOF

# =============================================================================
# STAGE: cartesapp-cloud-sdk
#
# =============================================================================

FROM base-cartesapp-sdk AS cartesapp-cloud-sdk

RUN touch /etc/s6-overlay/s6-rc.d/user/contents.d/telegraf

# Configure nginx server with cache
COPY --chmod=755 <<EOF /etc/nginx/sites-available/cloud.conf
server {
    listen       80;
    listen  [::]:80;

    proxy_cache mycache;

    location /nonce {
        proxy_pass   http://localhost:${ESPRESSO_SERVICE_PORT}/nonce;
    }

    location /submit {
        proxy_pass   http://localhost:${ESPRESSO_SERVICE_PORT}/submit;
    }

    location /inspect {
        proxy_pass   http://localhost:${CARTESI_INSPECT_PORT}/inspect;
        proxy_cache_valid 200 5s;
        proxy_cache_background_update on;
        proxy_cache_use_stale error timeout updating http_500 http_502
                              http_503 http_504;
        proxy_cache_lock on;

        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }

    location /rpc {
        proxy_pass   http://localhost:${CARTESI_JSONRPC_API_ADDRESS}/rpc;
        proxy_cache_valid 200 1s;
        proxy_cache_background_update on;
        proxy_cache_use_stale error timeout updating http_500 http_502
                              http_503 http_504;
        proxy_cache_lock on;

        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }

    error_page   500 502 503 504  /50x.html;
    location = /50x.html {
        root   /usr/share/nginx/html;
    }
}
EOF

RUN ln -sr /etc/nginx/sites-available/cloud.conf /etc/nginx/sites-enabled/cloud.conf

# Create init wrapper
COPY --chmod=755 <<EOF /init-wrapper
#!/bin/sh
# run /init with PID 1, creating a new PID namespace if necessary
if [ "\$$" -eq 1 ]; then
    # we already have PID 1
    exec /init "\$@"
else
    # create a new PID namespace
    exec unshare --pid sh -c '
        # set up /proc and start the real init in the background
        unshare --mount-proc /init "\$@" &
        child="\$!"
        # forward signals to the real init
        trap "kill -INT \$child" INT
        trap "kill -TERM \$child" TERM
        # wait until the real init exits
        # ("wait" returns early on signals; "kill -0" checks if the process exists)
        until wait "\$child" || ! kill -0 "\$child" 2>/dev/null; do :; done
    ' sh "\$@"
fi
EOF

CMD ["/init-wrapper"]


# =============================================================================
# STAGE: cartesapp-sdk
#
# =============================================================================

FROM base-cartesapp-sdk AS cartesapp-sdk

RUN chown -R cartesi:cartesi /run

# Configure nginx server with cache
COPY --chmod=755 <<EOF /etc/nginx/sites-available/node.conf
server {
    listen       80;
    listen  [::]:80;

    location /nonce {
        proxy_pass   http://localhost:${ESPRESSO_SERVICE_PORT}/nonce;
    }

    location /submit {
        proxy_pass   http://localhost:${ESPRESSO_SERVICE_PORT}/submit;
    }

    location /inspect {
        proxy_pass   http://localhost:${CARTESI_INSPECT_PORT}/inspect;
    }

    location /rpc {
        proxy_pass   http://localhost:${CARTESI_JSONRPC_API_PORT}/rpc;
    }

    error_page   500 502 503 504  /50x.html;
    location = /50x.html {
        root   /usr/share/nginx/html;
    }
}
EOF

RUN ln -sr /etc/nginx/sites-available/node.conf /etc/nginx/sites-enabled/node.conf

# Set user to low-privilege.
USER cartesi

# Set the Go supervisor as the command.
CMD [ "/init" ]
