import os
import logging
import importlib
from inspect import getmembers, isfunction, signature
from typing import Optional, List
from pydantic import BaseModel, create_model
import traceback
import typer

from cartesi import DApp, Rollup, RollupData, RollupMetadata, ABIRouter, URLRouter, URLParameters, abi
from cartesi.models import ABIFunctionSelectorHeader

from .storage import Storage, helpers
from .output import MAX_OUTPUT_SIZE, MAX_AGGREGATED_OUTPUT_SIZE, MAX_SPLITTABLE_OUTPUT_SIZE, Output
from .input import Query, Mutation, _make_mut,  _make_query
from .setting import Setting

LOGGER = logging.getLogger(__name__)


###
# Aux

class EmptyClass(BaseModel):
    pass

splittable_query_params = {"part":(int,None)}


###
# Manager

class Manager(object):
    dapp = None
    abi_router = None
    url_router = None
    storage = None
    modules_to_add = []
    queries_info = {}
    mutations_info = {}

    def __new__(cls):
        return cls
    
    @classmethod
    def add_module(cls,mod):
        cls.modules_to_add.append(mod)

    @classmethod
    def _import_apps(cls):
        if len(cls.modules_to_add) == 0:
            raise Exception("No modules detected")

        add_dapp_relay = False
        add_indexer_query = False
        add_wallet = False
        storage_path = None
        for module_name in cls.modules_to_add:
            stg = importlib.import_module(f"{module_name}.settings")
            if not hasattr(stg,'FILES'):
                raise Exception(f"Module {module_name} has nothing to import (no FILES defined)")
            
            files_to_import = getattr(stg,'FILES')
            if not isinstance(files_to_import, list) or len(files_to_import) == 0:
                raise Exception(f"Module {module_name} has nothing to import (empty FILES list)")

            Setting.add(stg)
            if not add_indexer_query and hasattr(stg,'INDEX_OUTPUTS') and getattr(stg,'INDEX_OUTPUTS'):
                add_indexer_query = True
            
            if not add_dapp_relay and hasattr(stg,'ENABLE_DAPP_RELAY') and getattr(stg,'ENABLE_DAPP_RELAY'):
                add_dapp_relay = True
            
            if not add_wallet and hasattr(stg,'ENABLE_WALLET') and getattr(stg,'ENABLE_WALLET'):
                if not add_dapp_relay:
                    raise Exception(f"To enable wallet you should enable dapp relay")
                add_dapp_relay = True
                
            if hasattr(stg,'STORAGE_PATH'):
                if storage_path is not None and storage_path != getattr(stg,'STORAGE_PATH'):
                    raise Exception(f"Conflicting storage path")
                storage_path = getattr(stg,'STORAGE_PATH')

            for f in files_to_import:
                importlib.import_module(f"{module_name}.{f}")

        if add_indexer_query:
            indexer_lib = importlib.import_module(f".indexer.output_index",package='cartesapp')
            Output.add_output_index = indexer_lib.add_output_index
            
        if add_dapp_relay:
            importlib.import_module(f"cartesapp.relay.dapp_relay")

        if add_dapp_relay:
            importlib.import_module(f"cartesapp.wallet.dapp_wallet")

        if storage_path is not None:
            Storage.STORAGE_PATH = storage_path

    @classmethod
    def _register_queries(cls, add_to_router=True):
        query_selectors = []
        for func in Query.queries:
            func_name = func.__name__
            original_module_name = func.__module__.split('.')[0]
            configs = Query.configs[f"{original_module_name}.{func_name}"]
            module_name = configs.get('module_name') if configs.get('module_name') is not None else original_module_name

            sig = signature(func)

            if len(sig.parameters) > 1:
                raise Exception("Queries shouldn't have more than one parameter")

            it = iter(sig.parameters.items())
            param = next(it, None)
            if param is not None:
                model = param[1].annotation
            else:
                model = EmptyClass

            # using url router
            path = f"{module_name}/{func_name}"
            path_params = configs.get('path_params')
            if path_params is not None:
                for p in path_params:
                    path = f"{path}/{'{'+p+'}'}"
            if path in query_selectors:
                raise Exception("Duplicate query selector")
            query_selectors.append(path)

            original_model = model
            func_configs = {}
            if configs.get("splittable_output") is not None and configs["splittable_output"]:
                model_kwargs = splittable_query_params.copy()
                model_kwargs["__base__"] = model
                model = create_model(model.__name__+'Splittable',**model_kwargs)
                func_configs["extended_model"] = model
            
            abi_types = [] # abi.get_abi_types_from_model(model)
            cls.queries_info[f"{module_name}.{func_name}"] = {"selector":path,"module":module_name,"method":func_name,"abi_types":abi_types,"model":model,"configs":configs}
            if add_to_router:
                LOGGER.info(f"Adding query {module_name}.{func_name} selector={path}, model={model.__name__}")
                cls.url_router.inspect(path=path)(_make_query(func,original_model,param is not None,module_name,**func_configs))

    @classmethod
    def _register_mutations(cls, add_to_router=True):
        mutation_selectors = []
        for func in Mutation.mutations:
            func_name = func.__name__
            original_module_name = func.__module__.split('.')[0]
            configs = Mutation.configs[f"{original_module_name}.{func_name}"]
            module_name = configs.get('module_name') if configs.get('module_name') is not None else original_module_name
            
            sig = signature(func)

            if len(sig.parameters) > 1:
                raise Exception("Mutations shouldn't have more than one parameter")

            it = iter(sig.parameters.items())
            param = next(it, None)
            if param is not None:
                model = param[1].annotation
            else:
                model = EmptyClass

            # using abi router
            abi_types = abi.get_abi_types_from_model(model)
            header = None
            header_selector = None
            no_header = configs.get('no_header')
            has_header = no_header is None or not no_header
            if has_header:
                header = ABIFunctionSelectorHeader(
                    function=f"{module_name}.{func_name}",
                    argument_types=abi_types
                )
                header_selector = header.to_bytes().hex()
                if header_selector in mutation_selectors:
                    raise Exception("Duplicate mutation selector")
                mutation_selectors.append(header_selector)
            
            func_configs = {'has_header':has_header}
            if configs.get('packed'): func_configs['packed'] = configs['packed']

            cls.mutations_info[f"{module_name}.{func_name}"] = {"selector":header,"module":module_name,"method":func_name,"abi_types":abi_types,"model":model,"configs":configs}
            if add_to_router:
                LOGGER.info(f"Adding mutation {module_name}.{func_name} selector={header_selector}, model={model.__name__}")
                advance_kwargs = {}
                if has_header: advance_kwargs['header'] = header
                msg_sender = configs.get('msg_sender')
                if msg_sender is not None: advance_kwargs['msg_sender'] = msg_sender
                cls.abi_router.advance(**advance_kwargs)(_make_mut(func,model,param is not None,module_name,**func_configs))

    @classmethod
    def _run_setup_functions(cls):
        for app_setup in Setup.setup_functions:
            app_setup()

    @classmethod
    def run(cls):
        cls.dapp = DApp()
        cls.abi_router = ABIRouter()
        cls.url_router = URLRouter()
        cls.storage = Storage
        cls.dapp.add_router(cls.abi_router)
        cls.dapp.add_router(cls.url_router)
        cls._import_apps()
        cls._register_queries()
        cls._register_mutations()
        cls._run_setup_functions()
        cls.storage.initialize_storage()
        cls.dapp.run()

    @classmethod
    def generate_frontend_lib(cls, lib_path=None):
        cls._import_apps()
        cls._register_queries(False)
        cls._register_mutations(False)
        # generate lib
        from .template_frontend_generator import render_templates
        params = [
            Setting.settings,
            cls.mutations_info,
            cls.queries_info,
            Output.notices_info,
            Output.reports_info,
            Output.vouchers_info,
            cls.modules_to_add]
        if lib_path is not None: params.append(lib_path)
        render_templates(*params)

    @classmethod
    def create_frontend(cls):
        from .template_frontend_generator import create_frontend_structure
        create_frontend_structure()

