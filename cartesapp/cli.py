import os
import logging
from typing import Optional, List, Annotated, Dict, Any
import traceback
import typer

from cartesapp.manager import Manager
from cartesapp.utils import get_modules, DEFAULT_CONFIGS, SHELL_CONFIGS, DEFAULT_CONFIGFILE, read_config_file
from cartesapp.external_tools import run_cmd, run_node, run_cm, build_drives
from cartesapp.sdk import get_sdk_version

LOGGER = logging.getLogger(__name__)

###
# AUX

MAKEFILENAME = "Makefile"

def cartesapp_run(modules=[],reset_storage=False):
    run_params = {}
    run_params['reset_storage'] = reset_storage
    m = Manager()
    for mod in modules:
        m.add_module(mod)
    m.setup_manager(**run_params)
    m.run()

def create_project(name:str,force:bool|None=None,**kwargs):
    from cartesapp.template_generator import create_cartesapp_module
    if os.path.exists(name) and os.path.isdir(name):
        if not force:
            raise Exception(f"There is already a {name} directory")
    else:
        os.makedirs(name)

    module_name = 'app' if kwargs.get('module_name') is None else str(kwargs.get('module_name'))
    create_cartesapp_module(module_name,basedir=name)

# def run_dev_node(**kwargs):
#     import subprocess, time
#     from multiprocessing import Event
#     from watchdog.observers import Observer
#     from watchdog.events import PatternMatchingEventHandler

#     class ReloadCartesappEventHandler(PatternMatchingEventHandler):
#         reload_event = None
#         def __init__(self, reload_event):
#             super().__init__(patterns=['*.py'])
#             self.reload_event = reload_event
#         def on_modified(self, event):
#             self.reload_event.set()
#         def on_deleted(self, event):
#             self.reload_event.set()
#         def on_moved(self, event):
#             self.reload_event.set()

#     if kwargs.get('modules') is None:
#         print("please define modules")
#         return

#     dev_image_name = get_dev_node_image_name()
#     image_info_json = get_image_info(dev_image_name)
#     if image_info_json is None:
#         raise Exception(f"Couldn't get docker image {dev_image_name}. Make sure to build it first with [cartesapp build-dev-image]")

#     name = subprocess.run("whoami", capture_output=True).stdout.decode().strip()
#     su = ["--env",f"USER={name}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
#     args = ["docker","run","--rm"]
#     args.extend(su)
#     if kwargs.get('port') is not None:
#         args.extend(["-p",f"{kwargs.get('port')}:8080"])
#     else:
#         args.extend(["-p",f"8080:8080"])
#     if kwargs.get('rollups-port') is not None:
#         args.extend(["-p",f"{kwargs.get('rollups-port')}:5004"])
#     else:
#         args.extend(["-p",f"5004:5004"])
#     if kwargs.get('rpc-url') is None:
#         if kwargs.get('anvil-port') is not None:
#             args.extend(["-p",f"{kwargs.get('anvil-port')}:8545"])
#         else:
#             args.extend(["-p",f"8545:8545"])
#     if kwargs.get('add-host') is not None:
#         args.append(f"--add-host={kwargs.get('add-host')}")
#     args.append(dev_image_name)
#     nonodo_args = ["nonodo","--http-address=0.0.0.0","--anvil-address=0.0.0.0","--http-port=8080","--http-rollups-port=5004","--anvil-port=8545"]

#     if kwargs.get('disable-advance') is not None:
#         nonodo_args.append("--disable-advance")
#     if kwargs.get('rpc-url') is not None:
#         nonodo_args.append(f"--rpc-url={kwargs.get('rpc-url')}")
#     if kwargs.get('contracts-application-address') is not None:
#         nonodo_args.append(f"--contracts-application-address={kwargs.get('contracts-application-address')}")
#     if kwargs.get('contracts-input-box-address') is not None:
#         nonodo_args.append(f"--contracts-input-box-address={kwargs.get('contracts-input-box-address')}")
#     if kwargs.get('contracts-input-box-block') is not None:
#         nonodo_args.append(f"--contracts-input-box-block={kwargs.get('contracts-input-box-block')}")

