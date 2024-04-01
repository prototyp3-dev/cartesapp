import os
import logging
from typing import Optional, List, Annotated
import traceback
import typer
from enum import Enum

from .setting import SETTINGS_TEMPLATE
from .manager import Manager

LOGGER = logging.getLogger(__name__)

###
# AUX

class NodeMode(str, Enum):
    dev = "dev"
    reader = "reader"
    full = "full"
    sunodo = "sunodo"

SUNODO_LABEL_PREFIX = "io.sunodo"
CARTESI_LABEL_PREFIX = "io.cartesi.rollups"

UNITS = {"b": 1, "Kb": 2**10, "Mb": 2**20, "Gb": 2**30, "Tb": 2**40}

MACHINE_CONFIGFILE = ".machine_config.json"

def parse_size(size):
    import re
    m = re.compile('(\d+)\s*(\S+)').match(size)
    number = m.group(1)
    unit = m.group(2)
    return int(float(number)*UNITS[unit])

def build_image():
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(mode='w+') as idfile:
        args = ["docker","build","--iidfile",idfile.name,"."]
        result = subprocess.run(args)
        if result.returncode != 0:
            raise Exception(f"Error building image: {str(result.stderr)}")
        with open(idfile.name) as f:
            return f.read()

def get_image_info(imageid):
    import subprocess, json
    args = ["docker","image","inspect",imageid]
    result = subprocess.run(args,capture_output=True)
    if result.returncode > 0:
        raise Exception(f"Error getting image info: {str(result.stderr)}")
    return json.loads(result.stdout)

def export_image(imageid, config):
    import subprocess
    args = ["docker","container","create","--platform=linux/riscv64",imageid]
    result = subprocess.run(args,capture_output=True)
    if result.returncode > 0:
        raise Exception(f"Error creating container: {str(result.stderr)}")
    container_id = result.stdout.decode("utf-8").strip()
    args = ["docker","export",f"--output={config['basepath']}/{config['imagebase']}.tar",container_id]
    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error exporting container: {str(result.stderr)}")
    args = ["docker","rm",container_id]
    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error removing container: {str(result.stderr)}")

def save_machine_config(config):
    import json
    with open(MACHINE_CONFIGFILE,'w') as f: f.write(json.dumps(config))

def get_machine_config(imageid, **kwargs):
    image_info_json = get_image_info(imageid)
    sdkversion = image_info_json[0]['Config']['Labels'].get(f"{SUNODO_LABEL_PREFIX}.sdk_version")
    ramsize = image_info_json[0]['Config']['Labels'].get(f"{CARTESI_LABEL_PREFIX}.ram_size")
    if ramsize is None: ramsize = '128Mi'
    ramsize = kwargs.get('ramsize') or ramsize
    datasize = image_info_json[0]['Config']['Labels'].get(f"{CARTESI_LABEL_PREFIX}.data_size")
    if datasize is None: datasize = '10Mb'
    datasize = kwargs.get('datasize') or datasize
    #
    basepath = kwargs.get('basepath') or ".sunodo"
    imagezero = kwargs.get('imagezero') or "image_0"
    imagebase = kwargs.get('imagebase') or "image"
    #
    flashdrivename = kwargs.get('flashdrivename') or 'data'
    flashdrivesize = kwargs.get('flashdrivesize') or '128Mb'
    #
    blocksize = kwargs.get('blocksize') or 4096
    return {
        "sdkversion": sdkversion,
        "ramsize": ramsize,
        "datasize": datasize,
        "basepath": basepath,
        "imagezero": imagezero,
        "imagebase": imagebase,
        "flashdrivename": flashdrivename,
        "blocksize": blocksize,
        "flashdrivesize": flashdrivesize
    }


