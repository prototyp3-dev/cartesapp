FILES = ['fee'] # * Required

STORAGE_PATH = 'data'

ENABLE_LEDGER = True

NOTICE_FORMAT = "header_abi"

LEDGER_CONFIG = {
    "mem_file": "/dev/pmem2",
    "memory_size": 67108864,
    "max_accounts": 16384,
    "max_assets": 8,
    "max_balances": 131072,
    # "offset": 0,
}
