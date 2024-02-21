
from cartesi import Rollup, RollupData, RollupMetadata


###
# Context

class Context(object):
    rollup: Rollup | None = None
    metadata: RollupMetadata | None = None
    module: str | None = None
    n_reports: int = 0
    n_notices: int = 0
    n_vouchers: int = 0
    configs = None
    dapp_address: str | None = None


    def __new__(cls):
        return cls
    
    @classmethod
    def set_context(cls, rollup: Rollup, metadata: RollupMetadata, module: str, **kwargs):
        cls.rollup = rollup
        cls.metadata = metadata
        cls.module = module
        cls.n_reports = 0
        cls.n_notices = 0
        cls.n_vouchers = 0
        cls.configs = kwargs

    @classmethod
    def clear_context(cls):
        cls.rollup = None
        cls.metadata = None
        cls.module = None
        cls.n_reports: 0
        cls.n_notices = 0
        cls.n_vouchers = 0
        cls.configs = None


###
# Helpers

def get_metadata() -> RollupMetadata:
    return Context.metadata

def get_dapp_address() -> str | None:
    return Context.dapp_address
