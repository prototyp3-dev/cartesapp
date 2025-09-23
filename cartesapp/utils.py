import os
from pydantic import BaseModel
import re
from enum import Enum

###
# Consts

right_bit = (1 << 256)

DEFAULT_CONFIGFILE = 'cartesi.toml'

DEFAULT_CONFIGS = {
    "machine":{
        "entrypoint":"rollup-init /usr/local/bin/run_cartesapp",
        "assert_rolling_template":"true",
        "final_hash":"true"
    },
    "drives":{
        "root": {
            "builder":"none",
            "filename":".cartesi/root.ext2",
        },
        "app":{
            "builder": "directory",
            "directory":".",
            "format":"sqfs",
        }
    }
}

SHELL_CONFIGS = {
    "machine":{
        "entrypoint":"sh",
        "network":"true",
    },
    "drives":{
        "root": {
            "builder":"none",
            "filename":".cartesi/root.ext2",
            "shared":"true"
        },
        "app":{
            "builder": "volume",
            "directory":"."
        }
    }
}

###
# Conversion Functions

def hex2bytes(hexstr):
    if hexstr.startswith('0x'):
        hexstr = hexstr[2:]
    return bytes.fromhex(hexstr)

def bytes2str(binstr):
    return binstr.decode("utf-8")

def hex2str(hexstr):
    return bytes2str(hex2bytes(hexstr))

def bytes2hex(value):
    return "0x" + value.hex()

def str2bytes(strtxt):
    return strtxt.encode("utf-8")

def str2hex(strtxt):
    return bytes2hex(str2bytes(strtxt))

def int2hex256(val):
    return f"0x{hex((val + right_bit) % right_bit)[2:].rjust(64,"0")}"

def hex2562int(val):
    i = int(val,16)
    return i - (right_bit if i >> 255 == 1 else 0)

def uint2hex256(val):
    return hex(val)

def hex2562uint(val):
    return int(val,16)

def convert_camel_case(s, title_first = False):
    snaked = re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower()
    splitted = snaked.split('_')
    return (splitted[0] if not title_first else splitted[0].title()) + ''.join(i.title() for i in splitted[1:])

def str2bool(v):
    return str(v).lower() in ("yes", "true", "t", "1","y")


###
# Helpers

def get_modules(path='.',maxdepth=2,exclude=['tests']):
    import os, re

    pyfiles = []
    root_depth = path.rstrip(os.path.sep).count(os.path.sep) - 1
    for root, dirs, files in os.walk(path, topdown=True):
        depth = root.count(os.path.sep) - root_depth
        dirs[:] = [d for d in dirs if d not in exclude and not d.startswith('.')]
        if depth > maxdepth:
            dirs[:] = []
            continue
        for file in files:
            if file.endswith(".py"):
                pyfiles.append(os.path.join(root, file))
    return list(set(map(lambda f: re.sub('/[^/]+$|^./','',f).replace('/','.'),pyfiles)))

def get_function_signature(func) -> tuple[str,str]:
    func_name = func.__name__
    original_module_name = extract_module_name(func.__module__)
    return original_module_name,func_name

def get_class_name(data) -> tuple[str,str]:
    return get_function_signature(data.__class__)

def get_module_name(mod) -> str:
    return extract_module_name(mod.__name__)

def extract_module_name(mod_name) -> str:
    return mod_name.split('.')[-2]

def fix_import_path(libpath):
    import os,sys
    libabsdir = os.path.abspath(libpath)
    sys.path.insert(0,libabsdir)

def get_script_dir():
    import os,inspect
    currentdir = os.path.dirname(os.path.abspath(inspect.stack()[1].filename))
    return currentdir

def read_config_file(config_file: str | None = None):
    import tomllib, os
    if config_file is None:
        config_file = 'cartesi.toml'
    if not os.path.isfile(config_file): return {}
    with open(config_file, "rb") as f:
        return tomllib.load(f)

def deep_merge_dicts(dict1, dict2):
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result

def get_dir_size(path,exclude=[]):
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.name.startswith(tuple(exclude)):
                continue
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path,exclude)
    return total

###
# Models

class EmptyClass(BaseModel):
    pass

class IOType(Enum):
    report = 0
    notice = 1
    voucher = 2
    input = 3
    delegate_call_voucher = 3

class OutputFormat(Enum):
    abi = 0
    packed_abi = 1
    json = 2
    header_abi = 3

class InputFormat(Enum):
    abi = 0
    url = 1
    json = 2
    jsonrpc = 3
