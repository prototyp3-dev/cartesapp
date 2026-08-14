import os
FILES = ['fee'] # * Required

STORAGE_PATH = 'data'

ENABLE_LEDGER = True

NOTICE_FORMAT = "header_abi"

LEDGER_CONFIG = {
    "mem_file": os.getenv('LEDGER_FILE') or "/dev/uio0",
    "memory_size": 67108864,
    "max_accounts": 16384,
    "max_assets": 8,
    "max_balances": 131072,
    # "offset": 0,
    "ether_portal_address": "0x00000000000000000000000000000000000e73e9",
    "erc20_portal_address": "0x00000000000000000000000000000000000e9c20",
    "erc721_portal_address": "0x0000000000000000000000000000000000e9c721",
    "erc1155_single_portal_address": "0x00000000000000000000000000000000e9c1155a",
    "erc1155_batch_portal_address": "0x00000000000000000000000000000000e9c1155b",
}
