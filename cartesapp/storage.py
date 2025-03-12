import pony.orm
import logging
import os
import shutil

from cartesi.abi import String, Bytes, Int, UInt


helpers = pony.orm


###
# Storage

class Storage:
    db = pony.orm.Database()
    seeds = []
    STORAGE_PATH = None
    CASE_INSENSITIVITY_LIKE = None

    def __new__(cls):
        return cls

    @classmethod
    def initialize_storage(cls,reset_storage=False):
        filename = ":memory:"
        create_db = True
        if reset_storage:
            cls.db.provider = cls.db.schema = None
        if cls.STORAGE_PATH is not None:
            uname = os.uname()
            if 'ctsi' in uname.release and uname.machine == 'riscv64':
                cls.STORAGE_PATH = '/mnt/' + cls.STORAGE_PATH
            if not os.path.isabs(cls.STORAGE_PATH):
                cls.STORAGE_PATH = f"{os.getcwd()}/{cls.STORAGE_PATH}"
            if reset_storage and os.path.exists(cls.STORAGE_PATH):
                shutil.rmtree(cls.STORAGE_PATH)
            filename = f"{cls.STORAGE_PATH}/storage.db"
            if not os.path.exists(cls.STORAGE_PATH):
                os.makedirs(cls.STORAGE_PATH)
            elif os.path.exists(filename): create_db = False
        if logging.root.level <= logging.DEBUG:
            pony.orm.set_sql_debug(True)
        if cls.CASE_INSENSITIVITY_LIKE:
            @cls.db.on_connect(provider='sqlite')
            def sqlite_case_sensitivity(db, connection):
                cursor = connection.cursor()
                cursor.execute('PRAGMA case_sensitive_like = OFF')
        cls.db.bind(provider="sqlite", filename=filename, create_db=create_db)
        # cls.db.execute("PRAGMA journal_mode = OFF;")
        # cls.db.provider.converter_classes.append((Enum, EnumConverter))
        cls.db.generate_mapping(create_tables=create_db)
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
