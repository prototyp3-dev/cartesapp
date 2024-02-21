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
    return hex((val + right_bit) % right_bit)

def hex2562int(val):
    i = int(val,16)
    return i - (right_bit if i >> 255 == 1 else 0)

def uint2hex256(val):
    return hex(val)

def hex2562uint(val):
    return int(val,16)


###
# Helpers
