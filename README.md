# Cartesapp

Cartesapp is a opinionated python library and tool for cartesi rollups apps. It uses several formats and for the inputs, outputs, enpoints routing, and storage.

One simple echo app would be:

```python
from pydantic import BaseModel
from cartesapp.output import emit_event
from cartesapp.input import mutation

class Payload(BaseModel):
    message: bytes

@mutation()
def echo_mutation(payload: Payload) -> bool:
    emit_event(payload.message)
    return True
```

One of the advantages of Cartesapp is that it can create frontend libraries to interact with your app, speeding up the development of a complete app.

```typescript
import { sepolia } from "viem/chains";
import { getWalletClient } from "@/lib/cartesapp/utils";
import { echoMutation } from "@/lib/echo/lib"; // auto-generated classes and functions
import * as ifaces from "@/lib/echo/ifaces.d"; // auto-generated interfaces

const applicationAddress = "0x73C04b5b77A28A43c948B1aa34EcAF1fE3e7890f";

async function sendTestInput() {
  const inputData: ifaces.Payload = {
    message; "Hello World!"
  };
  const client = await getWalletClient(sepolia);
  await echoMutation(inputData,{applicationAddress,client});
}
```

## Requirements

- [docker](https://docs.docker.com/) to execute the cartesapp sdk image that runs the cartesi rollups node and other tools.
- [npm](https://docs.npmjs.com/cli/v9/configuring-npm/install) to install dependencies and run the frontend.

## Installing

After you create a virtual environment and activate it you can install with:

```shell
pip3 install git+https://github.com/prototyp3-dev/cartesapp@feature/node-v2#egg=cartesapp[dev]
```

## Creating new project

We recommend activating the virtual environment:

```shell
mkdir NAME
cd NAME
python3 -m venv .venv
```

Then install cartesapp:

```shell
pip install cartesapp@git+https://github.com/prototyp3-dev/python-cartesi@feature/node-v2[dev]
```

If cartesapp is already installed you can create a project with:

```shell
cartesapp create NAME
cd NAME
```

## Creating new module

To create a module run:

```shell
cartesapp create-module MODULE_NAME
```

This will generate the example files `<app>/settings.py`, `<app>/<app>.py`, and `tests/<app>.py`. Check and edit these files.

## Building

Run this command to generate a snapshot of your app:

```shell
cartesapp build
```

This will generate the required snapshot to run the cartesi rollups node.

## Running

After building the snapshot, you can run a cartesi rollups node on a local devnet with:

```shell
cartesapp node
```

To run the node on a testnet

```shell
cartesapp node --config rpc-url=RPC_URL --config rpc-ws=RPC_WS
```

## Generating the Debug Frontend and Frontend Libs

Run the following command to generate a test frontend with the libs

```shell
cartesapp generate-frontend
```

This will generate the frontend at `./frontend` with custom cartesapp libs to interact with the backend. You can install and run with:

```shell
cd frontend
npm install
npm run dev
```

Run the following command to (re)generate the libraries for the frontend (this will add them to frontend/src)

```shell
cartesapp generate-frontend-libs
```

You can also define the path to the libs and enable the debug components files (App.tsx, Input.tsx, Inspect.tsx,...) of the debug frontend

```shell
cartesapp generate-frontend-libs --libs-path path/to/libs --generate-debug-components
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

# [node]
# APP_NAME = "myapp"
# consensus-address = "0x1d76...3FED"
# port = 8080
# dbport = 5432

# [node.envs]
# ROLLUP_HTTP_SERVER_URL = "http://127.0.0.1:5004"
```
