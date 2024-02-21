import logging
from typing import Optional, List, get_type_hints
import traceback

from cartesi import Rollup, RollupData, RollupMetadata, URLParameters, abi

from .storage import helpers
from .context import Context
from .output import add_output

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
        func_name = func.__name__
        module_name = func.__module__.split('.')[0]
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
    def __new__(cls):
        return cls
    
    @classmethod
    def add(cls, func, **kwargs):
        cls.mutations.append(func)
        func_name = func.__name__
        module_name = func.__module__.split('.')[0]
        cls.configs[f"{module_name}.{func_name}"] = kwargs

# TODO: decorator params to allow chunked and compressed mutations
def mutation(**kwargs):
    if kwargs.get('chunk') is not None:
        LOGGER.warning("Chunking inputs is not implemented yet")
    if kwargs.get('compress') is not None:
        LOGGER.warning("Compressing inputs is not implemented yet")
    if kwargs.get('sender_address') is not None:
        LOGGER.warning("Sender address filtering is not implemented yet")
    def decorator(func):
        Mutation.add(func,**kwargs)
        return func
    return decorator


###
# Helpers

def _make_query(func,model,has_param,module,**func_configs):
    @helpers.db_session
    def query(rollup: Rollup, params: URLParameters) -> bool:
        try:
            res = False
            ctx = Context
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
    @helpers.db_session
    def mut(rollup: Rollup, data: RollupData) -> bool:
        try:
            res = False
            ctx = Context
            ctx.set_context(rollup,data.metadata,module,**kwargs)
            payload = data.bytes_payload()[(4 if kwargs.get('has_header') else 0):]
            param_list = []
            decode_params = {
                "data":payload,
                "model":model
            }
            is_packed = kwargs.get('packed')
            if is_packed is not None: decode_params["packed"] = is_packed
            if has_param:
                param_list.append(abi.decode_to_model(**decode_params))
            res = func(*param_list)
        except Exception as e:
            msg = f"Error: {e}"
            LOGGER.error(msg)
            if logging.root.level <= logging.DEBUG:
                traceback.print_exc()
                add_output(msg,tags=['error'])
        finally:
            if not res: helpers.rollback()
            ctx.clear_context()
        return res
    return mut
