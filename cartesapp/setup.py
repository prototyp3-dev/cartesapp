from .storage import Storage, helpers

###
# Setup

class Setup:
    setup_functions = []
    post_setup_functions = []
    
    def __new__(cls):
        return cls
    
    @classmethod
    def add_setup(cls, func):
        cls.setup_functions.append(_make_setup_function(func))

    @classmethod
    def add_post_setup(cls, func):
        cls.post_setup_functions.append(_make_setup_function(func))

def _make_setup_function(f):
    @helpers.db_session
    def setup_func():
        f()
    return setup_func

def setup(**kwargs):
    def decorator(func):
        Setup.add_setup(func)
        return func
    return decorator

def post_setup(**kwargs):
    def decorator(func):
        Setup.add_post_setup(func)
        return func
    return decorator
