import os
import logging
from typing import Optional, List, Annotated
import traceback
import typer

from .setting import SETTINGS_TEMPLATE
from .manager import Manager

LOGGER = logging.getLogger(__name__)

###
# AUX

SUNODO_LABEL_PREFIX = "io.sunodo"
CARTESI_LABEL_PREFIX = "io.cartesi.rollups"

UNITS = {"b": 1, "Kb": 2**10, "Mb": 2**20, "Gb": 2**30, "Tb": 2**40}

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
        if result.returncode > 0:
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
    basepath = kwargs.get('basepath') or ".cartesapp"
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
    image_path = f"{os.getcwd()}/{config['basepath']}/{config['imagebase']}"
    if os.path.exists(image_path):
        shutil.rmtree(image_path)
    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","container","run","--rm", 
            f"--volume={os.getcwd()}/{config['basepath']}:/mnt"]
    args.extend(su)
    args.append(f"sunodo/sdk:{config['sdkversion']}")
    #
    args.append("cartesi-machine")
    args.append("--rollup")
    args.append(f"--ram-length='{config['ramsize']}'")
    args.append(f"--store='/mnt/{config['imagebase']}'")
    args.append(f"--flash-drive='label:root,filename:/mnt/{config['imagebase']}.ext2'")
    args.append(f"--flash-drive='label:data,filename:/mnt/{config['flashdrivename']}.ext2'")
    args.append("--final-hash")
    # args.append("--assert-rolling-template") # either asser rolling template or max cycle = 0
    args.append("--max-mcycle=0")
    args.append("--")
    args.append("'cd /opt/cartesi/dapp;  PATH=/opt/venv/bin:/opt/cartesi/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin ROLLUP_HTTP_SERVER_URL=http://127.0.0.1:5004 rollup-init /opt/cartesi/dapp/entrypoint.sh'")
    # print(' '.join(args))
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
def generate_frontend_libs(modules: List[str], libs_path: Optional[str] = None):
    """
    Generate frontend libs for MODULES
    """
    try:
        m = Manager()
        for mod in modules:
            m.add_module(mod)
        m.generate_frontend_lib(libs_path)
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
def node(dev: Optional[bool] = True):
    """
    Run node on NETWORK
    """
    # doctor basic reqs (sunodo,nonodo)
    print("Not yet Implemented")
    exit(1)

@app.command()
def build(config: Annotated[List[str], typer.Argument(help="machine config in the [ key=value ] format")] = None):
    """
    Build cartesi machine with 0+ CONFIGs
    """
    config_dict = {}
    for c in config:
        k,v = c.split('=')
        config_dict[k] = v
    print("Building image...")
    imageid = build_image()

    print("Getting configs...")
    machine_config = get_machine_config(imageid, **config_dict)
    print(f"{machine_config=}")

    print("exporting image and generating file systems...")
    export_image(imageid, machine_config)
    create_extfs(machine_config)

    print(f"creating image")
    create_machine_image(machine_config)


if __name__ == '__main__':
    app()
    