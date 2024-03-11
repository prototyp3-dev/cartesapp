import pony.orm
import logging
from enum import Enum
from typing import Optional, List
import os

from cartesi.abi import String, Bytes, Int, UInt


helpers = pony.orm


###
# Storage

class Storage:
    db = pony.orm.Database()
    seeds = []
    STORAGE_PATH = None
    
    def __new__(cls):
        return cls
    
    @classmethod
    def initialize_storage(cls):
        filename = ":memory:"
        if cls.STORAGE_PATH is not None:
            if not os.path.isabs(cls.STORAGE_PATH):
                cls.STORAGE_PATH = f"{os.getcwd()}/{cls.STORAGE_PATH}"
            uname = os.uname()
            if 'ctsi' in uname.release and uname.machine == 'riscv64':
                cls.STORAGE_PATH += '/mnt'
            filename = f"{cls.STORAGE_PATH}/storage.db"
            if not os.path.exists(cls.STORAGE_PATH):
                os.makedirs(cls.STORAGE_PATH)
        if logging.root.level <= logging.DEBUG:
            pony.orm.set_sql_debug(True)
        cls.db.bind(provider="sqlite", filename=filename, create_db=True)
        # cls.db.provider.converter_classes.append((Enum, EnumConverter))
        cls.db.generate_mapping(create_tables=True)
        for s in cls.seeds: s()

    @classmethod
    def add_seed(cls, func):
        cls.seeds.append(_make_seed_function(func))

def _make_seed_function(f):
    @helpers.db_session
    def seed_func():
        f()
    return seed_func

# TODO: allow ordering
def seed(**kwargs):
    def decorator(func):
        Storage.add_seed(func)
        return func
    return decorator


Entity = Storage.db.Entity

