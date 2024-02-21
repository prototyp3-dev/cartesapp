

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
