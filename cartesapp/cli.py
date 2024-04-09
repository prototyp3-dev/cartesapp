import os
import logging
from typing import Optional, List, Annotated
import traceback
import typer
from enum import Enum
from multiprocessing import Process
from watchdog.events import PatternMatchingEventHandler

from .setting import SETTINGS_TEMPLATE
from .manager import Manager
from .templates import reader_image_template, dev_image_template, cm_image_template, makefile_template

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
MINIMUM_SDK_VERSION = '0.4.0'

UNITS = {"b": 1, "Kb": 2**10, "Mb": 2**20, "Gb": 2**30, "Tb": 2**40}

MACHINE_CONFIGFILE = ".machine_config.json"

ACCEPTED_ENVS = ['PATH','ROLLUP_HTTP_SERVER_URL','PYTHONPATH']

DOCKERFILENAME = "Dockerfile"
MAKEFILENAME = "Makefile"

class ReloadCartesappEventHandler(PatternMatchingEventHandler):
    reload_event = None
    def __init__(self, reload_event):
        super().__init__(patterns=['*.py'])
        self.reload_event = reload_event
    def on_modified(self, event):
        self.reload_event.set()
    def on_deleted(self, event):
        self.reload_event.set()
    def on_moved(self, event):
        self.reload_event.set()

class CartesappProcess(Process):
    reload_event = None
    cartesapp_proc = None
    delay_restart_time = None
    modules = []
    def __init__(self, reload_event, modules, delay_restart_time=10):
        super().__init__()
        self.delay_restart_time = delay_restart_time
        self.reload_event = reload_event
        self.modules = modules
    def run(self):
        import time
        self.cartesapp_proc = Process(target=cartesapp_run,args=(self.modules,True))
        self.cartesapp_proc.start()
        while True:
            time.sleep(1)
            if self.reload_event.is_set():
                while self.reload_event.is_set():
                    self.reload_event.clear()
                    time.sleep(self.delay_restart_time)
                self.cartesapp_proc.terminate()
                self.reload_event.clear()
                self.cartesapp_proc = Process(target=cartesapp_run,args=(self.modules,False))
                self.cartesapp_proc.start()
    def terminate_proc(self):
        if self.cartesapp_proc is not None and \
                self.cartesapp_proc.exitcode is None:
            self.cartesapp_proc.terminate()

def get_modules():
    import subprocess, re
    result = subprocess.run(["find",".","-maxdepth","2","-type","f","-name","*.py","-not","-path","./tests/*"],capture_output=True)
    if result.returncode > 0:
        pass

    files = result.stdout.decode('utf-8').strip().split('\n')
    return list(set(map(lambda f: re.sub('/.+$|^./','',f),files)))

def cartesapp_run(modules=[],reset_storage=False):
    run_params = {}
    run_params['reset_storage'] = reset_storage
    m = Manager()
    for mod in modules:
        m.add_module(mod)
    m.setup_manager(**run_params)
    m.run()

def parse_size(size):
    import re
    m = re.compile('(\d+)\s*(\S+)').match(size)
    number = m.group(1)
    unit = m.group(2)
    return int(float(number)*UNITS[unit])

def create_project(name,force=False,**kwargs):
    from jinja2 import Template

    if os.path.exists(name) and os.path.isdir(name):
        if not force:
            raise Exception(f"There is already a {name} directory")
    else:
        os.makedirs(name)

    template = Template(makefile_template).render({
    })

    with open(f"{name}/{MAKEFILENAME}",'w') as f:
        f.write(template)

def export_cm_dockerfile(force=False,**kwargs):
    from jinja2 import Template

    if not force and os.path.exists(DOCKERFILENAME):
        raise Exception(f"There is already a {DOCKERFILENAME} file")

    modules = get_modules()
    if modules is None or len(modules) == 0:
        raise Exception("No modules detected")

    template = Template(cm_image_template).render({
        "modules": modules,
        "config": kwargs
    })

    with open(DOCKERFILENAME,'w') as f:
        f.write(template)

