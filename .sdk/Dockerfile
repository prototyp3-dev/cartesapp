# syntax=docker.io/docker/dockerfile:1.4

ARG EMULATOR_VERSION=0.19.0
ARG KERNEL_VERSION=0.20.0
ARG MACHINE_LINUX_VERSION=6.5.13-ctsi-1
ARG S6_OVERLAY_VERSION=3.2.0.2
ARG TELEGRAF_VERSION=1.32.1
ARG TRAEFIK_VERSION=3.2.0
ARG GOVERSION=1.24.4
ARG GO_BUILD_PATH=/build/cartesi/go
ARG ROLLUPSNODE_VERSION=2.0.0-alpha.9
ARG ROLLUPSNODE_BRANCH=fix/handle-http-on-chunked-filter-logs
ARG ROLLUPSNODE_DIR=rollups-node
ARG CARTESI_ROLLUPS_VERSION=2.1.1
ARG CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION=2.0.2
ARG FOUNDRY_DIR=/foundry
ARG FOUNDRY_VERSION=1.4.3
ARG XGENEXT2_VERSION=1.5.6
ARG STATE_FILE=/usr/share/devnet/anvil_state.json

# =============================================================================
# STAGE: foundry-installer
#
# =============================================================================

FROM ubuntu:24.04 AS common-env

USER root

RUN <<EOF
apt update
apt install -y --no-install-recommends \
    curl ca-certificates
EOF

FROM common-env AS foundry-installer

RUN <<EOF
apt update
apt install -y --no-install-recommends git
EOF

# install foundry
ARG FOUNDRY_DIR
ARG FOUNDRY_VERSION
ENV FOUNDRY_DIR=${FOUNDRY_DIR}
RUN mkdir -p ${FOUNDRY_DIR}
RUN curl -L https://foundry.paradigm.xyz | bash
RUN ${FOUNDRY_DIR}/bin/foundryup -i ${FOUNDRY_VERSION}

# =============================================================================
# STAGE: build-devnet
#
# =============================================================================

FROM common-env AS build-devnet

ARG DEBIAN_FRONTEND=noninteractive
RUN <<EOF
set -e
apt-get update
apt-get install -y --no-install-recommends jq
EOF

