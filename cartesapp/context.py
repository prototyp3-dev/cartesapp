from cartesi import Rollup, RollupMetadata
from pydantic import BaseModel


###
# Context

class Context(object):
    rollup: Rollup | None = None
    metadata: RollupMetadata | None = None
    module: str | None = None
    n_input_reports: int = 0
    n_reports: int = 0
    n_notices: int = 0
    n_vouchers: int = 0
    n_delegate_call_vouchers: int = 0
    n_outputs: int = 0
    configs = None
    app_contract: str | None = None
    input_payload: BaseModel | None = None
    set_input_indexes: bool = False

    def __new__(cls):
        return cls

    @classmethod
    def set_context(cls, rollup: Rollup, metadata: RollupMetadata | None, module: str, **kwargs):
        cls.rollup = rollup
        cls.metadata = metadata
        # TODO: change this when migrating to lambda state
        if cls.app_contract is not None and metadata is not None:
            cls.app_contract = metadata.app_contract
        cls.module = module
        cls.n_reports = 0
        cls.n_input_reports = 0
        cls.configs = kwargs

    @classmethod
    def set_input(cls, input_payload: BaseModel):
        cls.input_payload = input_payload

    @classmethod
    def clear_context(cls):
        cls.rollup = None
        cls.metadata = None
        cls.module = None
        cls.n_reports= 0
        cls.n_input_reports = 0
        cls.configs = None
        cls.input_payload = None
        cls.set_input_indexes = False

    @classmethod
    def inc_reports(cls):
        cls.n_reports += 1
        cls.n_input_reports += 1

    @classmethod
    def inc_notices(cls):
        cls.n_notices += 1
        cls.n_outputs += 1

    @classmethod
    def inc_vouchers(cls):
        cls.n_vouchers += 1
        cls.n_outputs += 1

    @classmethod
    def inc_delegate_call_vouchers(cls):
        cls.n_delegate_call_vouchers += 1
        cls.n_outputs += 1

###
# Helpers

def get_metadata() -> RollupMetadata:
    if Context.metadata is None:
        raise Exception("No metadata (inspects don't have metadata)")
    return Context.metadata

def get_app_contract() -> str | None:
    return Context.app_contract
