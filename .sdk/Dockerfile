# syntax=docker.io/docker/dockerfile:1

ARG EMULATOR_VERSION=0.20.0
ARG KERNEL_VERSION=0.20.0
ARG MACHINE_LINUX_VERSION=6.5.13-ctsi-1
ARG NITRO_VERSION=c937fa4fd202074dd250086ebd92de6884968b84 # 0.8.1
ARG SU_EXEC_VERSION=0.3
ARG TELEGRAF_VERSION=1.39.0
ARG ROLLUPSNODE_VERSION=2.0.0-alpha.12
ARG CARTESI_ROLLUPS_VERSION=3.0.0-alpha.6
ARG CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION=3.0.0-alpha.3
ARG CARTESI_ROLLUPS_PRT_REPO=https://github.com/cartesi/dave.git
ARG CUSTOM_CONTRACTS_VERSION=d1f06fc84398a0209f1068b7d1c2dd32d3a6af0a
ARG FOUNDRY_VERSION=1.5.1
ARG XGENEXT2_VERSION=1.5.6
ARG STATE_FILE=/opt/cartesi/devnet/localhost-state.json
ARG CONTRACTS_ENV=/opt/cartesi/devnet/contracts.env

ARG CARTESI_INSPECT_PORT=10012
ARG CARTESI_JSONRPC_API_PORT=10011
ARG CARTESI_NODE_TELEMETRY_ADDRESS=:10000
ARG CARTESI_EVM_READER_TELEMETRY_ADDRESS=:10001
ARG CARTESI_ADVANCER_TELEMETRY_ADDRESS=:10002
ARG CARTESI_VALIDATOR_TELEMETRY_ADDRESS=:10003
ARG CARTESI_CLAIMER_TELEMETRY_ADDRESS=:10004
ARG CARTESI_JSONRPC_API_TELEMETRY_ADDRESS=:10005
ARG CARTESI_PRT_TELEMETRY_ADDRESS=:10006 # 10003
# =============================================================================
# STAGE: foundry-installer
#
# =============================================================================

# baseimage args
ARG DEBIAN_TAG=bookworm-20260223-slim
ARG DEBIAN_DIGEST=sha256:f6e2cfac5cf956ea044b4bd75e6397b4372ad88fe00908045e9a0d21712ae3ba

###
# base image stage
FROM debian:${DEBIAN_TAG}@${DEBIAN_DIGEST} AS common-env

USER root

RUN <<EOF
set -e
apt update
apt install -y --no-install-recommends \
    curl ca-certificates
EOF

################################################################################
# builder image
FROM common-env AS builder
WORKDIR /usr/local/src
ARG DEBIAN_FRONTEND=noninteractive
RUN <<EOF
apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    libarchive-dev \
    libtool \
    liblz4-dev \
    liblzma-dev \
    liblzo2-dev \
    libzstd-dev \
    xz-utils \
    zlib1g-dev