class Setup:
    setup_functions = []
    
    def __new__(cls):
        return cls
    
    @classmethod
    def add_setup(cls, func):
        cls.setup_functions.append(_make_setup_function(func))

def _make_setup_function(f):
    @helpers.db_session
    def setup_func():
        f()
    return setup_func

def setup(**kwargs):
    def decorator(func):
        Setup.add_setup(func)
        return func
    return decorator


###
# CLI

app = typer.Typer(help="Cartesapp Manager: manage your Cartesi Rollups App")


@app.command()
def run(modules: List[str]):
    """
    Run backend with MODULES
    """
    try:
        m = Manager()
        for mod in modules:
            m.add_module(mod)
        m.run()
    except Exception as e:
        print(e)
        traceback.print_exc()
        exit(1)

@app.command()
def generate_fronted_libs(modules: List[str]):
    """
    Generate frontend libs for MODULES
    """
    try:
        m = Manager()
        for mod in modules:
            m.add_module(mod)
        m.generate_frontend_lib()
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
def create(name: str):
    """
    Create new Cartesi Rollups App with NAME
    """
    print("Not yet Implemented")
    exit(1)

@app.command()
def create_module(name: str, force: Optional[bool]):
    """
    Create new MODULE for current Cartesi Rollups App
    """
    print("Not yet Implemented")
    exit(1)

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
    Deploy App to NETWORK
    """
    # doctor basic reqs (sunodo,nonodo)
    print("Not yet Implemented")
    exit(1)

if __name__ == '__main__':
    app()
    