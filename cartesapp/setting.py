

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
INDEX_OUTPUTS = False # Defaul: False

# Enable endpoint to get address from Dapp relay contract
ENABLE_DAPP_RELAY = False # Defaul: False

# Enable endpoint to accept portal deposits and also add withdraw and transfer endpoints
ENABLE_WALLET = False # Defaul: False (required to set ENABLE_DAPP_RELAY)

# Path dir to database
STORAGE_PATH = None # Defaul: False

# List of endpoints to disable (useful for cascading)
DISABLED_ENDPOINTS = [] # Defaul: []

# List of modules to disable outputs  (useful for cascading)
DISABLED_MODULE_OUTPUTS = [] # Defaul: []
'''