rm -rf /var/lib/apt/lists/*
EOF

################################################################################
# su-exec builder
FROM common-env AS su-exec
ARG SU_EXEC_VERSION
ARG TARGETARCH
WORKDIR /usr/local/bin
RUN <<EOF
set -e
ARCH=${TARGETARCH}

if [ "$ARCH" = "amd64" ]; then
    ARCH="x86_64"
fi

echo curl -fsSL https://github.com/ncopa/su-exec/releases/download/v${SU_EXEC_VERSION}/su-exec-static-v${SU_EXEC_VERSION}-${ARCH} \
  -o su-exec
curl -fsSL https://github.com/ncopa/su-exec/releases/download/v${SU_EXEC_VERSION}/su-exec-static-v${SU_EXEC_VERSION}-${ARCH} \
  -o su-exec
case "${TARGETARCH}" in
    amd64) echo "675e7b454ad96e7631029f0b71c9ad5a6c23b553a8952ed528de1e591ca7cef0 su-exec" | sha256sum --check ;;
    arm64) echo "a08773d4af76a30371f8d1c93e86e8ac2b0379c9e75dce9d694c5059b0544909 su-exec" | sha256sum --check ;;
    *) echo "unsupported architecture: ${TARGETARCH}"; exit 1 ;;
esac
chmod +x su-exec
EOF

################################################################################
# foundry installer
FROM common-env AS foundry
ARG FOUNDRY_VERSION
ARG TARGETARCH
ARG TARGETOS
RUN <<EOF
set -e
mkdir -p /usr/local/bin
curl -fsSL https://github.com/foundry-rs/foundry/releases/download/v${FOUNDRY_VERSION}/foundry_v${FOUNDRY_VERSION}_${TARGETOS}_${TARGETARCH}.tar.gz \
  -o /tmp/foundry.tar.gz
case "${TARGETARCH}" in
    amd64) echo "73640b01bd9ed29fdb4965085099371f8cf0dbbec3e2086cf54564efc4dcfe88 /tmp/foundry.tar.gz" | sha256sum --check ;;
    arm64) echo "cccf28bdf202289e837a9e21ed213b2b80dc1e806e12f1717bc98a44315c331e /tmp/foundry.tar.gz" | sha256sum --check ;;
    *) echo "unsupported architecture: ${TARGETARCH}"; exit 1 ;;
esac
tar -zx -f /tmp/foundry.tar.gz -C /usr/local/bin
EOF

################################################################################
# nitro builder
FROM builder AS nitro
ARG NITRO_VERSION
WORKDIR /usr/local/src
ADD https://github.com/leahneukirchen/nitro.git#${NITRO_VERSION} /usr/local/src
RUN make

################################################################################
# install telegraf
FROM common-env AS telegraf
ARG TELEGRAF_VERSION
ARG TARGETARCH
WORKDIR /tmp
RUN <<EOF
set -e
curl -fsSL https://dl.influxdata.com/telegraf/releases/telegraf-${TELEGRAF_VERSION}_linux_${TARGETARCH}.tar.gz \
    -o ./telegraf.tar.gz;
case "${TARGETARCH}" in
    amd64) echo "a630831411fd2181048a5e3c6d001ea320f7636b3aae020bce439b810efbc76c /tmp/telegraf.tar.gz" | sha256sum --check ;;
    arm64) echo "3c8c271910d8e46e00a10008a7f7afaac3580554c882c5168891709d51118275 /tmp/telegraf.tar.gz" | sha256sum --check ;;
    *) echo "unsupported architecture: ${TARGETARCH}"; exit 1 ;;
esac
tar -xvzf /tmp/telegraf.tar.gz -C / --strip-components=2 ./telegraf-${TELEGRAF_VERSION}/usr/bin/telegraf
cp /usr/bin/telegraf /usr/local/bin/telegraf
telegraf --version
EOF

################################################################################
# config skel
FROM scratch AS skel

ARG CARTESI_INSPECT_PORT
ARG CARTESI_JSONRPC_API_PORT
ARG CARTESI_NODE_TELEMETRY_ADDRESS
ARG CARTESI_EVM_READER_TELEMETRY_ADDRESS
ARG CARTESI_ADVANCER_TELEMETRY_ADDRESS
ARG CARTESI_VALIDATOR_TELEMETRY_ADDRESS
ARG CARTESI_CLAIMER_TELEMETRY_ADDRESS
ARG CARTESI_JSONRPC_API_TELEMETRY_ADDRESS
ARG CARTESI_PRT_TELEMETRY_ADDRESS

COPY --chmod=755 <<EOF /etc/nitro-cmd-runsh
#!/usr/bin/env sh

cleanup() {
    trap - INT TERM EXIT
    kill -TERM -\$\$ 2>/dev/null
}
trap cleanup INT TERM EXIT

\$(dirname \$0)/run.sh &

wait
EOF

################################################################################
# configure telegraf
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

# Configure nitro
COPY --chmod=755 <<EOF /etc/nitro/telegraf/setup
#!/usr/bin/env sh
if [ "\${CLOUD}" != "true" ]; then
    echo "CLOUD not set. Skipping Telegraf service start."
    exit 0
fi
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/telegraf/run.sh
#!/usr/bin/env sh
exec su-exec cartesi /usr/local/bin/telegraf
EOF

COPY --chmod=755 <<EOF /etc/nitro/telegraf/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure nginx

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
        proxy_pass   http://localhost:${CARTESI_JSONRPC_API_PORT}/rpc;
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

# Configure nitro setup
COPY --chmod=755 <<EOF /etc/nitro/nginx/setup
#!/usr/bin/env sh
rm /etc/nginx/sites-enabled/*
if [ "\${CLOUD}" = "true" ]; then
    ln -sr /etc/nginx/sites-available/cloud.conf /etc/nginx/sites-enabled/cloud.conf
else
    ln -sr /etc/nginx/sites-available/node.conf /etc/nginx/sites-enabled/node.conf
fi
cp /etc/nitro-cmd-runsh run
EOF

# Configure nitro
COPY --chmod=755 <<EOF /etc/nitro/nginx/run.sh
#!/usr/bin/env sh
/usr/sbin/nginx -g "daemon off;"
EOF

################################################################################
# Configure create dir

COPY --chmod=755 <<EOF /etc/nitro/prepare-dirs/setup
#!/usr/bin/env sh
mkdir -p "\${SNAPSHOTS_APPS_PATH}"
mkdir -p "\${NODE_PATH}"/snapshots
mkdir -p "\${NODE_PATH}"/data
mkdir -p "\${PGDATA}"
EOF

################################################################################
# Configure Postgres

COPY --chmod=755 <<EOF /etc/nitro/database/setup
#!/usr/bin/env bash
case "\${CARTESI_DATABASE_CONNECTION}" in
    postgres://*:*@localhost:5432/*)
        while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ]; do
            sleep 1
        done
        ;;
    *)
        echo "Not local postgres. Skipping Database service start."
        exit 0
        ;;
esac
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/database/run.sh
#!/usr/bin/env sh
docker-entrypoint.sh postgres
EOF

COPY --chmod=755 <<EOF /etc/nitro/database/finish
#!/usr/bin/env sh
rm -f run
EOF

# check if db is ready
# pg_isready

################################################################################
# Configure anvil

COPY --chmod=755 <<EOF /etc/nitro/devnet/setup
#!/usr/bin/env sh
if [ \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} != 'http://localhost:8545' ]; then
    echo "Not devnet. Skipping Devnet service start."
    exit 0
fi
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/devnet/run.sh
anvil -q --load-state=/opt/cartesi/devnet/localhost-state.json --host 0.0.0.0 --block-time 1 --slots-in-an-epoch 1
EOF

COPY --chmod=755 <<EOF /etc/nitro/devnet/finish
#!/usr/bin/env sh
rm -f run
EOF

COPY --chmod=755 <<EOF /usr/local/bin/devnet_isready
#!/usr/bin/sh
curl -f -s -X POST http://localhost:8545 -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}' >> /dev/null
EOF

################################################################################
# Configure migrate

COPY --chmod=755 <<EOF /etc/nitro/migrate/setup
#!/usr/bin/env bash
case "\${CARTESI_DATABASE_CONNECTION}" in
    postgres://*:*@localhost:5432/*)
        while ! pg_isready; do
            sleep 1
        done
        ;;
    *)
        ;;
esac
cartesi-rollups-cli db init
EOF

################################################################################
# Configure evm-reader

COPY --chmod=755 <<EOF /etc/nitro/evm-reader/setup
#!/usr/bin/env sh
if [ "\${ACTIVATE_CARTESI_NODE}" != "true" ]; then
    echo "Cartesi Rollups node not activated. Skipping evm-reader service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/evm-reader/run.sh
#!/usr/bin/env sh
cartesi-rollups-evm-reader --telemetry-address ${CARTESI_EVM_READER_TELEMETRY_ADDRESS}
EOF

COPY --chmod=755 <<EOF /etc/nitro/evm-reader/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure advancer

COPY --chmod=755 <<EOF /etc/nitro/advancer/setup
#!/usr/bin/env sh
if [ "\${ACTIVATE_CARTESI_NODE}" != "true" ]; then
    echo "Cartesi Rollups node not activated. Skipping advancer service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/advancer/run.sh
#!/usr/bin/env sh
cartesi-rollups-advancer --telemetry-address ${CARTESI_ADVANCER_TELEMETRY_ADDRESS}
EOF

COPY --chmod=755 <<EOF /etc/nitro/advancer/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure validator

COPY --chmod=755 <<EOF /etc/nitro/validator/setup
#!/usr/bin/env sh
if [ "\${ACTIVATE_CARTESI_NODE}" != "true" ]; then
    echo "Cartesi Rollups node not activated. Skipping validator service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/validator/run.sh
#!/usr/bin/env sh
cartesi-rollups-validator --telemetry-address ${CARTESI_VALIDATOR_TELEMETRY_ADDRESS}
EOF

COPY --chmod=755 <<EOF /etc/nitro/validator/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure claimer

COPY --chmod=755 <<EOF /etc/nitro/claimer/setup
#!/usr/bin/env sh
if [ "\${ACTIVATE_CARTESI_NODE}" != "true" ]; then
    echo "Cartesi Rollups node not activated. Skipping claimer service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/claimer/run.sh
#!/usr/bin/env sh
cartesi-rollups-claimer --telemetry-address ${CARTESI_CLAIMER_TELEMETRY_ADDRESS}
EOF

COPY --chmod=755 <<EOF /etc/nitro/claimer/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure jsonrpc api

COPY --chmod=755 <<EOF /etc/nitro/jsonrpc-api/setup
#!/usr/bin/env sh
if [ "\${ACTIVATE_CARTESI_NODE}" != "true" ]; then
    echo "Cartesi Rollups node not activated. Skipping jsonrpc-api service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/jsonrpc-api/run.sh
#!/usr/bin/env sh
cartesi-rollups-jsonrpc-api  --telemetry-address ${CARTESI_JSONRPC_API_TELEMETRY_ADDRESS}
EOF

COPY --chmod=755 <<EOF /etc/nitro/jsonrpc-api/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure prt

COPY --chmod=755 <<EOF /etc/nitro/prt/setup
#!/usr/bin/env sh
if [ "\${ACTIVATE_CARTESI_NODE}" != "true" ] || [ "\${CARTESI_FEATURE_PRT_ENABLED}" != "true" ]; then
    echo "Cartesi Rollups node not activated. Skipping prt service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
cp /etc/nitro-cmd-runsh run
EOF

COPY --chmod=755 <<EOF /etc/nitro/prt/run
#!/usr/bin/env sh
cartesi-rollups-prt --telemetry-address ${CARTESI_PRT_TELEMETRY_ADDRESS}
EOF

COPY --chmod=755 <<EOF /etc/nitro/prt/finish
#!/usr/bin/env sh
rm -f run
EOF

################################################################################
# Configure register and deploy application

COPY --chmod=755 <<EOF /etc/nitro/deployer/setup
#!/usr/bin/env bash
if [ -z \${APP_NAME} ] || [ ! -z \${APPLICATION_ADDRESS} ]; then
    echo "No App name provided (or the app address was provided). Skipping deployer service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
/deploy.sh /mnt/apps/\${APP_NAME}
EOF

COPY --chmod=755 <<EOF /etc/nitro/register/setup
#!/usr/bin/env bash
if [ -z \${APP_NAME} ] || [ -z \${APPLICATION_ADDRESS} ]; then
    echo "No App name provided (or app address). Skipping register service start."
    exit 0
fi
while [ "\$(nitroctl list prepare-dirs | awk '{print \$1}')" != "ONESHOT" ] && [ "\$(nitroctl list migrate | awk '{print \$1}')" != "ONESHOT" ]; do
    sleep 1
done
/register.sh /mnt/apps/\${APP_NAME}
EOF

################################################################################
# deploy script

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
if [ ! -z "\${WITHDRAWAL_CONFIG}" ]; then
    withdrawal_config_arg="--withdrawal-config '\${WITHDRAWAL_CONFIG}'"
fi
if [ ! -z "\${CLAIM_STAGING_PERIOD}" ]; then
    staging_arg="--claim-staging-period \${CLAIM_STAGING_PERIOD}"
fi
timeout 22 bash -c 'until curl -s -X POST \${CARTESI_BLOCKCHAIN_HTTP_ENDPOINT} -H "Content-Type: application/json" --data '"'"'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}'"'"' >> /dev/null ; do sleep 1 && echo "waiting chain"; done'
(cartesi-rollups-cli deploy application \${APP_NAME} \$1 \${owner_args} \${consensus_arg} \${dave_fac_arg} \${prt_arg} \${epoch_arg} \${salt_arg} \${withdrawal_config_arg} \${staging_arg} \${EXTRA_ARGS} --execution-parameters-file - <<< '{
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

# =============================================================================
# STAGE: build-devnet
#
# =============================================================================

FROM common-env AS build-devnet

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get install -y --no-install-recommends jq ssh git

COPY --from=foundry /usr/local/bin/forge /usr/local/bin/
COPY --from=foundry /usr/local/bin/anvil /usr/local/bin/
COPY --from=foundry /usr/local/bin/cast /usr/local/bin/

WORKDIR /opt/cartesi/contracts

ARG CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION
ARG CARTESI_ROLLUPS_PRT_REPO
RUN <<EOF
# set -e
mkdir dave
cd dave

forge soldeer install dave~${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION} --git ${CARTESI_ROLLUPS_PRT_REPO} --tag v${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION} --recursive-deps --config-location foundry

cd dependencies/dave-${CARTESI_ROLLUPS_PRT_CONTRACTS_VERSION}/prt/contracts/
forge soldeer install

cd ../../cartesi-rollups/contracts
forge soldeer install

chmod +x script/build-devnet.sh
chmod +x script/deploy.sh
EOF

ARG CUSTOM_CONTRACTS_VERSION
ADD https://github.com/lynoferraz/aux-cr-contracts.git#${CUSTOM_CONTRACTS_VERSION} /opt/cartesi/contracts/custom
RUN <<EOF
# set -e
cd custom
forge soldeer install
EOF

ARG CARTESI_ROLLUPS_VERSION
ARG STATE_FILE
ARG CONTRACTS_ENV
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
    '/opt/cartesi/contracts/custom'
)

for root in "\${roots[@]}"
do
    echo "running deployment on \${root}"
    forge script --root "\$root" DeploymentScript --broadcast --non-interactive --private-key "\$private_key" --rpc-url "\$rpc_url" --slow
done

find . -path "*/deployments/31337/*.json" -type f -exec cat {} \\; | jq -rs '.[] | "\\(.contractName)=\\"\\(.address)\\""' | sort | uniq >> ${CONTRACTS_ENV}
source ${CONTRACTS_ENV}

cast send --json --rpc-url "\$rpc_url" --private-key "\$private_key" \\
    \${SelfHostedApplicationFactory} \\
    "deployContracts(address,uint256,uint256,address,bytes32,bytes,(address,uint8,uint8,uint64,address),bytes32)" \\
    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \\
    10 \\
    5 \\
    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \\
    0x0000000000000000000000000000000000000000000000000000000000000000 \\
    0xb12c9ede000000000000000000000000\${InputBox:2} \\
    "(0x0000000000000000000000000000000000000000,0,0,0x0,0x0000000000000000000000000000000000000000)" \\
    0x0000000000000000000000000000000000000000000000000000000000000000 > deploy_output.json

echo DeployedAuthority=\$(cat deploy_output.json | jq '.logs[0].address') >> ${CONTRACTS_ENV}
echo DeployedBlankApplication=\$(cat deploy_output.json | jq '.logs[2].address') >> ${CONTRACTS_ENV}

kill \$anvil_pid
wait \$anvil_pid
EOF

# authority 0xd693cc06ffcbe2b82d416a0d4b623b5d83b2e182
# app address 0x51bb5ee19f3248e5b19ee7d5229c101fdf5861ff

RUN mkdir -p $(dirname ${STATE_FILE}) $(dirname ${CONTRACTS_ENV})

RUN /dump-devnet-state.sh

# build and run devnet only
# docker build --target build-devnet -f .sdk/Dockerfile -t devnet .
# docker run --rm -p 8545:8545 devnet anvil --load-state=/usr/share/devnet/anvil_state.json --host 0.0.0.0 --block-time 1 --slots-in-an-epoch 1

# =============================================================================
# STAGE: base-cartesapp-sdk
#
# =============================================================================

FROM postgres:16-trixie AS base-cartesapp-sdk
ARG TARGETARCH

# Download system dependencies required at runtime.
ARG DEBIAN_FRONTEND=noninteractive
RUN <<EOF
set -e
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    xz-utils \
    nginx \
    postgresql-client \
    lua5.4 \
    libslirp0 \
    libglib2.0-0 \
    libarchive13 \
    squashfs-tools \
    libgomp1 \
    bsdextrautils
EOF

# install cm emulator
ARG EMULATOR_VERSION
RUN <<EOF
set -e
curl -s -L -o /tmp/cartesi-machine.deb https://github.com/cartesi/machine-emulator/releases/download/v${EMULATOR_VERSION}/machine-emulator_${TARGETARCH}.deb
apt-get install -y --no-install-recommends /tmp/cartesi-machine.deb
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
apt-get install -y --no-install-recommends /tmp/xgenext2fs.deb
xgenext2fs --version
EOF

ARG ROLLUPSNODE_VERSION
RUN <<EOF
set -e
curl -s -L -o /tmp/cartesi-rollups-node.deb https://github.com/cartesi/rollups-node/releases/download/v${ROLLUPSNODE_VERSION}/cartesi-rollups-node-v${ROLLUPSNODE_VERSION}_${TARGETARCH}.deb
apt-get install -y --no-install-recommends /tmp/cartesi-rollups-node.deb
EOF

# install foundry
COPY --from=foundry /usr/local/bin/anvil /usr/local/bin/
COPY --from=foundry /usr/local/bin/cast /usr/local/bin/

COPY --from=su-exec /usr/local/bin/su-exec /usr/local/bin/
COPY --from=nitro /usr/local/src/nitro /usr/local/bin/
COPY --from=nitro /usr/local/src/nitroctl /usr/local/bin/
COPY --from=telegraf /usr/local/bin/telegraf /usr/local/bin/
COPY --from=skel / /

ARG STATE_FILE
ARG CONTRACTS_ENV
COPY --from=build-devnet ${STATE_FILE} ${STATE_FILE}
COPY --from=build-devnet ${CONTRACTS_ENV} ${CONTRACTS_ENV}


RUN <<EOF
mkdir -p /run/nitro
chown -R cartesi:cartesi /run/nitro
chmod +x /etc/nitro/*/run
EOF

