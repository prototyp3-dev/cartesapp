# Cartesapp

## Requirements

- [venv](https://docs.python.org/3/library/venv.html), Python virtual environment
- [npm](https://docs.npmjs.com/cli/v9/configuring-npm/install) to install dependencies and run the frontend
- [Sunodo](https://github.com/sunodo/sunodo) to run the DApp backend
- [json-schema-to-typescript](https://www.npmjs.com/package/json-schema-to-typescript) to generate typescript interfaces`npm install -g json-schema-to-typescript --save`
- [cartesi-client](https://github.com/prototyp3-dev/cartesi-client/), an interface to cartesi rollups framework

## Installing

After you create a virtual environment and activate it you can install with

```shell
pip3 install git+https://github.com/prototyp3-dev/cartesapp@main
```

## Creating new project

```shell
cartesapp create NAME
cd NAME
make setup-env
```

or (without a previous cartesapp installation and using this [Makefile](https://github.com/prototyp3-dev/cartesapp/blob/main/cartesapp/Makefile))

```shell
mdir NAME
cd NAME
wget https://github.com/prototyp3-dev/cartesapp/blob/main/cartesapp/Makefile
make setup-env
```

We then recommend to activate the virtual environment so you can run the cartesapp commands directly

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

You can run a cartesapp app with

```shell
cartesapp run 
```

You can set the log level with

```shell
cartesapp run --log-level debug
```

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
yarn
```

Link cartesi client lib (in `./frontend`), redo this step every time you install or remeve a package:

```shell
npm link cartesi-client
```

## Running the backend in dev mode

First you should create the dev image

```shell
cartesapp build-dev-image
```

Then you can run the dev node

```shell
cartesapp node --mode dev
```

## Export Dockerfile

The cartesi machine Dockerfile is saved as a template, so if you want to customize it, you can export it with

```shell
cartesapp export-dockerfile
```
