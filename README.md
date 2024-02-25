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

To be implemented

## Generating frontend libs

Run

```shell
cartesapp create-module NAME
```

Import cartesapp manager and add module

```python
from cartesapp.manager import Manager
m = Manager()
m.add_module('app')
```

To create (or merge) the frontend structure:

```python
m.create_frontend()
```

To (re)generate frontend libs based on backend (on a specific path, default is `src`):

```python
m.generate_frontend_lib("app/backend-libs")
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

Now you can use the generated libs on the frontend. Check examples in `./misc/dry-run.ts`