def build_image(**kwargs):
    import subprocess, tempfile, re
    from jinja2 import Template
    with tempfile.NamedTemporaryFile(mode='w+') as idfile:
        args = ["docker","build","--iidfile",idfile.name,"."]
        if kwargs.get('build-args') is not None:
            for env_pair in kwargs.get('build-args').split(','):
                m = re.match('^\w*=.*',env_pair)
                if m is not None:
                    args.extend(["--build-arg",env_pair])
        
        if not os.path.exists(DOCKERFILENAME):
            modules = get_modules()
            if modules is None or len(modules) == 0:
                raise Exception("No modules detected")
            
            template = Template(cm_image_template).render({
                "modules": modules,
                "config": kwargs
            })

            with tempfile.NamedTemporaryFile(mode='w+') as dockerfile:
                dockerfile.write(template)
                dockerfile.flush()
                args.extend(["--file",dockerfile.name])

                result = subprocess.run(args)
            
        else:
            result = subprocess.run(args)

        if result.returncode != 0:
            raise Exception(f"Error building image: {str(result.stderr)}")
        with open(idfile.name) as f:
            return f.read()

def get_image_info(image):
    import subprocess, json
    args = ["docker","image","inspect",image]
    result = subprocess.run(args,capture_output=True)
    if result.returncode > 0:
        return None # raise Exception(f"Error getting image info: {str(result.stderr)}")
    return json.loads(result.stdout)

def export_image(imageid, config):
    import subprocess
    args = ["docker","container","create","--platform=linux/riscv64",imageid]
    result = subprocess.run(args,capture_output=True)
    if result.returncode > 0:
        raise Exception(f"Error creating container: {str(result.stderr)}")
    container_id = result.stdout.decode("utf-8").strip()
    if not os.path.exists(config['basepath']):
        os.makedirs(config['basepath'])
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
    import re
    from packaging.version import Version
    image_info_json = get_image_info(imageid)
    if image_info_json is None:
        raise Exception(f"Error getting image info")
    if image_info_json[0]['Architecture'] != 'riscv64':
        raise Exception(f"Invalid image Architecture: {image_info_json[0]['Architecture']}. Expected riscv64")
    sdkversion = image_info_json[0]['Config']['Labels'].get(f"{SUNODO_LABEL_PREFIX}.sdk_version")
    match_base_version = re.match('.*(\d+\.\d+\.\d+).*',sdkversion)
    if match_base_version is not None and Version(match_base_version[1]) < Version(MINIMUM_SDK_VERSION):
        raise Exception(f"Minimum required sdk version is {MINIMUM_SDK_VERSION}")
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
    flashdrivesize = image_info_json[0]['Config']['Labels'].get(f"{CARTESI_LABEL_PREFIX}.flashdrive_size") or '64Mb'
    flashdrivesize = kwargs.get('flashdrivesize') or flashdrivesize
    #
    blocksize = kwargs.get('blocksize') or 4096
    #
    workdir = image_info_json[0]['Config'].get('WorkingDir')
    #
    ep = image_info_json[0]['Config'].get('Entrypoint') or []
    cmd = image_info_json[0]['Config'].get('Cmd') or []
    entrypoint = ' '.join(ep + cmd)
    #
    env_list = image_info_json[0]['Config'].get('Env')
    envs = []
    if env_list is not None:
        for env_pair in env_list:
            m = re.match('^(\w*)=',env_pair)
            if m is not None and m.group(1) in ACCEPTED_ENVS:
                envs.append(env_pair)
    if kwargs.get('envs') is not None:
        for env_pair in kwargs.get('envs').split(','):
            m = re.match('^\w*=.*',env_pair)
            if m is not None:
                envs.append(env_pair)
    
    return {
        "sdkversion": sdkversion,
        "ramsize": ramsize,
        "datasize": datasize,
        "basepath": basepath,
        "imagezero": imagezero,
        "imagebase": imagebase,
        "flashdrivename": flashdrivename,
        "blocksize": blocksize,
        "flashdrivesize": flashdrivesize,
        "envs":envs,
        "entrypoint":entrypoint,
        "workdir":workdir
    }


