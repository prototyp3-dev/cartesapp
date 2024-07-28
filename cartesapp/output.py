from enum import Enum
import json
from pydantic import BaseModel
from typing import Union
import logging
from Crypto.Hash import keccak

from cartesi import abi

from .utils import str2bytes, hex2bytes, bytes2hex
from .context import Context
from .setting import Setting

LOGGER = logging.getLogger(__name__)

###
# Configs

MAX_OUTPUT_SIZE = 1048567 # (2097152-17)/2
MAX_AGGREGATED_OUTPUT_SIZE = 4194248 # 4194248 = 4194304 (4MB) - 56 B (extra 0x and json formating)
MAX_SPLITTABLE_OUTPUT_SIZE = 4194247 # Extra byte means there's more data
PROXY_SUFFIX = "Proxy"

###
# Models

class IOType(Enum):
    report = 0
    notice = 1
    voucher = 2
    input = 3

class OutputFormat(Enum):
    abi = 0
    packed_abi = 1
    json = 2

###
# Outputs

class Output:
    notices_info = {}
    reports_info = {}
    vouchers_info = {}
    disabled_modules = []
    add_output_index = None
    add_input_index = None
    def __new__(cls):
        return cls
    
    @classmethod
    def add_report(cls, klass, **kwargs):
        module_name = kwargs.get('module_name') if kwargs.get('module_name')is not None else klass.__module__.split('.')[0]
        class_name = klass.__name__
        abi_types = [] # abi.get_abi_types_from_model(klass)
        cls.reports_info[f"{module_name}.{class_name}"] = {"module":module_name,"class":class_name,"abi_types":abi_types,"model":klass}

    @classmethod
    def add_notice(cls, klass, **kwargs):
        module_name = kwargs.get('module_name') if kwargs.get('module_name')is not None else klass.__module__.split('.')[0]
        class_name = klass.__name__
        abi_types = abi.get_abi_types_from_model(klass)
        cls.notices_info[f"{module_name}.{class_name}"] = {"module":module_name,"class":class_name,"abi_types":abi_types,"model":klass}

    @classmethod
    def add_voucher(cls, klass, **kwargs):
        module_name = kwargs.get('module_name') if kwargs.get('module_name')is not None else klass.__module__.split('.')[0]
        class_name = klass.__name__
        abi_types = abi.get_abi_types_from_model(klass)
        cls.vouchers_info[f"{module_name}.{class_name}"] = {"module":module_name,"class":class_name,"abi_types":abi_types,"model":klass}

def notice(**kwargs):
    def decorator(klass):
        Output.add_notice(klass,**kwargs)
        return klass
    return decorator

def report(**kwargs):
    def decorator(klass):
        Output.add_report(klass,**kwargs)
        return klass
    return decorator

def voucher(**kwargs):
    def decorator(klass):
        Output.add_voucher(klass,**kwargs)
        return klass
    return decorator

def normalize_output(data,encode_format) -> Union[bytes, str]:
    if isinstance(data, bytes): return data,'bytes'
    if isinstance(data, int): data.to_bytes(32,byteorder='big'),'int'
    if isinstance(data, str): 
        if data.startswith('0x'): return hex2bytes(data[2:]),'hex'
        return str2bytes(data),'str'
    if isinstance(data, dict) or isinstance(data, list) or isinstance(data, tuple):
        class_name = type(data).__name__
        return str2bytes(json.dumps(data)),class_name
    if issubclass(data.__class__,BaseModel):
        class_name = f"{data.__module__.split('.')[0]}.{data.__class__.__name__}"
        if encode_format == OutputFormat.abi: return abi.encode_model(data),class_name
        if encode_format == OutputFormat.packed_abi: return abi.encode_model(data,True),class_name
        if encode_format == OutputFormat.json: return str2bytes(data.json(exclude_unset=True,exclude_none=True)),class_name
    raise Exception("Invalid output format")

