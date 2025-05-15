# Cartesapp

## Requirements

- [venv](https://docs.python.org/3/library/venv.html), Python virtual environment
- [npm](https://docs.npmjs.com/cli/v9/configuring-npm/install) to install dependencies and run the frontend
- [json-schema-to-typescript](https://www.npmjs.com/package/json-schema-to-typescript) to generate typescript interfaces`npm install -g json-schema-to-typescript --save`

## Installing

After you create a virtual environment and activate it you can install with

```shell
pip3 install git+https://github.com/prototyp3-dev/cartesapp@main#egg=cartesapp[dev]
```

## Creating new project

We recommend activating the virtual environment:

````shell
mdir NAME
cd NAME
python3 -m venv .venv
```

Then isntall cartesapp

```shell
pip install cartesapp@git+https://github.com/prototyp3-dev/python-cartesi@feature/node-v2[dev]
````

## Creating new module

First you'll need to create a module and

```shell
cartesapp create-module MODULE_NAME
```

Then edit the `MODULE_NAME/settings.py` to import the project files.

## Building

```shell
cartesapp build
```

## Running

You can run a cartesi rollups node on a local devnet with

```shell
cartesapp node
```

To run the node on a testnet

```shell
cartesapp run
```

Note: app should be already deployed onchain (feature tbi)

## Generating frontend libs

Run the following command to generate the libraries for the frontend (this will add them to frontend/src)

```shell
cartesapp generate-frontend-libs
```

You can also define the path to the libs

```shell
cartesapp generate-frontend-libs --libs-path path/to/libs
```

Then install frontend dependencies:

```shell
cd frontend
pnpm i
```

## Customize the root file system

You can install anything on the root file system. You'll run the cartesi machine in shell mode and you'll be able to install any dependencies;

```shell
cartesapp shell
```

## Test you project

You can test you project directly on the host with

```shell
cartesapp test
```

You can also test you project running inside cartesi machine:

```shell
cartesapp test --cartesi-machine
```

## Customize Drives and Machine configuring

Create a `cartesi.toml` file and add the desired configurations, e.g.:

```toml
# sdk = "ghcr.io/prototyp3-dev/cartesapp-sdk:latest"

# [machine]
# ram-length = "256Mi"
# assert-rolling-update = true
# entrypoint = "rollup-init cartesapp run --log-level=debug"
# bootargs = ["no4lvl", "quiet", "earlycon=sbi", "console=hvc0", "rootfstype=ext2", "root=/dev/pmem0", "rw", "init=/usr/sbin/cartesi-init"]
# assert-rolling-template = true
# final-hash = true
# max-mcycle = 0
# no-rollup = false
# ram-image = "/usr/share/cartesi-machine/images/linux.bin" # directory inside SDK image

# [drives.root] # it will search for it on the sdk
# builder = "none"
# filename = ".cartesi/root.ext2"

# [drives.root]
# builder = "docker"
# dockerfile = "Dockerfile"
# target = "docker-multi-stage-target"
# format = "ext2" #  "ext2" or "sqfs"
# extraSize = "100Mb" # optional. size is given by directory content size plus this amount

# [drives.data]
# builder = "empty"
# size = "100Mb" # size can be given as string, or as a number in bytes
# mount = "/var/lib/app" # default is /mnt/{name}

# [drives.data]
# builder = "directory"
# directory = "./data"
# format = "ext2" #  "ext2" or "sqfs"
# extraSize = "100Mb" # optional. size is given by directory content size plus this amount
# mount = "/var/lib/app" # optional, default is /mnt/{name}

# [drives.data]
# builder = "tar"
# filename = "build/files.tar"
# extraSize = "100Mb" # optional. size is given by directory content size plus this amount
# mount = "/var/lib/app" # optional, default is /mnt/{name}
```
