import os
import logging
from typing import get_type_hints, Dict, Any
import traceback
import urllib.parse
import random
import json
from pydantic import BaseModel

from cartesi import Rollup, RollupData, URLParameters, abi
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.storage import helpers
from cartesapp.context import Context
from cartesapp.output import add_output, index_input as _index_input
from cartesapp.utils import bytes2hex, str2hex, convert_camel_case, get_function_signature, EmptyClass, InputFormat


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

def _make_url_query(func,model,has_param,module,**func_configs):
    @helpers.db_session
    def query(rollup: Rollup, params: URLParameters) -> bool:
        res: bool = False
        ctx = Context
        try:
            func_configs["query_format"] = InputFormat.url
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


def _make_json_query(func,model,has_param,module,**func_configs):
    @helpers.db_session
    def query(rollup: Rollup, raw_data: RollupData) -> bool:
        res: bool = False
        ctx = Context
        try:
            param_list = []
            data = raw_data.json_payload()
            func_configs["query_format"] = InputFormat.json
            if data.get("jsonrpc") == "2.0":
                req_id = data.get('id')
                if req_id is None: raise Exception("Missing id parameters for jsonrpc request")
                func_configs["query_format"] = InputFormat.jsonrpc
                func_configs["id"] = req_id
            if has_param:
                params = data.get('params')
                fields = []
                values = []
                model_fields = list(model.__fields__.keys())
                extended_model = func_configs.get("extended_model")
                diff_fields = None
                if extended_model is not None:
                    diff_fields = list(set(extended_model.__fields__.keys()).difference(model_fields))
                if type(params) == type([]):
                    for i in range(min(len(params),len(model_fields))):
                        fields.append(model_fields[i])
                        values.append(params[i])
                    param_list.append(model.parse_obj(dict(zip(fields, values))))
                    if diff_fields is not None and extended_model is not None and len(params) > len(values):
                        initial_param_ind = len(values)
                        for i in range(min(len(params) - initial_param_ind,len(diff_fields))):
                            fields.append(diff_fields[i])
                            values.append(params[initial_param_ind+i])
                        func_configs["extended_params"] = extended_model.parse_obj(dict(zip(fields, values)))
                elif type(params) == type({}):
                    for k in params:
                        if k in model_fields:
                            fields.append(k)
                            values.append(params[k])
                    param_list.append(model.parse_obj(dict(zip(fields, values))))
                    if diff_fields is not None and extended_model is not None and len(params) > len(values):
                        for k in diff_fields:
                            fields.append(k)
                            values.append(params[k])
                        func_configs["extended_params"] = extended_model.parse_obj(dict(zip(fields, values)))
                else:
                    if len(model_fields) >= 1:
                        fields.append(model_fields[0])
                        values.append(params)
                        param_list.append(model.parse_obj(dict(zip(fields, values))))
                    elif diff_fields is not None and extended_model is not None and len(diff_fields) >= 1:
                        fields.append(diff_fields[0])
                        values.append(params)
                        func_configs["extended_params"] = extended_model.parse_obj(dict(zip(fields, values)))
                    else:
                        raise Exception("Parameters format not supported")

                ctx.set_input(param_list[-1])

            ctx.set_context(rollup,None,module,**func_configs)
            res = func(*param_list)
        except Exception as e:
            msg = f"Error: {e}"
            LOGGER.error(msg)
            if logging.root.level <= logging.DEBUG:
                traceback.print_exc()
                add_output(msg,error=True)
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
        function_name = func_name if configs.get('no_module_header') else f"{mod_name}.{func_name}"
        header = ABIFunctionSelectorHeader(
            function=function_name,
            argument_types=abi.get_abi_types_from_model(model)
        ).to_bytes()
    param_list = [model]
    if configs.get('packed') is not None:
        param_list.append(configs.get('packed'))
    data = abi.encode_model(*param_list)
    return bytes2hex(header + data)

def encode_inspect_url_input(func, model: BaseModel) -> str:
    path = generate_url_input(func, model)
    return str2hex(path)

def generate_url_input(func, model: BaseModel) -> str:
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

    return path

def url_quote_param(k: str, v):
    if hasattr(v,'__iter__') and not isinstance(v, str) and not isinstance(v, bytes):
        return '&'.join([url_quote_param(k, i) for i in v])
    return f"{k}={urllib.parse.quote(v) if type(v) == bytes else f'{v}'}"

def encode_inspect_json_input(func, model: BaseModel) -> str:
    request_data = generate_json_input(func, model)
    return str2hex(json.dumps(request_data))

def generate_json_input(func, model: BaseModel) -> dict:
    orig_mod_name,func_name = get_function_signature(func)
    configs = Query.configs[f"{orig_mod_name}.{func_name}"]
    mod_name = configs.get('module_name') if configs.get('module_name') is not None else orig_mod_name
    selector = f"{mod_name}_{convert_camel_case(func_name)}"
    request_data: Dict[str,Any] = {"method":selector}
    model_dict = model.dict(exclude_none=True)
    if len(model_dict) > 0:
        request_data["params"] = model_dict

    return request_data

def encode_inspect_jsonrpc_input(func, model: BaseModel) -> str:
    request_data = generate_jsonrpc_input(func, model)
    return str2hex(json.dumps(request_data))

def generate_jsonrpc_input(func, model: BaseModel) -> dict:
    orig_mod_name,func_name = get_function_signature(func)
    configs = Query.configs[f"{orig_mod_name}.{func_name}"]
    mod_name = configs.get('module_name') if configs.get('module_name') is not None else orig_mod_name
    selector = f"{mod_name}_{convert_camel_case(func_name)}"
    request_data: Dict[str,Any] = {"jsonrpc": "2.0", "method":selector,"id":random.randint(1,1000)}
    model_dict = model.dict(exclude_none=True)
    if len(model_dict) > 0:
        request_data["params"] = model_dict

    return request_data

encode_mutation_input = encode_advance_input
encode_query_url_input = encode_inspect_url_input
encode_query_jsonrpc_input = encode_inspect_jsonrpc_input
encode_query_json_input = encode_inspect_json_input
