from cartesapp.utils import get_module_name

# Settings
class Setting:
    settings = {}
    def __new__(cls):
        return cls

    @classmethod
    def add(cls, mod):
        cls.settings[get_module_name(mod)] = mod
