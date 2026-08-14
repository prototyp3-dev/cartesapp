import os
import logging
from typing import Optional, List, Annotated, Dict, Any
import traceback
import typer
import json

from cartesapp.manager import cartesapp_run
from cartesapp.utils import (get_modules, DEFAULT_CONFIGS, SHELL_CONFIGS, DEFAULT_CONFIGFILE,
    read_config_file, deep_merge_dicts, parse_key_value, parse_drive_config, load_machine_drive_config)
from cartesapp.external_tools import run_node, run_cm, run_cmd, build_drives, IMAGE_DIR
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

app = typer.Typer(help="Cartesapp Manager: manage your Cartesi Rollups App",no_args_is_help=True)

def version_callback(value: bool):
    if value:
        from cartesapp.sdk import get_sdk_version
        print(f"Cartesapp {get_sdk_version()}")
        raise typer.Exit()

@app.callback()
def main(version: Optional[bool] = typer.Option(None, "--version", callback=version_callback, is_eager=True)):
    pass

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

def _module_storage_path() -> Optional[str]:
    """Read the app's STORAGE_PATH from module settings (cheap import)."""
    import importlib
    for mod in get_modules():
        try:
            stg = importlib.import_module(f"{mod}.settings")
        except Exception:
            continue
        if hasattr(stg, "STORAGE_PATH"):
            return getattr(stg, "STORAGE_PATH")
    return None

@app.command()
def query_server(
    host: str = "0.0.0.0",
    port: int = 8090,
    log_level: Optional[str] = None,
    reset_storage: Optional[bool] = False,
    watch_snapshots: Optional[str] = None,
    watch_drive: Optional[Annotated[List[str], typer.Option(help="Drive name(s) to watch; overrides [node].watched_drives")]] = None,
    app_name: str = "app",
    config_file: Optional[str] = None,
):
    """
    Serve only queries (inspects) over a plain HTTP server (no Cartesi node).

    Returns a Cartesi-node-compatible inspect response, so a generated frontend
    works against it by pointing its node URL at this server.

    With --watch-snapshots <dir> it becomes a *reader*: it watches a Cartesi
    node's snapshot directory, extracts the configured drive(s) from each new
    snapshot, and restarts the query-server bound to that committed state.
    """
    try:
        if log_level is not None:
            logging.basicConfig(level=getattr(logging,log_level.upper()))

        if watch_snapshots is None:
            from cartesapp.manager import cartesapp_run_query_server
            cartesapp_run_query_server(
                modules=get_modules(),
                reset_storage=reset_storage,
                host=host,
                port=port,
            )
            return

        # reader mode
        from cartesapp.reader import run_reader
        cfile = load_machine_drive_config(config_file, DEFAULT_CONFIGS)
        drives_cfg = cfile.get("drives") or {}
        node_cfg = cfile.get("node") or {}
        drives = list(watch_drive) if watch_drive else list(node_cfg.get("watched_drives") or ["data"])
        storage_path = _module_storage_path()
        storage_drive = storage_path.split("/")[0] if storage_path else None
        run_reader(
            watch_dir=watch_snapshots,
            drives=drives,
            drives_cfg=drives_cfg,
            modules=get_modules(),
            host=host,
            port=port,
            app_name=app_name,
            storage_drive=storage_drive,
        )
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

