import os
import subprocess
from typing import List
from shutil import which

import logging

LOGGER = logging.getLogger(__name__)

DOCKER_CMD = ["docker","run","--rm"]
SDK_IMAGE = "ghcr.io/prototyp3-dev/cartesapp/sdk:0.0.1"

def is_tool(name):
    return which(name) is not None

def run_cmd(args: List[str], datadir: str | None = None, **kwargs) -> subprocess.CompletedProcess[str]:
    if is_tool(args[0]):
        LOGGER.debug(f"Running: {' '.join(args)}")
        return subprocess.run(args,**kwargs)
    LOGGER.debug(f"Command {args[0]} not found. Falling back to use docker")
    if not is_tool(DOCKER_CMD[0]):
        msg = "Could find tool or docker to run command"
        LOGGER.error(msg)
        raise Exception(msg)
    docker_args = DOCKER_CMD.copy()
    docker_args.extend(["-v",f"{os.getcwd()}:{os.getcwd()}","-w",os.getcwd()])
    if datadir is not None:
        docker_args.extend(["-v",f"{datadir}:{datadir}"])
    docker_args.append(SDK_IMAGE)
    docker_args.extend(args)
    LOGGER.debug(f"Running: {' '.join(docker_args)}")
    return subprocess.run(docker_args,**kwargs)