#     args.extend(nonodo_args)

#     path = '.'

#     observer = Observer()
#     reload_event = Event()

#     run_configs = {
#         "reload_event": reload_event,
#         "modules": kwargs['modules'],
#         "delay_restart_time":5
#     }
#     if kwargs.get('reset') is not None:
#         run_configs['reset'] = kwargs.get('reset').lower() in ['true', '1', 't', 'y', 'yes']
#     if kwargs.get('delay_restart_time') is not None:
#         run_configs['delay_restart_time'] = kwargs.get('delay_restart_time')

#     cs = CartesappProcess(**run_configs)
#     event_handler = ReloadCartesappEventHandler(reload_event)

#     observer.schedule(event_handler, path, recursive=True)

#     logging.getLogger("watchdog").setLevel(logging.WARNING)

#     try:
#         observer.start()
#         node = subprocess.Popen(args, start_new_session=True)
#         time.sleep(1)
#         cs.start()
#         output, errors = node.communicate()
#         if node.returncode > 0:
#             raise Exception(f"Error running dev node: {str(node.returncode)}")
#     except KeyboardInterrupt:
#         observer.stop()
#         cs.terminate_proc()
#         node.terminate()
#     finally:
#         node.wait()
#         observer.join()

###
# CLI

app = typer.Typer(help="Cartesapp Manager: manage your Cartesi Rollups App")


@app.command()
def run(log_level: Optional[str] = None,reset_storage: Optional[bool] = False):
    """
    Run the cartesapp application
    """
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
def generate_frontend_libs(libs_path: Optional[str] = None, frontend_path: Optional[str] = None, generate_debug_components: Optional[bool] = None):
    """
    Generate libs to use on the frontend
    """
    args = {}
    if libs_path is not None:
        args["libs_path"] = libs_path
    if frontend_path is not None:
        args["frontend_path"] = frontend_path
    if generate_debug_components is not None:
        args["generate_debug_components"] = generate_debug_components
    m = Manager()
    for mod in get_modules():
        m.add_module(mod)
    m.generate_frontend_lib(**args)

#   run npm create vite frontend -- --template react-ts
#   npm i @cartesi/viem@2.0.0-alpha.4 @rjsf/core@6.0.0-beta.7 @rjsf/utils@6.0.0-beta.7 @rjsf/validator-ajv8@6.0.0-beta.7 ajv@^8.17.1 ajv-formats@^3.0.1
#   generate frontend with main app
@app.command()
def create_frontend(libs_dir: Optional[str] = None, frontend_path: Optional[str] = None):
    """
    Create basic vite frontend to interact with cartesapp backend
    """
    from cartesapp.template_generator import create_frontend_structure
    args = {}
    if libs_dir is not None:
        args["libs_path"] = os.path.join('src',libs_dir)
    if frontend_path is not None:
        args["frontend_path"] = frontend_path
    args["generate_debug_components"] = True
    all_modules = get_modules()
    if len(all_modules) == 0:
        raise Exception("No modules detected")
    m = Manager()
    for mod in all_modules:
        m.add_module(mod)
    create_frontend_structure(**args)
    m.generate_frontend_lib(**args)

# TODO: Dont use makefile, create example module
@app.command()
def create(name: str,
        config: Annotated[List[str]|None, typer.Option(help="args config in the [ key=value ] format")] = None,
        force: Optional[bool] = None):
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
    print("  You should now create a module for your project")
    print("  We recommend creating and activating a virtual environment then installing cartesapp with extra [dev] dependencies")

@app.command()
def create_module(name: str):
    """
    Create new MODULE for current Cartesi Rollups App
    """
    from cartesapp.template_generator import create_cartesapp_module
    print(f"Creating module {name}")
    create_cartesapp_module(name)