def normalize_voucher(*kargs):
    if len(kargs) == 1:
        if isinstance(kargs[0], bytes): return kargs[0],'bytes'
        if isinstance(kargs[0], str): return hex2bytes(kargs[0]),'hex'
        if issubclass(kargs[0].__class__,BaseModel):

            args_types = abi.get_abi_types_from_model(kargs[0])
            signature = f'{kargs[0].__class__.__name__}({",".join(args_types)})'
            sig_hash = keccak.new(digest_bits=256)
            sig_hash.update(signature.encode('utf-8'))

            selector = sig_hash.digest()[:4]
            data = abi.encode_model(kargs[0])
            return selector+data,kargs[0].__class__.__name__
        raise Exception("Invalid voucher payload")
    if len(kargs) == 2:
        if not isinstance(kargs[0], str): raise Exception("Invalid voucher selector")
        if not issubclass(kargs[1].__class__,BaseModel): raise Exception("Invalid voucher model")

        args_types = abi.get_abi_types_from_model(kargs[1])
        signature = f'{kargs[0]}({",".join(args_types)})'
        sig_hash = keccak.new(digest_bits=256)
        sig_hash.update(signature.encode('utf-8'))

        selector = sig_hash.digest()[:4]
        data = abi.encode_model(kargs[1])

        return selector+data,kargs[1].__class__.__name__
    # TODO: 3 is name, classes, and data, 
    #   too many problems: how is model stored in index? how formats are defined: str or abi annotation? 
    raise Exception("Invalid number of arguments")

def send_report(payload_data, **kwargs):
    ctx = Context
    # only one output to allow always chunking
    if ctx.metadata is None and ctx.n_reports > 0: # single report per inspect
        raise Exception("Can't add multiple reports")

    if ctx.module in Output.disabled_modules:
        LOGGER.debug(f"Skipping report: disabled {ctx.module} module")
        return

    stg = Setting.settings.get(ctx.module)

    report_format = OutputFormat[getattr(stg,'REPORT_FORMAT')] if hasattr(stg,'REPORT_FORMAT') else OutputFormat.json
    payload,class_name = normalize_output(payload_data,report_format)

    extended_params = ctx.configs.get("extended_params")
    if extended_params is not None:
        if ctx.metadata is None: # inspect
            part = extended_params.part
            payload_len = len(payload)
            if payload_len > MAX_SPLITTABLE_OUTPUT_SIZE and part is not None:
                if part >= 0:
                    startb = MAX_SPLITTABLE_OUTPUT_SIZE*(part)
                    endb = MAX_SPLITTABLE_OUTPUT_SIZE*(part+1)
                    payload = payload[startb:endb]
                    if endb < payload_len: payload += b'0'

    if len(payload) > MAX_AGGREGATED_OUTPUT_SIZE:
        LOGGER.warn("Payload Data exceed maximum length. Truncating")
    payload = payload[:MAX_AGGREGATED_OUTPUT_SIZE]

    # For inspects always chunk if len > MAX_OUTPUT_SIZE, for advance raise error
    if ctx.metadata is not None and len(payload) > MAX_OUTPUT_SIZE:
        raise Exception("Maximum report length violation")

    tags = kwargs.get('tags')
    add_idx = ctx.metadata is not None and stg is not None \
        and hasattr(stg,'INDEX_OUTPUTS') and getattr(stg,'INDEX_OUTPUTS')

    sent_bytes = 0
    while sent_bytes < len(payload):
        inds = f" ({ctx.metadata.input_index}, {ctx.n_reports})" if ctx.metadata is not None else ""
        top_bytes = sent_bytes + MAX_OUTPUT_SIZE
        if top_bytes > len(payload):
            top_bytes = len(payload)
        
        if Output.add_output_index is not None and add_idx:
            splited_class_name = class_name.split('.')[-1]
            LOGGER.debug(f"Adding index report{inds} {tags=}")
            index_kwargs = {}
            if kwargs.get('value') is not None: index_kwargs['value'] = kwargs['value']
            Output.add_output_index(ctx.metadata,ctx.dapp_address,IOType.report,ctx.n_reports,ctx.module,splited_class_name,tags,**index_kwargs)

        LOGGER.debug(f"Sending report{inds} {top_bytes - sent_bytes} bytes")
        ctx.rollup.report(bytes2hex(payload[sent_bytes:top_bytes]))
        ctx.n_reports += 1
        sent_bytes = top_bytes
    