@app.command()
def generate_frontend_libs(libs_dir: Optional[str] = None, frontend_path: Optional[str] = None, generate_debug_components: Optional[bool] = None):
    """
    Generate libs to use on the frontend
    """
    from cartesapp.manager import Manager
    args = {}
    if libs_dir is not None:
        args["libs_path"] = libs_dir
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
    from cartesapp.manager import Manager
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
    config_dict = parse_key_value(config)
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
        env: Optional[Annotated[List[str], typer.Option(help="env in the [ key=value ] format")]] = None,
        volume: Optional[Annotated[List[str], typer.Option(help="volume in the [ key=value ] format")]] = None,
        log_level: Optional[str] = None):
    """
    Deploy the application onchain
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    configs_from_cfile = read_config_file(config_file).get('node') or {}

    env_dict = parse_key_value(env)
    env_dict["EXTRA_ARGS"] = "--register=false"
    config_dict: Dict[str,Any] = {"envs":env_dict,"volumes":parse_key_value(volume)}
    config_dict.update(parse_key_value(config))
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
        volume: Optional[Annotated[List[str], typer.Option(help="volume in the [ key=value ] format")]] = None,
        dev: Optional[Annotated[bool, typer.Option(help="Run node in Dev mode: rebuilds snapshot and reloads it on the node")]] = None,
        dev_watch_patterns: Optional[Annotated[List[str], typer.Option(help="File patterns to watch for changes when running in Dev mode")]] = None,
        dev_path: Optional[Annotated[str, typer.Option(help="Path to watch for changes when running in Dev mode")]] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        drive_config: Optional[Annotated[List[str], typer.Option(help="drive config in the [ drive.key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi', log_level: Optional[str] = None):
    """
    Run the node and register/deploy the application
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    cfile = load_machine_drive_config(config_file, DEFAULT_CONFIGS, base_path,
        parse_key_value(machine_config), parse_drive_config(drive_config))
    configs_from_cfile = cfile.get('node') or {}

    if not os.path.isdir(os.path.join(cfile["base_path"],IMAGE_DIR)):
        params: Dict[str,Any] = deep_merge_dicts({}, cfile)
        params['store'] = True
        print("Building cartesi machine snapshot. This may take some time...")
        run_cm(**params)
        # raise Exception("Couldn't find image, please build it first")

    config_dict: Dict[str,Any] = {"envs":parse_key_value(env),"volumes":parse_key_value(volume)}
    config_dict.update(parse_key_value(config))
    node_configs = deep_merge_dicts(configs_from_cfile, config_dict)
    node_configs["config_file"] = config_file
    if dev:
        params = {}
        if dev_watch_patterns is not None:
            params["watch_patterns"] = dev_watch_patterns
        if dev_path is not None:
            params["watch_path"] = dev_path
        run_dev_node(cfile,node_configs,**params)
    else:
        run_node(**node_configs, workdir=base_path)

@app.command()
def build(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None, drives_only: Optional[bool] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        drive_config: Optional[Annotated[List[str], typer.Option(help="drive config in the [ drive.key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi'):
    """
    Built the snapshot of the application
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    params = load_machine_drive_config(config_file, DEFAULT_CONFIGS, base_path,
        parse_key_value(machine_config), parse_drive_config(drive_config))
    if drives_only:
        build_drives(**params)
        exit(0)
    params['store'] = True
    print("Building cartesi machine snapshot. This may take some time...")
    run_cm(**params)

@app.command()
def shell(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        drive_config: Optional[Annotated[List[str], typer.Option(help="drive config in the [ drive.key=value ] format")]] = None,
        base_path: Optional[str] = '.cartesi', entrypoint: Optional[str] = 'sh'):
    """
    Run cartesi machine shell to customize the root file system
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    params = load_machine_drive_config(config_file, SHELL_CONFIGS, base_path,
        parse_key_value(machine_config), parse_drive_config(drive_config))
    params["machine"]["entrypoint"] = entrypoint
    params["interactive"] = True
    run_cm(**params)

@app.command()
def test(test_files: Annotated[Optional[List[str]], typer.Argument()] = None, cartesi_machine: Optional[bool] = False,
        machine_config: Optional[Annotated[List[str], typer.Option(help="machine config in the [ key=value ] format")]] = None,
        drive_config: Optional[Annotated[List[str], typer.Option(help="drive config in the [ drive.key=value ] format")]] = None,
        config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None,
        test_param: Optional[List[str]] = None, default_test_params: Optional[bool] = True,
        base_path: Optional[str] = '.cartesi', rootfs: Optional[str] = None):
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
    if base_path is not None:
        os.environ['BASE_PATH'] = base_path
    if machine_config is not None:
        os.environ['MACHINE_CONFIG'] = json.dumps(parse_key_value(machine_config))
    if drive_config is not None:
        os.environ['DRIVES_CONFIG'] = json.dumps(parse_drive_config(drive_config))
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

@app.command()
def address_book(config_file: Optional[str] = DEFAULT_CONFIGFILE, log_level: Optional[str] = None):
    """
    Display the cartesi rollups addresses
    """
    if log_level is not None:
        logging.basicConfig(level=getattr(logging,log_level.upper()))
    params = {"config_file": config_file}
    args = ["sh","-c","column -s= -t ${CONTRACTS_ENV}"]
    run_cmd(args, force_docker=True,**params)


if __name__ == '__main__':
    app()