def create_extfs(config):
    import subprocess
    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","container","run","--rm", 
            f"--volume={os.getcwd()}/{config['basepath']}:/mnt"]
    args.extend(su)
    args.append(f"sunodo/sdk:{config['sdkversion']}")
    args1 = args.copy()
    args1.extend(["retar",f"/mnt/{config['imagebase']}.tar"])
    result = subprocess.run(args1)
    if result.returncode > 0:
        raise Exception(f"Error doing retar: {str(result.stderr)}")
    #
    #
    extra_size = parse_size(config['datasize'])//config['blocksize']
    args2 = args.copy()
    args2.extend(["genext2fs","--tarball",f"/mnt/{config['imagebase']}.tar",
                  "--block-size",str(config['blocksize']),"--faketime",
                  "--readjustment",f"+{extra_size}",f"/mnt/{config['imagebase']}.ext2"])
    result = subprocess.run(args2)
    if result.returncode > 0:
        raise Exception(f"Error generating ext2 fs: {str(result.stderr)}")
    os.remove(f"{config['basepath']}/{config['imagebase']}.tar")
    #
    #
    flashdrive_bsize = parse_size(config['flashdrivesize'])//config['blocksize']
    args3 = args.copy()
    args3.extend(["genext2fs","--faketime","--size-in-blocks", str(flashdrive_bsize),
                  "--block-size",str(config['blocksize']),f"/mnt/{config['flashdrivename']}.ext2"])
    result = subprocess.run(args3)
    if result.returncode > 0:
        raise Exception(f"Error generating flashdrive ext2 fs: {str(result.stderr)}")
    

def create_machine_image(config):
    import subprocess, shutil
    image0_path = f"{os.getcwd()}/{config['basepath']}/{config['imagezero']}"
    if os.path.exists(image0_path):
        shutil.rmtree(image0_path)
    image_path = f"{os.getcwd()}/{config['basepath']}/{config['imagebase']}"
    if os.path.exists(image_path):
        shutil.rmtree(image_path)
    
    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","container","run","--rm", 
            f"--volume={os.getcwd()}/{config['basepath']}:/mnt"]
    args.extend(su)
    args.append(f"sunodo/sdk:{config['sdkversion']}")
    #
    args1 = args.copy()
    args1.append("cartesi-machine")
    args1.append("--rollup")
    args1.append(f"--ram-length='{config['ramsize']}'")
    args1.append(f"--store='/mnt/{config['imagezero']}'")
    args1.append(f"--flash-drive='label:root,filename:/mnt/{config['imagebase']}.ext2'")
    args1.append(f"--flash-drive='label:data,filename:/mnt/{config['flashdrivename']}.ext2'")
    args1.append("--final-hash")
    # args1.append("--assert-rolling-template") # either asser rolling template or max cycle = 0
    args1.append("--max-mcycle=0")
    args1.append("--")
    args1.append("'cd /opt/cartesi/dapp;  PATH=/opt/venv/bin:/opt/cartesi/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin ROLLUP_HTTP_SERVER_URL=http://127.0.0.1:5004 rollup-init /opt/cartesi/dapp/entrypoint.sh'")
    # print(' '.join(args1))
    result = subprocess.run(' '.join(args1), shell=True)
    if result.returncode > 0:
        raise Exception(f"Error generating flashdrive ext2 fs: {str(result.stderr)}")
    #
    args2 = args.copy()
    args2.append("cartesi-machine")
    args2.append(f"--load='{config['imagezero']}'")
    args2.append(f"--store='/mnt/{config['imagebase']}'")
    args2.append("--rollup")
    args2.append("--assert-rolling-template")
    # print(' '.join(args2))
    result = subprocess.run(' '.join(args2), shell=True)
    if result.returncode > 0:
        raise Exception(f"Error generating flashdrive ext2 fs: {str(result.stderr)}")
    

def get_old_machine_config():
    import json
    if not os.path.exists(MACHINE_CONFIGFILE):
        raise Exception(f"Couldn't find machine config file")
    with open(MACHINE_CONFIGFILE,'r') as f: 
        return json.loads(f.read())

def get_reader_node_image_name():
    project_name = os.path.basename(os.getcwd())
    return f"{project_name}-reader-node"

