import os
import logging
from typing import Optional, List, Annotated, Dict, Any
import traceback
import typer

from cartesapp.manager import cartesapp_run
from cartesapp.utils import get_modules, DEFAULT_CONFIGS, SHELL_CONFIGS, DEFAULT_CONFIGFILE, read_config_file, deep_merge_dicts
from cartesapp.external_tools import run_node, run_cm, build_drives
from cartesapp.sdk import get_sdk_version
from cartesapp.dev_node import run_dev_node

LOGGER = logging.getLogger(__name__)

###
# AUX

MAKEFILENAME = "Makefile"

def create_project(name:str,force:bool|None=None,**kwargs):
    from cartesapp.template_generator import create_cartesapp_module
    if os.path.exists(name) and os.path.isdir(name):
        if not force:
            raise Exception(f"There is already a {name} directory")
    else:
        os.makedirs(name)

    module_name = 'app' if kwargs.get('module_name') is None else str(kwargs.get('module_name'))
    create_cartesapp_module(module_name,basedir=name)

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
    all_configs = deep_merge_dicts(configs_from_cfile, config_dict)
    app_name = 'app'
    if all_configs.get('APP_NAME') is not None:
        app_name = all_configs.get('APP_NAME')
    all_configs['cmd'] = f"/deploy.sh /mnt/apps/{app_name}"
    run_node(**all_configs)

@app.command()
def node(config_file: Optional[str] = None,
        config: Optional[Annotated[List[str], typer.Option(help="config in the [ key=value ] format")]] = None,
        env: Optional[Annotated[List[str], typer.Option(help="env in the [ key=value ] format")]] = None,
        dev: Optional[Annotated[bool, typer.Option(help="Run node in Dev mode: rebuilds snapshot and reloads it on the node")]] = None,
        dev_watch_patterns: Optional[Annotated[List[str], typer.Option(help="File patterns to watch for changes when running in Dev mode")]] = None,
        dev_path: Optional[Annotated[str, typer.Option(help="Path to watch for changes when running in Dev mode")]] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi', log_level: Optional[str] = None):
    """
    Run the node and register/deploy the application
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    machine_dict = {}
    if machine_config is not None:
        import re
        for c in machine_config:
            k,v = re.split('=',c,1)
            machine_dict[k] = v
    cfile: Dict[str,Any] = {} | DEFAULT_CONFIGS
    cfile = deep_merge_dicts(cfile, read_config_file(config_file))
    cfile["machine"] = deep_merge_dicts(cfile["machine"], machine_dict)
    if base_path is not None:
        cfile["base_path"] = base_path
    configs_from_cfile = cfile.get('node') or {}

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
    node_configs = deep_merge_dicts(configs_from_cfile, config_dict)
    if dev:
        params = {}
        if dev_watch_patterns is not None:
            params["watch_patterns"] = dev_watch_patterns
        if dev_path is not None:
            params["watch_path"] = dev_path
        run_dev_node(cfile,node_configs,**params)
    else:
        run_node(**node_configs)

@app.command()
def build(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None, drives_only: Optional[bool] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi'):
    """
    Built the snapshot of the application
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    machine_dict = {}
    if machine_config is not None:
        import re
        for c in machine_config:
            k,v = re.split('=',c,1)
            machine_dict[k] = v
    params: Dict[str,Any] = {} | DEFAULT_CONFIGS
    params = deep_merge_dicts(params, read_config_file(config_file))
    params["machine"] = deep_merge_dicts(params["machine"], machine_dict)
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
    machine_dict = {}
    if machine_config is not None:
        import re
        for c in machine_config:
            k,v = re.split('=',c,1)
            machine_dict[k] = v
    params: Dict[str,Any] = {} | SHELL_CONFIGS
    params = deep_merge_dicts(params, read_config_file(config_file))
    params["machine"] = deep_merge_dicts(params["machine"], machine_dict)
    params["machine"]["entrypoint"] = "sh"
    if base_path is not None:
        params["base_path"] = base_path
    params["interactive"] = True
    run_cm(**params)

@app.command()
def test(test_files: Annotated[Optional[List[str]], typer.Argument()] = None, cartesi_machine: Optional[bool] = False,
        config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        test_param: Optional[List[str]] = None, default_test_params: Optional[bool] = True,
        rootfs: Optional[str] = None):
    """
    Test the application
    """
    import pytest
    if cartesi_machine:
        os.environ['CARTESAPP_TEST_CLIENT'] = 'cartesi_machine'
    if config_file is not None:
        os.environ['CARTESAPP_CONFIG_FILE'] = config_file
    if rootfs is not None:
        os.environ['TEST_ROOTFS'] = os.path.abspath(rootfs)
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