ARG FOUNDRY_DIR
COPY --from=foundry-installer ${FOUNDRY_DIR}/bin/* /usr/local/bin/

WORKDIR /opt/cartesi/contracts

ARG PRT_ANVIL_STATE_FILE=prt-anvil-state.json

ARG CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION
RUN <<EOF
# set -e
mkdir dave
cd dave

forge soldeer install dave~${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION} --config-location foundry

cd dependencies/dave-${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION}/prt/contracts/
forge soldeer install

cd ../../cartesi-rollups/contracts
forge soldeer install

chmod +x script/build-devnet.sh
chmod +x script/deploy.sh

EOF
ARG CARTESI_ROLLUPS_VERSION
ARG STATE_FILE
COPY --chmod=755 <<EOF /dump-devnet-state.sh
#!/bin/bash
set -e
anvil --dump-state ${STATE_FILE} --preserve-historical-states > /tmp/anvil.log 2>&1 & anvil_pid=\$!
timeout 22 bash -c 'until curl -s -X POST http://localhost:8545 -H "Content-Type: application/json" --data '"'"'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}'"'"' >> /dev/null ; do sleep 1 && echo "wait"; done'

rpc_url='http://127.0.0.1:8545'
private_key='0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'

roots=(
    '/opt/cartesi/contracts/dave/dependencies/dave-${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION}/prt/contracts'
    '/opt/cartesi/contracts/dave/dependencies/dave-${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION}/cartesi-rollups/contracts/dependencies/cartesi-rollups-contracts-${CARTESI_ROLLUPS_VERSION}'
    '/opt/cartesi/contracts/dave/dependencies/dave-${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION}/cartesi-rollups/contracts'
)

for root in "\${roots[@]}"
do
    echo "running deployment on \${root}"
    forge script --root "\$root" DeploymentScript --broadcast --non-interactive --private-key "\$private_key" --rpc-url "\$rpc_url" --slow
done

find . -path "*/deployments/31337/*.json" -type f -exec cat {} \\; | jq -rs '.[] | "\\(.contractName)=\\"\\(.address)\\""' >> contracts.env
source /opt/cartesi/contracts/contracts.env

cast send --json --rpc-url "\$rpc_url" --private-key "\$private_key" \\
    \${SelfHostedApplicationFactory} \\
    "deployContracts(address,uint256,address,bytes32,bytes,bytes32)" \\
    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \\
    10 \\
    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \\
    0x0000000000000000000000000000000000000000000000000000000000000000 \\
    0xb12c9ede000000000000000000000000\${InputBox:2} \\
    0x0000000000000000000000000000000000000000000000000000000000000000 > deploy_output.json

kill \$anvil_pid
wait \$anvil_pid
EOF

# authority 0x3e6e5b662a133bd5ff26b3e7989058a7c68ae6be
# app address 0x6c060d453705bc56797d84516feb949c9bd53caa

RUN mkdir -p $(dirname ${STATE_FILE})

RUN /dump-devnet-state.sh

# build and run devnet only
# docker build --target build-devnet -f .sdk/Dockerfile -t devnet .
# docker run --rm -p 8545:8545 devnet anvil --load-state=/usr/share/devnet/anvil_state.json --host 0.0.0.0 --block-time 1 --slots-in-an-epoch 1

# =============================================================================
# STAGE: base-cartesapp-sdk
#
# =============================================================================

FROM postgres:16-bookworm AS base-cartesapp-sdk
ARG TARGETARCH
ARG BASE_PATH=/mnt
ENV BASE_PATH=${BASE_PATH}

ENV SNAPSHOTS_APPS_PATH=${BASE_PATH}/apps
ENV NODE_PATH=${BASE_PATH}/node

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
    mkdir -p ${NODE_PATH}/snapshots ${NODE_PATH}/data
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

# install cm emulator
ARG EMULATOR_VERSION
RUN <<EOF
set -e
curl -s -L -o /tmp/cartesi-machine.deb https://github.com/cartesi/machine-emulator/releases/download/v${EMULATOR_VERSION}/machine-emulator_${TARGETARCH}.deb
dpkg -i /tmp/cartesi-machine.deb
rm /tmp/cartesi-machine.deb
EOF

ARG KERNEL_VERSION
ARG MACHINE_LINUX_VERSION
RUN <<EOF
set -e
curl -s -L https://github.com/cartesi/machine-linux-image/releases/download/v${KERNEL_VERSION}/linux-${MACHINE_LINUX_VERSION}-v${KERNEL_VERSION}.bin \
    -o /usr/share/cartesi-machine/images/linux.bin
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
ADD ${ROOTFS} /usr/share/cartesi-machine/images/rootfs.ext2

ARG ROLLUPSNODE_VERSION
RUN <<EOF
set -e
curl -s -L -o /tmp/cartesi-rollups-node.deb https://github.com/cartesi/rollups-node/releases/download/v${ROLLUPSNODE_VERSION}/cartesi-rollups-node-v${ROLLUPSNODE_VERSION}_${TARGETARCH}.deb
dpkg -i /tmp/cartesi-rollups-node.deb
rm /tmp/cartesi-rollups-node.deb
EOF

# install foundry
ARG FOUNDRY_DIR
COPY --from=foundry-installer ${FOUNDRY_DIR}/bin/* /usr/local/bin/

RUN mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d

################################################################################
# Env variables
ARG CARTESI_INSPECT_PORT=10012
ENV CARTESI_INSPECT_PORT=${CARTESI_INSPECT_PORT}
ENV CARTESI_INSPECT_PORT=${CARTESI_INSPECT_PORT}
ENV CARTESI_INSPECT_ADDRESS=localhost:${CARTESI_INSPECT_PORT}
ARG CARTESI_JSONRPC_API_PORT=10011
ENV CARTESI_JSONRPC_API_PORT=${CARTESI_JSONRPC_API_PORT}
ENV CARTESI_JSONRPC_API_ADDRESS=localhost:${CARTESI_JSONRPC_API_PORT}
ENV CARTESI_SNAPSHOTS_DIR=${NODE_PATH}/snapshots

ARG CARTESI_NODE_TELEMETRY_ADDRESS=:10000
ARG CARTESI_EVM_READER_TELEMETRY_ADDRESS=:10001
ARG CARTESI_ADVANCER_TELEMETRY_ADDRESS=:10002
ARG CARTESI_VALIDATOR_TELEMETRY_ADDRESS=:10003
ARG CARTESI_CLAIMER_TELEMETRY_ADDRESS=:10004
ARG CARTESI_JSONRPC_API_TELEMETRY_ADDRESS=:10005
ARG CARTESI_PRT_TELEMETRY_ADDRESS=:10006 # 10003

ENV NODE_DB=rollupsdb

ENV CARTESI_LOG_LEVEL=info
ENV CARTESI_BLOCKCHAIN_HTTP_ENDPOINT=http://localhost:8545
ENV CARTESI_BLOCKCHAIN_WS_ENDPOINT=ws://localhost:8545
ENV CARTESI_BLOCKCHAIN_ID=31337
ENV CARTESI_AUTH_KIND=private_key
ENV CARTESI_AUTH_PRIVATE_KEY=ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
ENV CARTESI_BLOCKCHAIN_DEFAULT_BLOCK=latest

ENV CARTESI_FEATURE_JSONRPC_API_ENABLED=true
ENV CARTESI_FEATURE_PRT_ENABLED=
ENV CARTESI_FEATURE_MACHINE_HASH_CHECK_ENABLED=

ARG POSTGRES_PASSWORD=password
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ARG POSTGRES_DB=rollupsdb
ENV POSTGRES_DB=${POSTGRES_DB}
ENV CARTESI_DATABASE_CONNECTION=postgres://postgres:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}?sslmode=disable
ENV PGDATA=${BASE_PATH}/database

ENV CARTESI_CONTRACTS_INPUT_BOX_ADDRESS=0x1b51e2992A2755Ba4D6F7094032DF91991a0Cfac
ENV CARTESI_CONTRACTS_AUTHORITY_FACTORY_ADDRESS=0x5a3368b30174d389aFd205a46bAd35BBE6709b8a
ENV CARTESI_CONTRACTS_APPLICATION_FACTORY_ADDRESS=0x26E758238CB6eC5aB70ce0dd52aF2d7b82e1972E
ENV CARTESI_CONTRACTS_SELF_HOSTED_APPLICATION_FACTORY_ADDRESS=0x870240e83b1181b419f18303D4ccC56574De2931
ENV CARTESI_CONTRACTS_DAVE_APP_FACTORY_ADDRESS=0x96cD319eBD67DF6b753766ec000fe639dFba9F6b

ENV ACTIVATE_CARTESI_NODE=true

ENV APP_NAME=
ENV APPLICATION_ADDRESS=
ENV CONSENSUS_ADDRESS=

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

# Configure nginx server with cache
COPY <<EOF /etc/nginx/sites-available/cloud.conf
server {
    listen       80;
    listen  [::]:80;

    proxy_cache mycache;

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

# Configure nginx server without cache
COPY <<EOF /etc/nginx/sites-available/node.conf
server {
    listen       80;
    listen  [::]:80;

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

RUN rm /etc/nginx/sites-enabled/*
RUN chown -R cartesi:cartesi /etc/nginx/sites-enabled

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

ARG STATE_FILE
COPY --from=build-devnet ${STATE_FILE} /etc/s6-overlay/s6-rc.d/devnet/data/localhost-state.json

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
# Configure s6 evm-reader
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/evm-reader/dependencies.d
touch /etc/s6-overlay/s6-rc.d/evm-reader/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/evm-reader/dependencies.d/migrate
echo "longrun" > /etc/s6-overlay/s6-rc.d/evm-reader/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/evm-reader/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/evm-reader: /" }
fdmove -c 2 1
cartesi-rollups-evm-reader --telemetry-address ${CARTESI_EVM_READER_TELEMETRY_ADDRESS}
EOF

################################################################################
# Configure s6 advancer
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/advancer/dependencies.d
touch /etc/s6-overlay/s6-rc.d/advancer/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/advancer/dependencies.d/migrate
echo "longrun" > /etc/s6-overlay/s6-rc.d/advancer/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/advancer/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/advancer: /" }
fdmove -c 2 1
cartesi-rollups-advancer --telemetry-address ${CARTESI_ADVANCER_TELEMETRY_ADDRESS}
EOF

################################################################################
# Configure s6 validator
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/validator/dependencies.d
touch /etc/s6-overlay/s6-rc.d/validator/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/validator/dependencies.d/migrate
echo "longrun" > /etc/s6-overlay/s6-rc.d/validator/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/validator/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/validator: /" }
fdmove -c 2 1
cartesi-rollups-validator --telemetry-address ${CARTESI_VALIDATOR_TELEMETRY_ADDRESS}
EOF

################################################################################
# Configure s6 claimer
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/claimer/dependencies.d
touch /etc/s6-overlay/s6-rc.d/claimer/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/claimer/dependencies.d/migrate
echo "longrun" > /etc/s6-overlay/s6-rc.d/claimer/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/claimer/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/claimer: /" }
fdmove -c 2 1
cartesi-rollups-claimer --telemetry-address ${CARTESI_CLAIMER_TELEMETRY_ADDRESS}
EOF

################################################################################
# Configure s6 jsonrpc api
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/jsonrpc-api/dependencies.d
touch /etc/s6-overlay/s6-rc.d/jsonrpc-api/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/jsonrpc-api/dependencies.d/migrate
echo "longrun" > /etc/s6-overlay/s6-rc.d/jsonrpc-api/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/jsonrpc-api/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/jsonrpc-api: /" }
fdmove -c 2 1
cartesi-rollups-jsonrpc-api  --telemetry-address ${CARTESI_JSONRPC_API_TELEMETRY_ADDRESS}
EOF

################################################################################
# Configure s6 prt
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/prt/dependencies.d
touch /etc/s6-overlay/s6-rc.d/prt/dependencies.d/prepare-dirs \
    /etc/s6-overlay/s6-rc.d/prt/dependencies.d/migrate
echo "longrun" > /etc/s6-overlay/s6-rc.d/prt/type
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/prt/run
#!/command/execlineb -P
with-contenv
pipeline -w { sed --unbuffered "s/^/prt: /" }
fdmove -c 2 1
cartesi-rollups-prt --telemetry-address ${CARTESI_PRT_TELEMETRY_ADDRESS}
EOF

################################################################################
# Configure s6 stage 2 hook
RUN mkdir -p /etc/s6-overlay/scripts

ENV S6_STAGE2_HOOK=/etc/s6-overlay/scripts/stage2-hook.sh
COPY --chmod=755 <<EOF /etc/s6-overlay/scripts/stage2-hook.sh
#!/command/with-contenv bash
if [[ "\${CLOUD}" = "true" ]]; then
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/telegraf
    ln -sr /etc/nginx/sites-available/cloud.conf /etc/nginx/sites-enabled/cloud.conf
else
    ln -sr /etc/nginx/sites-available/node.conf /etc/nginx/sites-enabled/node.conf
fi
if [[ \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} = 'http://localhost:8545' ]]; then
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/devnet
fi
if [[ \${CARTESI_DATABASE_CONNECTION} = postgres://*:*@localhost:5432/* ]]; then
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/database
    touch /etc/s6-overlay/s6-rc.d/migrate/dependencies.d/database
fi
if [[ "\${ACTIVATE_CARTESI_NODE}" = "true" ]]; then
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/nginx
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/migrate
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/advancer
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/claimer
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/validator
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/evm-reader
    if [ \${CARTESI_FEATURE_JSONRPC_API_ENABLED} = "true" ]; then
        touch /etc/s6-overlay/s6-rc.d/user/contents.d/jsonrpc-api
    fi
    if [ "\${CARTESI_FEATURE_PRT_ENABLED}" = "true" ]; then
        touch /etc/s6-overlay/s6-rc.d/user/contents.d/prt
    fi
fi
if [[ ! -z \${APP_NAME} ]]; then
    if [[ -z \${APPLICATION_ADDRESS} ]]; then
        touch /etc/s6-overlay/s6-rc.d/user/contents.d/deploy-app
    else
        touch /etc/s6-overlay/s6-rc.d/user/contents.d/register-app
    fi
fi
EOF

################################################################################
# Configure s6 build snapshot


################################################################################
# Configure s6 register and deploy application
RUN <<EOF
mkdir -p /etc/s6-overlay/s6-rc.d/deploy-app/dependencies.d
touch /etc/s6-overlay/s6-rc.d/deploy-app/dependencies.d/migrate
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
touch /etc/s6-overlay/s6-rc.d/register-app/dependencies.d/migrate
echo "oneshot" > /etc/s6-overlay/s6-rc.d/register-app/type
EOF

COPY --chmod=755 <<EOF /etc/s6-overlay/s6-rc.d/register-app/run.sh
#!/command/with-contenv bash
/register.sh /mnt/apps/\${APP_NAME}
EOF

COPY <<EOF /etc/s6-overlay/s6-rc.d/register-app/up
/etc/s6-overlay/s6-rc.d/register-app/run.sh
EOF

################################################################################
# deploy script
RUN <<EOF
chown -R cartesi:cartesi /mnt
EOF

COPY --chmod=755 <<EOF /deploy.sh
#!/bin/bash
if [ ! -z \${OWNER} ]; then
    owner_args="--application-owner \${OWNER} --authority-owner \${OWNER}"
fi
if [ ! -z \${CONSENSUS_ADDRESS} ]; then
    consensus_arg="--consensus \${CONSENSUS_ADDRESS}"
fi
if [ ! -z \${EPOCH_LENGTH} ]; then
    epoch_arg="--epoch-length \${EPOCH_LENGTH}"
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
if [ ! -z \${DAVE_APP_FACTORY_ADDRESS} ]; then
    dave_fac_arg="--prt-factory \${DAVE_APP_FACTORY_ADDRESS}"
fi
if [ "\${PRT_CONSENSUS}" = "true" ]; then
    prt_arg="--prt"
fi
timeout 22 bash -c 'until curl -s -X POST \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} -H "Content-Type: application/json" --data '"'"'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}'"'"' >> /dev/null ; do sleep 1 && echo "waiting chain"; done'
(cartesi-rollups-cli deploy application \${APP_NAME} \$1 \${owner_args} \${consensus_arg} \${dave_fac_arg} \${prt_arg} \${epoch_arg} \${salt_arg} \${EXTRA_ARGS} --execution-parameters-file - <<< '{
  "snapshot_policy": "EVERY_INPUT",
  "advance_inc_cycles": "0x400000",
  "advance_max_cycles": "0x3fffffffffffffff",
  "inspect_inc_cycles": "0x400000",
  "inspect_max_cycles": "0x3fffffffffffffff",
  "advance_inc_deadline": "0x2540be400",
  "advance_max_deadline": "0x29e8d60800",
  "inspect_inc_deadline": "0x2540be400",
  "inspect_max_deadline": "0x29e8d60800",
  "load_deadline": "0x45d964b800",
  "store_deadline": "0x29e8d60800",
  "fast_deadline": "0x12a05f200",
  "max_concurrent_inspects": 10
}'
)|| echo 'Not deployed'
EOF

COPY --chmod=755 <<EOF /register.sh
#!/bin/bash
if [ "\${PRT_CONSENSUS}" = "true" ]; then
    prt_arg="--prt"
fi
timeout 22 bash -c 'until curl -s -X POST \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} -H "Content-Type: application/json" --data '"'"'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}'"'"' >> /dev/null ; do sleep 1 && echo "waiting chain"; done'
(cartesi-rollups-cli app register --name \${APP_NAME} --address \${APPLICATION_ADDRESS} --consensus \${CONSENSUS_ADDRESS} \${prt_arg} \${EXTRA_ARGS} --template-path \$1 --execution-parameters-file - <<< '{
  "snapshot_policy": "EVERY_INPUT",
  "advance_inc_cycles": "0x400000",
  "advance_max_cycles": "0x3fffffffffffffff",
  "inspect_inc_cycles": "0x400000",
  "inspect_max_cycles": "0x3fffffffffffffff",
  "advance_inc_deadline": "0x2540be400",
  "advance_max_deadline": "0x29e8d60800",
  "inspect_inc_deadline": "0x2540be400",
  "inspect_max_deadline": "0x29e8d60800",
  "load_deadline": "0x45d964b800",
  "store_deadline": "0x29e8d60800",
  "fast_deadline": "0x12a05f200",
  "max_concurrent_inspects": 10
}'
)|| echo 'Not registered'
EOF

WORKDIR /opt/cartesi

RUN <<EOF
chown -R cartesi:cartesi /opt/cartesi
chown -R cartesi:cartesi /etc/s6-overlay/s6-rc.d
chown -R cartesi:cartesi /run
EOF

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

# =============================================================================
# STAGE: cartesapp-sdk
#
# =============================================================================

FROM base-cartesapp-sdk AS cartesapp-sdk

# Set user to low-privilege.
USER cartesi

ENTRYPOINT [ "/init" ]
