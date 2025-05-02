from .utils import get_module_name

# Settings
class Setting:
    settings = {}
    def __new__(cls):
        return cls

    @classmethod
    def add(cls, mod):
        cls.settings[get_module_name(mod)] = mod

# def setting(**kwargs):
#     def decorator(klass):
#         Setting.add(klass)
#         return klass
#     return decorator

SETTINGS_TEMPLATE = '''
# Cartesapp Framework settings

# Files with definitions to import
FILES = [] # * Required

# Index outputs in inspect indexer queries
# INDEX_OUTPUTS = False

# Index inputs in inspect indexer queries
# INDEX_INPUTS = False

# Enable endpoint to accept portal deposits and also add withdraw and transfer endpoints
# ENABLE_WALLET = False # Defaul: False

# Path dir to database
# STORAGE_PATH = None

# Case insensitivity for like queries
# CASE_INSENSITIVITY_LIKE = False

# List of endpoints to disable (useful for cascading)
# DISABLED_ENDPOINTS = []

# List of modules to disable outputs  (useful for cascading)
# DISABLED_MODULE_OUTPUTS = []

# Input Formats
# QUERY_FORMAT = 'json' # 'url', 'json', 'jsonrpc'

# Output Formats
# REPORT_FORMAT = 'json'
# NOTICE_FORMAT = 'abi
'''
