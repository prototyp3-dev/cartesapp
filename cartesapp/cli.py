import os
import logging
from typing import Optional, List
import traceback
import typer

from .setting import SETTINGS_TEMPLATE
from .manager import Manager

LOGGER = logging.getLogger(__name__)

###
# AUX

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

if __name__ == '__main__':
    app()
    