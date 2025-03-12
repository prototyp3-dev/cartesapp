import os
import logging
from typing import get_type_hints
import traceback
import urllib.parse
from pydantic import BaseModel

from cartesi import Rollup, RollupData, URLParameters, abi
from cartesi.models import ABIFunctionSelectorHeader

from .storage import helpers
from .context import Context
from .output import add_output, index_input as _index_input
from .utils import bytes2hex, get_function_signature, EmptyClass

LOGGER = logging.getLogger(__name__)

# Query
class Query:
    queries = []
    configs = {}
    def __new__(cls):
        return cls

    @classmethod
    def add(cls, func, **kwargs):
        cls.queries.append(func)
        module_name, func_name = get_function_signature(func)
        cls.configs[f"{module_name}.{func_name}"] = kwargs

def query(**kwargs):
    def decorator(func):
        Query.add(func,**kwargs)
        return func
    return decorator

splittable_query_params = {"part":(int,None)}

# Mutation
class Mutation:
    mutations = []
    configs = {}
    add_input_index = None
    def __new__(cls):
        return cls

    @classmethod
    def add(cls, func, **kwargs):
        cls.mutations.append(func)
        module_name, func_name = get_function_signature(func)
        cls.configs[f"{module_name}.{func_name}"] = kwargs

# TODO: decorator params to allow chunked and compressed mutations
def mutation(**kwargs):
    if kwargs.get('chunk') is not None:
        LOGGER.warning("Chunking inputs is not implemented yet")
    if kwargs.get('compress') is not None:
        LOGGER.warning("Compressing inputs is not implemented yet")
    def decorator(func):
        Mutation.add(func,**kwargs)
        return func
    return decorator


###
# Helpers

def _make_query(func,model,has_param,module,**func_configs):
    @helpers.db_session
    def query(rollup: Rollup, params: URLParameters) -> bool:
        res: bool = False
        ctx = Context
        try:
            # TODO: accept abi encode or json (for larger post requests, configured in settings)
            # Decoding url parameters
            param_list = []
            if has_param:
                hints = get_type_hints(model)
                fields = []
                values = []
                model_fields = model.__fields__.keys()
                for k in model_fields:
                    if k in params.query_params:
                        field_str = str(hints[k])
                        if field_str.startswith('typing.List') or field_str.startswith('typing.Optional[typing.List'):
                            fields.append(k)
                            values.append(params.query_params[k])
                        else:
                            fields.append(k)
                            values.append(params.query_params[k][0])
                    if k in params.path_params:
                        fields.append(k)
                        values.append(params.path_params[k])
                param_list.append(model.parse_obj(dict(zip(fields, values))))

                extended_model = func_configs.get("extended_model")
                if extended_model is not None:
                    extended_hints = get_type_hints(extended_model)
                    for k in list(set(extended_model.__fields__.keys()).difference(model_fields)):
                        if k in params.query_params:
                            field_str = str(extended_hints[k])
                            if field_str.startswith('typing.List') or field_str.startswith('typing.Optional[typing.List'):
                                fields.append(k)
                                values.append(params.query_params[k])
                            else:
                                fields.append(k)
                                values.append(params.query_params[k][0])
                    func_configs["extended_params"] = extended_model.parse_obj(dict(zip(fields, values)))
                ctx.set_input(param_list[-1])

            ctx.set_context(rollup,None,module,**func_configs)
            res = func(*param_list)
        except Exception as e:
            msg = f"Error: {e}"
            LOGGER.error(msg)
            if logging.root.level <= logging.DEBUG:
                traceback.print_exc()
                add_output(msg)
        finally:
            helpers.rollback()
            ctx.clear_context()
        return res
    return query

def _make_mut(func,model,has_param,module, **kwargs):
    @helpers.db_session(strict=True)
    def mut(rollup: Rollup, data: RollupData) -> bool:
        res: bool = False
        ctx = Context
        try:
            ctx.set_context(rollup,data.metadata,module,**kwargs)
            all_payload_bytes = data.bytes_payload()
            payload_index = 4 if kwargs.get('has_header') else 0
            if kwargs.get('has_proxy') and ctx.metadata:
                new_payload_index = payload_index+20
                new_msg_sender = f"0x{all_payload_bytes[payload_index:new_payload_index].hex()}"
                ctx.metadata.msg_sender = new_msg_sender
                payload_index = new_payload_index
                # TODO: right now proxy overrides msg_sender, todo allow both
            payload = all_payload_bytes[payload_index:]
            param_list = []
            decode_params = {
                "data":payload,
                "model":model
            }
            is_packed = kwargs.get('packed')
            if is_packed is not None: decode_params["packed"] = is_packed
            if has_param:
                param_list.append(abi.decode_to_model(**decode_params))
                ctx.set_input(param_list[-1])
            res = func(*param_list)
        except Exception as e:
            msg = f"Error: {e}"
            traceback.print_exc()
            LOGGER.error(msg)
            if logging.root.level <= logging.DEBUG:
                traceback.print_exc()
                add_output(msg,tags=['error'])
        finally:
            if not res: helpers.rollback()
            else:
                helpers.commit()
                os.sync()
            ctx.clear_context()
        return res
    return mut

index_input = _index_input

def encode_advance_input(func = None, model: BaseModel | None = None) -> str:
    orig_mod_name,func_name = get_function_signature(func)
    configs = Mutation.configs[f"{orig_mod_name}.{func_name}"]
    mod_name = configs.get('module_name') if configs.get('module_name') is not None else orig_mod_name
    if model is None:
        model = EmptyClass()

    header = b''
    no_header = configs.get('no_header')
    if no_header is None or not no_header:
        header = ABIFunctionSelectorHeader(
            function=f"{mod_name}.{func_name}",
            argument_types=abi.get_abi_types_from_model(model)
        ).to_bytes()
    param_list = [model]
    if configs.get('packed') is not None:
        param_list.append(configs.get('packed'))
    data = abi.encode_model(*param_list)
    return bytes2hex(header + data)

def encode_inspect_input(func, model: BaseModel) -> str:
    orig_mod_name,func_name = get_function_signature(func)
    configs = Query.configs[f"{orig_mod_name}.{func_name}"]
    mod_name = configs.get('module_name') if configs.get('module_name') is not None else orig_mod_name

    path = f"{mod_name}/{func_name}"
    path_params = configs.get('path_params')
    if path_params is not None:
        for p in path_params:
            path = f"{path}/{'{'+p+'}'}"
    query_params = []
    for k,v in model.dict(exclude_none=True).items():
        k_path_param = '{'+k+'}'
        if k_path_param in path:
            path = path.replace(k_path_param,v)
        else:
            query_params.append(url_quote_param(k, v))
    path = f"{path}?{'&'.join(query_params)}"

    return bytes2hex(path.encode('ascii'))

def url_quote_param(k: str, v):
    if hasattr(v,'__iter__') and not isinstance(v, str) and not isinstance(v, bytes):
        return '&'.join([url_quote_param(k, i) for i in v])
    return f"{k}={urllib.parse.quote(v) if type(v) == bytes else f'{v}'}"

encode_mutation_input = encode_advance_input
encode_query_input = encode_inspect_input
