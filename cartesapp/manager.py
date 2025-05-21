import os
import sys
import logging
import importlib
from inspect import signature
from pydantic import create_model

from cartesi import App, ABIRouter, URLRouter, JSONRouter, abi
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.storage import Storage
from cartesapp.output import Output, PROXY_SUFFIX
from cartesapp.input import InputFormat, Query, Mutation, _make_mut,  _make_url_query, _make_json_query
from cartesapp.setting import Setting
from cartesapp.setup import Setup
from cartesapp.utils import convert_camel_case, get_function_signature, EmptyClass

LOGGER = logging.getLogger(__name__)


###
# Aux

splittable_query_params = {"part":(int,None)}


###
# Manager

class Manager(object):
    app: App
    abi_router: ABIRouter
    url_router: URLRouter
    storage = None
    modules_to_add = []
    queries_info = {}
    mutations_info = {}
    disabled_endpoints = []

    def __new__(cls):
        return cls

    @classmethod
    def add_module(cls,mod):
        cls.modules_to_add.append(mod)

    @classmethod
    def _import_apps(cls):
        if len(cls.modules_to_add) == 0:
            raise Exception("No modules detected")

        add_indexer_query = False
        add_indexer_input_query = False
        add_wallet = False
        storage_path = None
        sys.path.insert(0,os.getcwd())
        for module_name in cls.modules_to_add:
            stg = None
            try:
                stg = importlib.import_module(f"{module_name}.settings")
            except ModuleNotFoundError:
                continue
            if not hasattr(stg,'FILES'):
                raise Exception(f"Module {module_name} has nothing to import (no FILES defined)")

            files_to_import = getattr(stg,'FILES')
            if not isinstance(files_to_import, list) or len(files_to_import) == 0:
                raise Exception(f"Module {module_name} has nothing to import (empty FILES list)")

            Setting.add(stg)
            if not add_indexer_query and hasattr(stg,'INDEX_OUTPUTS') and getattr(stg,'INDEX_OUTPUTS'):
                add_indexer_query = True

            if not add_indexer_input_query and hasattr(stg,'INDEX_INPUTS') and getattr(stg,'INDEX_INPUTS'):
                add_indexer_input_query = True

            if not add_wallet and hasattr(stg,'ENABLE_WALLET') and getattr(stg,'ENABLE_WALLET'):
                add_wallet = True

            if hasattr(stg,'STORAGE_PATH'):
                if storage_path is not None and storage_path != getattr(stg,'STORAGE_PATH'):
                    raise Exception("Conflicting storage path")
                storage_path = getattr(stg,'STORAGE_PATH')

            if hasattr(stg,'DISABLED_ENDPOINTS') and len(getattr(stg,'DISABLED_ENDPOINTS')) > 0:
                for endpoint in getattr(stg,'DISABLED_ENDPOINTS'):
                    if endpoint not in cls.disabled_endpoints:
                        cls.disabled_endpoints.append(endpoint)

            if hasattr(stg,'DISABLED_MODULE_OUTPUTS') and len(getattr(stg,'DISABLED_MODULE_OUTPUTS')) > 0:
                for mod in getattr(stg,'DISABLED_MODULE_OUTPUTS'):
                    if mod not in Output.disabled_modules:
                        Output.disabled_modules.append(mod)

            if not Storage.CASE_INSENSITIVITY_LIKE and hasattr(stg,'CASE_INSENSITIVITY_LIKE') and getattr(stg,'CASE_INSENSITIVITY_LIKE'):
                Storage.CASE_INSENSITIVITY_LIKE = getattr(stg,'CASE_INSENSITIVITY_LIKE')

            for f in files_to_import:
                importlib.import_module(f"{module_name}.{f}")

        indexer_mod = None
        if add_indexer_query:
            indexer_mod = importlib.import_module("cartesapp.indexer.io_index",package='cartesapp')
            Setting.add(indexer_mod.get_settings_module())
            Output.add_output_index = indexer_mod.add_output_index

        if add_indexer_input_query:
            if indexer_mod is None:
                indexer_mod = importlib.import_module("cartesapp.indexer.io_index",package='cartesapp')
                Setting.add(indexer_mod.get_settings_module())
            Output.add_input_index = indexer_mod.add_input_index

        if add_wallet:
            wallet_mod = importlib.import_module("cartesapp.wallet.app_wallet")
            Setting.add(wallet_mod.get_settings_module())

        if storage_path is not None:
            Storage.STORAGE_PATH = storage_path

    @classmethod
    def _register_json_query(cls, is_jsonrpc, func, module_name, func_name, original_model, model, configs, func_configs, add_to_router=True):
        selector = f"{module_name}_{convert_camel_case(func_name)}"

        json_selector = {"method":selector}
        if is_jsonrpc: json_selector["jsonrpc"] = "2.0"

        abi_types = [] # abi.get_abi_types_from_model(model)
        cls.queries_info[f"{module_name}.{func_name}"] = {"selector":selector,"query_type":"queryJsonrpcPayload" if is_jsonrpc else "queryJsonPayload","module":module_name,"method":func_name,"abi_types":abi_types,"model":model,"configs":configs}
        if add_to_router and cls.json_router:
            LOGGER.info(f"Adding query {module_name}.{func_name} selector={selector}, model={model.__name__}")
            cls.json_router.inspect(route_dict=json_selector)(_make_json_query(func,original_model,model.__name__ != EmptyClass.__name__,module_name,**func_configs))
        return selector

    @classmethod
    def _register_url_query(cls, func, module_name, func_name, original_model, model, configs, func_configs, add_to_router=True):
        path = f"{module_name}/{func_name}"
        path_params = configs.get('path_params')
        if path_params is not None:
            for p in path_params:
                path = f"{path}/{'{'+p+'}'}"

        abi_types = [] # abi.get_abi_types_from_model(model)
        cls.queries_info[f"{module_name}.{func_name}"] = {"selector":path,"query_type":"queryUrlPayload","module":module_name,"method":func_name,"abi_types":abi_types,"model":model,"configs":configs}
        if add_to_router and cls.url_router:
            LOGGER.info(f"Adding query {module_name}.{func_name} selector={path}, model={model.__name__}")
            cls.url_router.inspect(path=path)(_make_url_query(func,original_model,model.__name__ != EmptyClass.__name__,module_name,**func_configs))
        return path


    @classmethod
    def _register_queries(cls, add_to_router=True):
        url_query_selectors = []
        json_query_selectors = []
        jsonrpc_query_selectors = []
        for func in Query.queries:
            original_module_name, func_name = get_function_signature(func)
            if f"{original_module_name}.{func_name}" in cls.disabled_endpoints: continue
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

            original_model = model
            func_configs = {}
            if configs.get("splittable_output") is not None and configs["splittable_output"]:
                model_kwargs = splittable_query_params.copy()
                model_kwargs["__base__"] = model
                model = create_model(f"{model.__name__}Splittable",**model_kwargs)
                func_configs["extended_model"] = model

            stg = Setting.settings.get(module_name)
            query_format = getattr(stg,'QUERY_FORMAT') if stg is not None and hasattr(stg,'QUERY_FORMAT') else None
            if query_format == InputFormat.url.name:
                selector = cls._register_url_query(func, module_name, func_name,original_model, model, configs, func_configs, add_to_router)

                if selector in url_query_selectors:
                    raise Exception(f"Duplicate query selector {module_name}/{func_name}")
                url_query_selectors.append(selector)
            elif query_format == InputFormat.jsonrpc.name:
                selector = cls._register_json_query(True, func, module_name, func_name,original_model, model, configs, func_configs, add_to_router)

                if selector in jsonrpc_query_selectors:
                    raise Exception(f"Duplicate query selector {module_name}/{func_name}")
                jsonrpc_query_selectors.append(selector)
            # elif query_format == InputFormat.json.name:
            #     cls._register_url_query(module_name, func_name, model, configs)
            else:
                selector = cls._register_json_query(False, func, module_name, func_name,original_model, model, configs, func_configs, add_to_router)

                if selector in json_query_selectors:
                    raise Exception(f"Duplicate query selector {module_name}/{func_name}")
                json_query_selectors.append(selector)

    @classmethod
    def _register_mutations(cls, add_to_router=True):
        mutation_selectors = []
        for func in Mutation.mutations:
            original_module_name, func_name = get_function_signature(func)
            if f"{original_module_name}.{func_name}" in cls.disabled_endpoints: continue
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
                    raise Exception(f"Duplicate mutation selector {module_name}.{func_name}")
                mutation_selectors.append(header_selector)

            func_configs = {'has_header':has_header}
            if configs.get('packed'): func_configs['packed'] = configs['packed']

            if configs.get('proxy') is not None:
                if configs.get('msg_sender') is not None:
                    raise Exception(f"Can't use proxy with msg_sender for {module_name}.{func_name}")
                class CloneModel(model): pass
                clone_model = CloneModel
                clone_model.__name__ = f"{model.__name__}{PROXY_SUFFIX}"
                model = clone_model

            cls.mutations_info[f"{module_name}.{func_name}"] = {"selector":header,"module":module_name,"method":func_name,"abi_types":abi_types,"model":model,"configs":configs}

            if add_to_router:
                LOGGER.info(f"Adding mutation {module_name}.{func_name} selector={header_selector}, model={model.__name__}")
                advance_kwargs = {}
                if has_header: advance_kwargs['header'] = header
                msg_sender = configs.get('msg_sender')
                if msg_sender is not None: advance_kwargs['msg_sender'] = msg_sender
                proxy = configs.get('proxy')
                if proxy is not None:
                    advance_kwargs['msg_sender'] = proxy
                    func_configs['has_proxy'] = True
                cls.abi_router.advance(**advance_kwargs)(_make_mut(func,model,param is not None,module_name,**func_configs))

    @classmethod
    def _run_setup_functions(cls):
        for app_setup in Setup.setup_functions:
            app_setup()

    @classmethod
    def _run_post_setup_functions(cls):
        for app_setup in Setup.post_setup_functions:
            app_setup()

    @classmethod
    def setup_manager(cls,reset_storage=False):
        cls.app = App()
        cls.abi_router = ABIRouter()
        cls.url_router = URLRouter()
        cls.json_router = JSONRouter()
        cls.storage = Storage
        cls.app.add_router(cls.abi_router)
        cls.app.add_router(cls.url_router)
        cls.app.add_router(cls.json_router)
        cls._import_apps()
        cls._run_setup_functions()
        cls._register_queries()
        cls._register_mutations()
        cls.storage.initialize_storage(reset_storage)
        cls._run_post_setup_functions()

    @classmethod
    def run(cls):
        cls.app.run()

    @classmethod
    def generate_frontend_lib(cls,**extra_args):
        cls._import_apps()
        cls._register_queries(False)
        cls._register_mutations(False)
        # generate lib
        from cartesapp.template_generator import render_templates
        params = [
            Setting.settings,
            cls.mutations_info,
            cls.queries_info,
            Output.notices_info,
            Output.reports_info,
            Output.vouchers_info,
            cls.modules_to_add]
        render_templates(*params,**extra_args)

def run():
    import sys
    if len(sys.argv) > 1:
        logging.basicConfig(level=getattr(logging,sys.argv[1].upper()))
    from cartesapp.utils import get_modules
    m = Manager()
    for mod in get_modules():
        m.add_module(mod)
    m.setup_manager()
    m.run()

if __name__ == '__main__':
    run()