ARG BASE_PATH=/mnt
ENV BASE_PATH=${BASE_PATH}

ENV NODE_PATH=${BASE_PATH}/cartesi-rollups-node
ENV SNAPSHOTS_APPS_PATH=${NODE_PATH}/apps

ARG ROOTFS=./root.ext2
ADD ${ROOTFS} /usr/share/cartesi-machine/images/rootfs.ext2

RUN rm -rf /var/lib/apt/lists/* /var/log/* /var/cache/* /tmp/*

RUN useradd --user-group cartesi

RUN <<EOF
mkdir -p /var/log/nginx/
chown -R cartesi:cartesi /var/lib/nginx
EOF

# =============================================================================
# STAGE: cartesapp-sdk
#
# =============================================================================

FROM base-cartesapp-sdk AS cartesapp-sdk

USER cartesi

################################################################################
# Env variables
ARG CARTESI_INSPECT_PORT
ENV CARTESI_INSPECT_PORT=${CARTESI_INSPECT_PORT}
ENV CARTESI_INSPECT_PORT=${CARTESI_INSPECT_PORT}
ENV CARTESI_INSPECT_ADDRESS=localhost:${CARTESI_INSPECT_PORT}
ARG CARTESI_JSONRPC_API_PORT
ENV CARTESI_JSONRPC_API_PORT=${CARTESI_JSONRPC_API_PORT}
ENV CARTESI_JSONRPC_API_ADDRESS=localhost:${CARTESI_JSONRPC_API_PORT}
ENV CARTESI_SNAPSHOTS_DIR=${NODE_PATH}/snapshots

ARG CARTESI_NODE_TELEMETRY_ADDRESS
ARG CARTESI_EVM_READER_TELEMETRY_ADDRESS
ARG CARTESI_ADVANCER_TELEMETRY_ADDRESS
ARG CARTESI_VALIDATOR_TELEMETRY_ADDRESS
ARG CARTESI_CLAIMER_TELEMETRY_ADDRESS
ARG CARTESI_JSONRPC_API_TELEMETRY_ADDRESS
ARG CARTESI_PRT_TELEMETRY_ADDRESS

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

ENV CARTESI_CONTRACTS_INPUT_BOX_ADDRESS=0x346B3df038FE9f8380071eC6514D5a83aD143939
ENV CARTESI_CONTRACTS_QUORUM_FACTORY_ADDRESS=0x1f94009389F408B8D0ADfFcF8BBDCe5552BaCa5F
ENV CARTESI_CONTRACTS_AUTHORITY_FACTORY_ADDRESS=0x3C1FE01c542a88A523FF6847eD1E26176c8C4ED0
ENV CARTESI_CONTRACTS_APPLICATION_FACTORY_ADDRESS=0xC549F89cF1ca43eDDECC64Ac2208F4b283B1c483
ENV CARTESI_CONTRACTS_SELF_HOSTED_APPLICATION_FACTORY_ADDRESS=0x6145C5996a71a379E030aEb0440df79D60833418
ENV CARTESI_CONTRACTS_DAVE_APP_FACTORY_ADDRESS=0x33FFf0b681c90664dD048a60400AE2D827a4c5bb


ENV ACTIVATE_CARTESI_NODE=true

ENV APP_NAME=
ENV APPLICATION_ADDRESS=
ENV CONSENSUS_ADDRESS=

ARG CONTRACTS_ENV
ENV CONTRACTS_ENV=${CONTRACTS_ENV}

# Set user to low-privilege.
USER cartesi

USER root
WORKDIR ${NODE_PATH}
VOLUME [ ${BASE_PATH} ]

CMD ["nitro"]