@app.command()
def deploy(config_file: Optional[str] = None,
        config: Optional[Annotated[List[str], typer.Option(help="config in the [ key=value ] format")]] = None,
        env: Optional[Annotated[List[str], typer.Option(help="env in the [ key=value ] format")]] = None):
    """
    Deploy the application onchain
    """
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    configs_from_cfile = read_config_file(config_file).get('node') or {}

    env_dict = {}
    if env is not None:
        import re
        for c in env:
            k,v = re.split('=',c,1)
            env_dict[k] = v
    env_dict["EXTRA_ARGS"] = "--no-register"
    config_dict: Dict[str,Any] = {"envs":env_dict}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    all_configs = configs_from_cfile | config_dict
    app_name = 'app'
    if all_configs.get('APP_NAME') is not None:
        app_name = all_configs.get('APP_NAME')
    all_configs['cmd'] = f"/deploy.sh /mnt/apps/{app_name}"
    run_node(**all_configs)

@app.command()
def node(config_file: Optional[str] = None,
        config: Optional[Annotated[List[str], typer.Option(help="config in the [ key=value ] format")]] = None,
        env: Optional[Annotated[List[str], typer.Option(help="env in the [ key=value ] format")]] = None):
    """
    Run the node and register/deploy the application
    """
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    configs_from_cfile = read_config_file(config_file).get('node') or {}

    env_dict = {}
    if env is not None:
        import re
        for c in env:
            k,v = re.split('=',c,1)
            env_dict[k] = v
    config_dict: Dict[str,Any] = {"envs":env_dict}
    if config is not None:
        import re
        for c in config:
            k,v = re.split('=',c,1)
            config_dict[k] = v
    all_configs = configs_from_cfile | config_dict
    run_node(**all_configs)

@app.command()
def build(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        drives_only: Optional[bool] = None, rebuild_data_drive: Optional[bool] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi'):
    """
    Built the snapshot of the application
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    machine_dict = {}
    if machine_config is not None:
        import re
        for c in machine_config:
            k,v = re.split('=',c,1)
            machine_dict[k] = v
    params: Dict[str,Any] = {} | DEFAULT_CONFIGS
    params |= read_config_file(config_file)
    params["machine"] |= machine_dict
    if rebuild_data_drive is not None:
        params["rebuild-data-drive"] = rebuild_data_drive
    if base_path is not None:
        params["base_path"] = base_path
    if drives_only:
        build_drives(**params)
        exit(0)
    params['store'] = True
    print("Building cartesi machine snapshot. This may take some time...")
    run_cm(**params)
    print("Done!")

@app.command()
def shell(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi'):
    """
    Run cartesi machine shell to customize the root file systema
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    machine_dict = {}
    if machine_config is not None:
        import re
        for c in machine_config:
            k,v = re.split('=',c,1)
            machine_dict[k] = v
    params: Dict[str,Any] = {} | SHELL_CONFIGS
    params |= read_config_file(config_file)
    params["machine"] |= machine_dict
    if base_path is not None:
        params["base_path"] = base_path
    params["interactive"] = True
    run_cm(**params)

@app.command()
def test(test_files: Annotated[Optional[List[str]], typer.Argument()] = None, cartesi_machine: Optional[bool] = False,
        config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        test_param: Optional[List[str]] = None, default_test_params: Optional[bool] = True):
    """
    Test the application
    """
    import pytest
    if cartesi_machine:
        os.environ['CARTESAPP_TEST_CLIENT'] = 'cartesi_machine'
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    args = []
    if default_test_params:
        args.extend(["--capture=no","--maxfail=1","--order-dependencies","-o","log_cli=true"]) #,"-W","error::DeprecationWarning"])
    if test_param is not None:
        args.extend([a for a in test_param])
    if log_level is not None:
        args.append(f"--log-level={log_level}")
    if test_files is not None:
        for tfile in test_files:
            args.append(tfile)
    exit(pytest.main(args))

if __name__ == '__main__':
    app()
