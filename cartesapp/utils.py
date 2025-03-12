from pydantic import BaseModel

###
# Consts

right_bit = (1 << 256)

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

###
# Models

class EmptyClass(BaseModel):
    pass