def send_notice(payload_data, **kwargs):
    ctx = Context

    if ctx.module in Output.disabled_modules:
        LOGGER.debug(f"Skipping notice: disabled {ctx.module} module")
        return

    stg = Setting.settings.get(ctx.module)

    notice_format = OutputFormat[getattr(stg,'NOTICE_FORMAT')] if hasattr(stg,'NOTICE_FORMAT') else OutputFormat.abi
    payload,class_name = normalize_output(payload_data,notice_format)

    if len(payload) > MAX_OUTPUT_SIZE: raise Exception("Maximum output length violation")

    tags = kwargs.get('tags')

    inds = f" ({ctx.metadata.input_index}, {ctx.n_notices})" if ctx.metadata is not None else ""
    if Output.add_output_index is not None and ctx.metadata is not None and stg is not None and hasattr(stg,'INDEX_OUTPUTS') and getattr(stg,'INDEX_OUTPUTS'):
        LOGGER.debug(f"Adding index notice{inds} {tags=}")
        splited_class_name = class_name.split('.')[-1]
        index_kwargs = {}
        if kwargs.get('value') is not None: index_kwargs['value'] = kwargs['value']
        Output.add_output_index(ctx.metadata,ctx.dapp_address,IOType.notice,ctx.n_notices,ctx.module,splited_class_name,tags,**index_kwargs)

    LOGGER.debug(f"Sending notice{inds} {len(payload)} bytes")
    ctx.rollup.notice(bytes2hex(payload))
    ctx.n_notices += 1

def send_voucher(destination: str, *kargs, **kwargs):
    payload,class_name = normalize_voucher(*kargs)

    if len(payload) > MAX_OUTPUT_SIZE: raise Exception("Maximum output length violation")

    ctx = Context

    if ctx.module in Output.disabled_modules:
        LOGGER.debug(f"Skipping voucher: disabled {ctx.module} module")
        return

    stg = Setting.settings.get(ctx.module)
    tags = kwargs.get('tags')
    inds = f" ({ctx.metadata.input_index}, {ctx.n_vouchers})" if ctx.metadata is not None else ""
    if Output.add_output_index is not None and ctx.metadata is not None and stg is not None and hasattr(stg,'INDEX_OUTPUTS') and getattr(stg,'INDEX_OUTPUTS'):
        LOGGER.debug(f"Adding index voucher{inds} {tags=}")
        splited_class_name = class_name.split('.')[-1]
        index_kwargs = {}
        if kwargs.get('value') is not None: index_kwargs['value'] = kwargs['value']
        Output.add_output_index(ctx.metadata,ctx.dapp_address,IOType.voucher,ctx.n_vouchers,ctx.module,splited_class_name,tags,**index_kwargs)

    LOGGER.debug(f"Sending voucher{inds}")
    ctx.rollup.voucher({"destination":destination,"payload":bytes2hex(payload)})
    ctx.n_vouchers += 1


# Aliases
output = report
event = notice
contract_call = voucher

add_output = send_report
emit_event = send_notice
submit_contract_call = send_voucher


def index_input(**kwargs):
    ctx = Context

    if ctx.module in Output.disabled_modules:
        LOGGER.debug(f"Skipping input index: disabled {ctx.module} module")
        return

    if ctx.set_input_indexes:
        raise Exception("Can't add input index multiple times")

    stg = Setting.settings.get(ctx.module)

    if not (Output.add_input_index is not None and ctx.metadata is not None \
            and stg is not None and hasattr(stg,'INDEX_OUTPUTS') and getattr(stg,'INDEX_OUTPUTS')):
        LOGGER.warning(f"Can't add index inputs: not enabled")
        return
        
    tags = kwargs.get('tags')

    inds = f" ({ctx.metadata.input_index})" if ctx.metadata is not None else ""
    LOGGER.debug(f"Adding index input{inds} {tags=}")
    class_name = ctx.input_payload.__class__.__name__
    index_kwargs = {}
    if kwargs.get('value') is not None: index_kwargs['value'] = kwargs['value']
    Output.add_input_index(ctx.metadata,ctx.dapp_address,ctx.module,class_name,tags,**index_kwargs)

    ctx.set_input_indexes = True