def build_reader_docker_image(**kwargs):
    import subprocess, tempfile
    reader_image_name = get_reader_node_image_name()
    config = get_old_machine_config()

    template = f'''
# syntax=docker.io/docker/dockerfile:1.4
FROM sunodo/sdk:{config['sdkversion']}

WORKDIR /opt/cartesi/reader
RUN chmod 777 .

ARG CM_CALLER_VERSION=0.0.1
ARG NONODO_VERSION=0.0.1

COPY --from=ghcr.io/foundry-rs/foundry:latest /usr/local/bin/anvil /usr/local/bin/anvil

RUN curl -s -L https://github.com/lynoferraz/nonodo/releases/download/v${{NONODO_VERSION}}/nonodo-v${{NONODO_VERSION}}-linux-$(dpkg --print-architecture).tar.gz | \
    tar xzf - -C /usr/local/bin nonodo

RUN curl -s -L https://github.com/lynoferraz/cm-caller/releases/download/v${{CM_CALLER_VERSION}}/cm-caller-v${{CM_CALLER_VERSION}}-linux-$(dpkg --print-architecture).tar.gz | \
    tar xzf - -C /usr/local/bin cm-caller

EXPOSE 8080
EXPOSE 8545
'''

    args = ["docker","build","-t",reader_image_name]
    if kwargs.get('CM_CALLER_VERSION') is not None:
        args.extend(["--build-arg",f"CM_CALLER_VERSION={kwargs.get('CM_CALLER_VERSION')}"])
    if kwargs.get('NONODO_VERSION') is not None:
        args.extend(["--build-arg",f"NONODO_VERSION={kwargs.get('NONODO_VERSION')}"])

    args.extend(["--progress","plain"])
    args.append("-")
    p = subprocess.Popen(args, stdin=subprocess.PIPE)
    p.communicate(input=template.encode())
    if p.returncode > 0:
        raise Exception(f"Error building reader node image: {str(p.stderr)}")

def run_full_node(**kwargs):
    import subprocess

    args = ["sunodo","run"]
    for k,v in kwargs:
        args.append(f"--{k}={v}")

    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error generating flashdrive ext2 fs: {str(result.stderr)}")

def run_dev_node(**kwargs):
    import subprocess
    print("DEV node is still WIP")
    print("  currently it only runs the rollups node without the backend")
    print("  (you can start the backend with 'cartesapp run ...')")
    config = get_old_machine_config()
    reader_image_name = get_reader_node_image_name()

    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","run","--rm",
            f"--volume={os.getcwd()}/{config['basepath']}:/mnt"]
    args.extend(su)
    if kwargs.get('port') is not None:
        args.extend(["-p",f"{kwargs.get('port')}:8080"])
    else:
        args.extend(["-p",f"8080:8080"])
    if kwargs.get('anvil-port') is not None:
        args.extend(["-p",f"{kwargs.get('anvil-port')}:8545"])
    else:
        args.extend(["-p",f"8545:8545"])
    args.append(reader_image_name)
    nonodo_args = ["nonodo","--http-address=0.0.0.0","--anvil-address=0.0.0.0"]

    args.extend(nonodo_args)
    print(' '.join(args))
    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error generating flashdrive ext2 fs: {str(result.stderr)}")

def run_reader_node(**kwargs):
    import subprocess
    config = get_old_machine_config()
    reader_image_name = get_reader_node_image_name()

    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","run","--rm",
            f"--volume={os.getcwd()}/{config['basepath']}:/mnt"]
    args.extend(su)
    if kwargs.get('port') is not None:
        args.extend(["-p",f"{kwargs.get('port')}:8080"])
    else:
        args.extend(["-p",f"8080:8080"])
    if kwargs.get('anvil-port') is not None:
        args.extend(["-p",f"{kwargs.get('anvil-port')}:8545"])
    else:
        args.extend(["-p",f"8545:8545"])
    args.append(reader_image_name)
    nonodo_args = ["nonodo","--http-address=0.0.0.0","--anvil-address=0.0.0.0"]
    cm_caller_args = ["cm-caller","--store-path=/mnt/reader","--flash-data=/mnt/reader/data.ext2"]

    if kwargs.get('image') is not None:
        cm_caller_args.append(f"--image=/mnt/{kwargs.get('image')}")
    else:
        cm_caller_args.append("--image=/mnt/image_0")
    if kwargs.get('disable-advance') is not None:
        nonodo_args.append("--disable-advance")
        cm_caller_args.append("--disable-advance")
    if kwargs.get('disable-inspect') is not None:
        cm_caller_args.append("--disable-inspect")
    if kwargs.get('reset') is not None:
        if os.path.exists(f"{config['basepath']}/reader/data.ext2"):
            os.remove(f"{config['basepath']}/reader/data.ext2")
        cm_caller_args.append("--reset-latest")
    args.extend(nonodo_args)
    args.append("--")
    args.extend(cm_caller_args)
    print(' '.join(args))
    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error generating flashdrive ext2 fs: {str(result.stderr)}")

