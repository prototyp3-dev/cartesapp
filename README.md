# Cartesapp

## Requirements

- [npm](https://docs.npmjs.com/cli/v9/configuring-npm/install) to install dependencies and run the frontend
- [Sunodo](https://github.com/sunodo/sunodo) to build and run the DApp backend
- [json-schema-to-typescript](https://www.npmjs.com/package/json-schema-to-typescript) to generate typescript interfaces`npm install -g json-schema-to-typescript --save`
- [cartesi-client](https://github.com/prototyp3-dev/cartesi-client/), an interface to cartesi rollups framework

## Installing

After you create a virtual environment and activate it you can install with

```shell
pip3 install git+https://github.com/prototyp3-dev/cartesapp@main
```

## Creating new project

To be implemented

## Creating new module

Run

```shell
cartesapp create-module NAME
```

## Building

To be implemented

## Running

You can run a cartesapp app with

```shell
cartesapp run MODULES 
```

So you should add this as entrypoint to the Cartesi Rollups Dockerfile 

You can set the log level with

```shell
cartesapp run MODULES --log-level debug
```

## Generating frontend libs

Run the following command to generate the libraries for the frontend (this will add them to frontend/src)

```shell
cartesapp generate-frontend-libs MODULES
```

You can also define the path to the libs

```shell
cartesapp generate-frontend-libs MODULES --libs-path path/to/libs
```

Then install frontend dependencies:

```shell
cd frontend
yarn
```

Link cartesi client lib (in `./frontend`), redo this step every time you install or remeve a package:

```shell
npm link cartesi-client
```

## Running the examples (with nonodo)

Follow the instructions to install [nonodo](https://github.com/gligneul/nonodo). Then go to one of the examples (e.g. echo-app) and start it

```shell
nonodo
```

Then, in an another terminal create the virtual environment:

```shell
cd examples/echo-app
python3 -m venv .venv
. .venv/bin/activate
pip install -e ../..
```

Finally start the application

```shell
ROLLUP_HTTP_SERVER_URL=http://localhost:8080/rollup cartesapp run echo --log-level debug
```

