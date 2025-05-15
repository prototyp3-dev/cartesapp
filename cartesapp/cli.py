import os
import logging
from typing import Optional, List, Annotated, Dict, Any
import traceback
import typer
from enum import Enum
from multiprocessing import Process

from cartesapp.setting import SETTINGS_TEMPLATE
from cartesapp.manager import Manager
from cartesapp.utils import get_modules, DEFAULT_CONFIGS, SHELL_CONFIGS, DEFAULT_CONFIGFILE, read_config_file
from cartesapp.external_tools import run_cmd, communicate_cmd, run_node, run_cm, build_drives
from cartesapp.sdk import SDK_IMAGE, get_sdk_version

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

def create_project(name:str,force:bool|None=False,**kwargs):
    if os.path.exists(name) and os.path.isdir(name):
        if not force:
            raise Exception(f"There is already a {name} directory")
    else:
        os.makedirs(name)

    # TODO: create default module and tests that showcases simple application (mix between count and echo examples)

###
# CLI

app = typer.Typer(help="Cartesapp Manager: manage your Cartesi Rollups App")

def create_cartesapp_module(module_name: str):
    if not os.path.exists(module_name):
        os.makedirs(module_name)
    if not os.path.exists(f"{module_name}/settings.py"):
        with open(f"{module_name}/settings.py", 'w') as f:
            f.write(SETTINGS_TEMPLATE)


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
def generate_frontend_libs(libs_path: Optional[str] = None, frontend_path: Optional[str] = None):
    """
    Generate libs to use on the frontend
    """
    try:
        m = Manager()
        for mod in get_modules():
            m.add_module(mod)
        m.generate_frontend_lib(libs_path,frontend_path)
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

# TODO: Implement this
# @app.command()
# def create_frontend(libs_path: Optional[str] = None, frontend_path: Optional[str] = None):
#     """
#     Create basic frontend structure
#     """
#     # check if it exists, bypass with force
#     # create frontend web
#     # install packages ["ajv": "^8.12.0","ethers": "^5.7.2","ts-transformer-keys": "^0.4.4"]
#     print("Note: not fully implemented yet")
#     m = Manager()
#     m.create_frontend(libs_path,frontend_path)
#     exit(1)

# TODO: Dont use makefile
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
    print(f"  You should now create a module for your project")
    print(f"  We recommend creating and activating a virtual environment then installing cartesapp with extra [dev] dependencies")

@app.command()
def create_module(name: str):
    """
    Create new MODULE for current Cartesi Rollups App
    """
    print(f"Creating module {name}")
    create_cartesapp_module(name)

# TODO: Implement this
#       with v2 it should use rollups node functions, or direct contract commands, or direct python commands
# @app.command()
# def deploy(conf: str):
#     """
#     Deploy App with CONF file
#     """
#     # doctor basic reqs (cartesi)
#     print("Not yet Implemented")
#     exit(1)

@app.command()
def node(config_file: Optional[str] = None,
        config: Optional[Annotated[List[str], typer.Option(help="config in the [ key=value ] format")]] = None,
        env: Optional[Annotated[List[str], typer.Option(help="env in the [ key=value ] format")]] = None):
    """
    Run the node and register/deploy the application
    """
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

    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    run_node(**config_dict)

@app.command()
def build(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        drives_only: Optional[bool] = None, rebuild_data_drive: Optional[bool] = None,
        base_path: Optional[str] = '.cartesi'):
    """
    Built the snapshot of the application
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    params: Dict[str,Any] = {} | DEFAULT_CONFIGS
    params |= read_config_file(config_file)
    if rebuild_data_drive is not None:
        params["rebuild-data-drive"] = rebuild_data_drive
    if base_path is not None:
        params["base_path"] = base_path
    if drives_only:
        build_drives(**params)
        exit(0)
    params['store'] = True
    run_cm(**params)

@app.command()
def shell(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        base_path: Optional[str] = '.cartesi'):
    """
    Run cartesi machine shell to customize the root file systema
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    params: Dict[str,Any] = {} | SHELL_CONFIGS
    params |= read_config_file(config_file)
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