###
# CLI

app = typer.Typer(help="Cartesapp Manager: manage your Cartesi Rollups App")

def create_cartesapp_module(module_name: str):
    if not os.path.exists(module_name):
        os.makedirs(module_name)
    open(f"{module_name}/__init__.py", 'a').close()
    if not os.path.exists(f"{module_name}/settings.py"):
        with open(f"{module_name}/settings.py", 'w') as f:
            f.write(SETTINGS_TEMPLATE)


@app.command()
def run(modules: List[str],log_level: Optional[str] = None):
    """
    Run backend with MODULES
    """
    try:
        if log_level is not None:
            logging.basicConfig(level=getattr(logging,log_level.upper()))
        m = Manager()
        for mod in modules:
            m.add_module(mod)
        m.setup_manager()
        m.run()
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

@app.command()
def generate_frontend_libs(modules: List[str], libs_path: Optional[str] = None, frontend_path: Optional[str] = None):
    """
    Generate frontend libs for MODULES
    """
    try:
        m = Manager()
        for mod in modules:
            m.add_module(mod)
        m.generate_frontend_lib(libs_path,frontend_path)
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

@app.command()
def create_frontend(force: Optional[bool]):
    """
    Create basic frontend
    """
    # check if it exists, bypass with force
    # create frontend web
    # doctor basic reqs (node)
    # install packages ["ajv": "^8.12.0","ethers": "^5.7.2","ts-transformer-keys": "^0.4.4"]
    print("Not yet Implemented")
    exit(1)

@app.command()
def create(name: str, modules: Optional[List[str]] = None):
    """
    Create new Cartesi Rollups App with NAME, and modules MODULES
    """
    # TODO: create basic structure of project: Dockerfile, modules
    print("Not yet Implemented")
    exit(1)

@app.command()
def create_module(name: str):
    """
    Create new MODULE for current Cartesi Rollups App
    """
    print(f"Creating module {name}")
    create_cartesapp_module(name)

@app.command()
def deploy(conf: str):
    """
    Deploy App with CONF file
    """
    # doctor basic reqs (sunodo)
    print("Not yet Implemented")
    exit(1)

@app.command()
def node(mode: NodeMode = NodeMode.full, config: Annotated[List[str], typer.Argument(help="configs in the [ key=value ] format")] = None):
    """
    Run node MODE
    """
    config_dict = {}
    print(mode,config)
    if config is not None:
        for c in config:
            k,v = c.split('=')
            config_dict[k] = v
    # doctor basic reqs (sunodo,nonodo)
    # either run basic sunodo, or nonodo (dev), or reader
    # sunodo or reader must check if it was build
    # allow to configure
    if mode == NodeMode.sunodo or mode == NodeMode.full:
        run_full_node(**config_dict)
    elif mode == NodeMode.dev:
        run_dev_node(**config_dict)
    elif mode == NodeMode.reader:
        run_reader_node(**config_dict)
    else:
        print("Invalid option")
        exit(1)


@app.command()
def build(config: Annotated[List[str], typer.Argument(help="machine config in the [ key=value ] format")] = None):
    """
    Build cartesi machine with 0+ CONFIGs
    """
    config_dict = {}
    if config is not None:
        for c in config:
            k,v = c.split('=')
            config_dict[k] = v
    print("Building image...")
    imageid = build_image()

    print("Getting configs...")
    machine_config = get_machine_config(imageid, **config_dict)
    print(f"{machine_config=}")
    save_machine_config(machine_config)

    print("exporting image and generating file systems...")
    export_image(imageid, machine_config)
    create_extfs(machine_config)

    print(f"creating image")
    create_machine_image(machine_config)

@app.command()
def build_reader_image(config: Annotated[List[str], typer.Argument(help="args config in the [ key=value ] format")] = None):
    """
    Build reader docker image
    """
    config_dict = {}
    if config is not None:
        for c in config:
            k,v = c.split('=')
            config_dict[k] = v
    build_reader_docker_image(**config_dict)

if __name__ == '__main__':
    app()
    