def create_extfs(config):
    import subprocess
    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","container","run","--rm", 
            f"--volume={os.getcwd()}/{config['basepath']}:/mnt"]
    args.extend(su)
    args.append(f"sunodo/sdk:{config['sdkversion']}")
    args1 = args.copy()
    # args1.extend(["retar",f"/mnt/{config['imagebase']}.tar"])
    args1.extend(["bsdtar","-cf",f"/mnt/{config['imagebase']}-retar.tar","--format=gnutar",f"@/mnt/{config['imagebase']}.tar"])
    result = subprocess.run(args1,capture_output=True)
    if result.returncode > 0:
        raise Exception(f"Error doing retar: {str(result.stderr)}")
    #
    #
    extra_size = parse_size(config['datasize'])//config['blocksize']
    args2 = args.copy()
    args2.extend(["xgenext2fs","--tarball",f"/mnt/{config['imagebase']}-retar.tar",
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
    args3.extend(["xgenext2fs","--faketime","--size-in-blocks", str(flashdrive_bsize),
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
    args1.append(f"--ram-length='{config['ramsize']}'")
    args1.append(f"--store='/mnt/{config['imagezero']}'")
    args1.append(f"--flash-drive='label:root,filename:/mnt/{config['imagebase']}.ext2'")
    # args1.append(f"--flash-drive='label:data,filename:/mnt/{config['flashdrivename']}.ext2'")
    args1.append("--final-hash")
    args1.append("--max-mcycle=0")
    if config.get('workdir') is not None:
        args1.append(f"--append-init=WORKDIR={config.get('workdir')}")
    if config.get('envs') is not None:
        for env_pair in config.get('envs'):
            args1.append(f"--append-init='export {env_pair}'")
    args1.append("--")
    args1.append(f"'{config['entrypoint']}'")
    # args1.append("--")
    # args1.append(f"'cd {config['workdir']};  {' '.join(config['envs'])} {config['entrypoint']}'")
    print(' '.join(args1))
    result = subprocess.run(' '.join(args1), shell=True)
    if result.returncode > 0:
        raise Exception(f"Error creating cartesi machine image 0: {str(result.stderr)}")
    #
    args2 = args.copy()
    args2.append("cartesi-machine")
    args2.append(f"--load='{config['imagezero']}'")
    args2.append(f"--store='/mnt/{config['imagebase']}'")
    args1.append("--final-hash")
    args2.append("--assert-rolling-template")
    # print(' '.join(args2))
    result = subprocess.run(' '.join(args2), shell=True)
    if result.returncode > 0:
        raise Exception(f"Error creating cartesi machine: {str(result.stderr)}")
    

def get_old_machine_config():
    import json
    if not os.path.exists(MACHINE_CONFIGFILE):
        raise Exception(f"Couldn't find machine config file, please build the image first")
    with open(MACHINE_CONFIGFILE,'r') as f: 
        return json.loads(f.read())

def get_reader_node_image_name():
    project_name = os.path.basename(os.getcwd())
    return f"{project_name}-reader-node"

def get_dev_node_image_name():
    project_name = os.path.basename(os.getcwd())
    return f"{project_name}-dev-node"

def build_dev_docker_image(**kwargs):
    import subprocess
    from jinja2 import Template
    reader_image_name = get_dev_node_image_name()

    template = Template(dev_image_template).render()

    args = ["docker","build","-t",reader_image_name]
    if kwargs.get('NONODO_VERSION') is not None:
        args.extend(["--build-arg",f"NONODO_VERSION={kwargs.get('NONODO_VERSION')}"])

    args.append("-")
    p = subprocess.Popen(args, stdin=subprocess.PIPE)
    p.communicate(input=template.encode())
    if p.returncode > 0:
        raise Exception(f"Error building dev node image: {str(p.stderr)}")

def build_reader_docker_image(**kwargs):
    import subprocess
    from jinja2 import Template
    reader_image_name = get_reader_node_image_name()
    config = get_old_machine_config()

    template = Template(reader_image_template).render({"config":config})

    args = ["docker","build","-t",reader_image_name]
    if kwargs.get('CM_CALLER_VERSION') is not None:
        args.extend(["--build-arg",f"CM_CALLER_VERSION={kwargs.get('CM_CALLER_VERSION')}"])
    if kwargs.get('NONODO_VERSION') is not None:
        args.extend(["--build-arg",f"NONODO_VERSION={kwargs.get('NONODO_VERSION')}"])

    args.append("-")
    p = subprocess.Popen(args, stdin=subprocess.PIPE)
    p.communicate(input=template.encode())
    if p.returncode > 0:
        raise Exception(f"Error building reader node image: {str(p.stderr)}")

def run_full_node(**kwargs):
    import subprocess

    args0 = ["sunodo","doctor"]
    result = subprocess.run(args0)
    if result.returncode > 0:
        raise Exception(f"Error running doctor: {str(result.stderr)}")

    config = get_old_machine_config()
    image_path = f"{os.getcwd()}/{config['basepath']}/{config['imagebase']}"
    if not os.path.exists(image_path):
        raise Exception(f"Couldn't find image, please build it first")
    
    args = ["sunodo","run"]
    for k,v in kwargs:
        args.append(f"--{k}={v}")

    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error running full node: {str(result.stderr)}")

def run_dev_node(**kwargs):
    import subprocess, time
    from multiprocessing import Event
    from watchdog.observers import Observer
    if kwargs.get('modules') is None:
        print("please define modules")
        return

    dev_image_name = get_dev_node_image_name()
    image_info_json = get_image_info(dev_image_name)
    if image_info_json is None:
        raise Exception(f"Could get docker image {dev_image_name}. Make sure to build it first with [cartesapp build-dev-image]")
    
    su = ["--env",f"USER={os.getlogin()}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    args = ["docker","run","--rm"]
    args.extend(su)
    if kwargs.get('port') is not None:
        args.extend(["-p",f"{kwargs.get('port')}:8080"])
    else:
        args.extend(["-p",f"8080:8080"])
    if kwargs.get('anvil-port') is not None:
        args.extend(["-p",f"{kwargs.get('anvil-port')}:8545"])
    else:
        args.extend(["-p",f"8545:8545"])
    args.append(dev_image_name)
    nonodo_args = ["nonodo","--http-address=0.0.0.0","--anvil-address=0.0.0.0"]

    args.extend(nonodo_args)
    
    # result = subprocess.run(args)
    # if result.returncode > 0:
    #     raise Exception(f"Error running dev node: {str(result.stderr)}")

    path = '.'

    observer = Observer()
    reload_event = Event()

    cs = CartesappProcess(reload_event,kwargs['modules'],3)
    event_handler = ReloadCartesappEventHandler(reload_event)

    observer.schedule(event_handler, path, recursive=True)

    logging.getLogger("watchdog").setLevel(logging.WARNING)

    try:
        observer.start()
        node = subprocess.Popen(args)
        time.sleep(1)
        cs.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        cs.terminate_proc()
        node.terminate()
    finally:
        node.wait()
        observer.join()


def run_reader_node(**kwargs):
    import subprocess
    config = get_old_machine_config()
    image_path = f"{os.getcwd()}/{config['basepath']}/{config['imagebase']}"
    if not os.path.exists(image_path):
        raise Exception(f"Couldn't find image, please build it first")

    reader_image_name = get_reader_node_image_name()
    image_info_json = get_image_info(reader_image_name)
    if image_info_json is None:
        raise Exception(f"Could get docker image {reader_image_name}. Make sure to build it first with [cartesapp build-reader-image]")

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
    if kwargs.get('rpc-url') is not None:
        nonodo_args.append(f"--rpc-url{kwargs.get('rpc-url')}")
    if kwargs.get('disable-inspect') is not None:
        cm_caller_args.append("--disable-inspect")
    if kwargs.get('reset') is not None:
        if os.path.exists(f"{config['basepath']}/reader/data.ext2"):
            os.remove(f"{config['basepath']}/reader/data.ext2")
        cm_caller_args.append("--reset-latest")
    args.extend(nonodo_args)
    args.append("--")
    args.extend(cm_caller_args)
    result = subprocess.run(args)
    if result.returncode > 0:
        raise Exception(f"Error running reader node: {str(result.stderr)}")

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
def run(log_level: Optional[str] = None,reset_storage: Optional[bool] = False):
    try:
        if log_level is not None:
            logging.basicConfig(level=getattr(logging,log_level.upper()))
        run_params = {}
        run_params['reset_storage'] = reset_storage
        run_params['modules'] = get_modules()
        cartesapp_run(**run_params)
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

@app.command()
def generate_frontend_libs(libs_path: Optional[str] = None, frontend_path: Optional[str] = None):
    try:
        m = Manager()
        for mod in get_modules():
            m.add_module(mod)
        m.generate_frontend_lib(libs_path,frontend_path)
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

@app.command()
def create_frontend(libs_path: Optional[str] = None, frontend_path: Optional[str] = None):
    """
    Create basic frontend structure
    """
    # check if it exists, bypass with force
    # create frontend web
    # doctor basic reqs (node)
    # install packages ["ajv": "^8.12.0","ethers": "^5.7.2","ts-transformer-keys": "^0.4.4"]
    print("Note: not fully implemented yet")
    m = Manager()
    m.create_frontend(libs_path,frontend_path)
    exit(1)

@app.command()
def create(name: str,config: Annotated[List[str], typer.Option(help="args config in the [ key=value ] format")] = None, force: Optional[bool] = False):
    """
    Create new Cartesi Rollups App with NAME
    """
    config_dict = {}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    create_project(name,force,**config_dict)
    print(f"{name} created!")
    print(f"  You should now run 'cd {name} && make setup-env' to setup the environment")
    print(f"  Then '. .venv/bin/activate' to activate it")

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
def node(mode: NodeMode = NodeMode.full, config: Annotated[List[str], typer.Option(help="config in the [ key=value ] format")] = None):
    config_dict = {}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v

    if mode == NodeMode.sunodo or mode == NodeMode.full:
        run_full_node(**config_dict)
    elif mode == NodeMode.dev:
        logging.basicConfig(level=logging.DEBUG)
        config_dict['modules'] = get_modules()
        run_dev_node(**config_dict)
    elif mode == NodeMode.reader:
        run_reader_node(**config_dict)
    else:
        print("Invalid option")
        exit(1)

@app.command()
def build(config: Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")] = None):
    config_dict = {}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    print("Building image...")
    imageid = build_image(**config_dict)

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
def build_reader_image(config: Annotated[List[str], typer.Option(help="args config in the [ key=value ] format")] = None):
    config_dict = {}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    build_reader_docker_image(**config_dict)

@app.command()
def build_dev_image(config: Annotated[List[str], typer.Option(help="args config in the [ key=value ] format")] = None):
    config_dict = {}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    build_dev_docker_image(**config_dict)

@app.command()
def export_dockerfile(config: Annotated[List[str], typer.Option(help="args config in the [ key=value ] format")] = None, force: Optional[bool] = False):
    config_dict = {}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    export_cm_dockerfile(force,**config_dict)

if __name__ == '__main__':
    app()
    