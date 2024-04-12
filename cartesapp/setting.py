

# Settings
class Setting:
    settings = {}
    def __new__(cls):
        return cls
    
    @classmethod
    def add(cls, mod):
        cls.settings[mod.__name__.split('.')[0]] = mod

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

# Enable endpoint to get address from Dapp relay contract
# ENABLE_DAPP_RELAY = False

# Enable endpoint to accept portal deposits and also add withdraw and transfer endpoints
# ENABLE_WALLET = False # Defaul: False (required to set ENABLE_DAPP_RELAY)

# Path dir to database
# STORAGE_PATH = None

# Case insensitivity for like queries
# CASE_INSENSITIVITY_LIKE = False

# List of endpoints to disable (useful for cascading)
# DISABLED_ENDPOINTS = []

# List of modules to disable outputs  (useful for cascading)
# DISABLED_MODULE_OUTPUTS = []

# Output Formats
# REPORT_FORMAT = 'json'
# NOTICE_FORMAT = 'abi
'''