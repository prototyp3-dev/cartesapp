"""End-to-end lifecycle tests driven with plain pytest (no TestClient / MockRollup).

These bind a real in-memory Pony database and run the actual request wrappers
(_make_mut / _make_url_query) against a fake rollup, exercising the persistence
policy that the refactor centralized: a mutation commits its DB writes only when
it returns a truthy value, and rolls back otherwise (including on exceptions),
while queries always roll back. Outputs are captured via the fake rollup.
"""
import pytest
from pydantic import BaseModel

from cartesi import abi, URLParameters
from cartesi.models import RollupMetadata, RollupData

from cartesapp.storage import Storage, Entity, helpers
from cartesapp.input import _make_mut, _make_url_query
from cartesapp.output import add_output
from cartesapp.utils import bytes2hex


MODULE = "sample"


class Counter(Entity):
    key = helpers.PrimaryKey(str)
    value = helpers.Required(int)


class CounterInput(BaseModel):
    key: abi.String
    value: abi.UInt256


class CounterQuery(BaseModel):
    key: abi.String


class FakeRollup:
    def __init__(self):
        self.reports = []
        self.notices = []
        self.vouchers = []

    def report(self, payload):
        self.reports.append(payload)

    def notice(self, payload):
        self.notices.append(payload)

    def voucher(self, payload):
        self.vouchers.append(payload)


@pytest.fixture(scope="session")
def storage():
    Storage.initialize_storage()  # in-memory sqlite + generate_mapping
    yield Storage.db


@pytest.fixture
def rollup():
    return FakeRollup()


def make_metadata():
    return RollupMetadata(
        chain_id=1,
        app_contract="0x" + "ab" * 20,
        msg_sender="0x" + "cd" * 20,
        input_index=0,
        block_number=1,
        block_timestamp=1,
        prev_randao="0x0",
    )


def advance_data(model: BaseModel):
    payload = bytes2hex(abi.encode_model(model))
    return RollupData(metadata=make_metadata(), payload=payload)


def get_counter(key):
    with helpers.db_session:
        c = Counter.get(key=key)
        return c.value if c is not None else None


# --- user-style handlers ---

def set_counter(payload: CounterInput):
    Counter(key=payload.key, value=payload.value)
    return True


def set_counter_no_commit(payload: CounterInput):
    Counter(key=payload.key, value=payload.value)
    return False  # framework must roll this back


def set_counter_raises(payload: CounterInput):
    Counter(key=payload.key, value=payload.value)
    raise ValueError("boom")


def read_counter(payload: CounterQuery):
    with helpers.db_session:
        c = Counter.get(key=payload.key)
    add_output(str(c.value) if c else "missing")
    return True


class TestMutationPersistence:
    def test_commit_on_true(self, storage, rollup):
        handler = _make_mut(set_counter, CounterInput, True, MODULE)
        result = handler(rollup, advance_data(CounterInput(key="a", value=11)))
        assert result is True
        assert get_counter("a") == 11

    def test_rollback_on_false(self, storage, rollup):
        handler = _make_mut(set_counter_no_commit, CounterInput, True, MODULE)
        result = handler(rollup, advance_data(CounterInput(key="b", value=22)))
        assert result is False
        assert get_counter("b") is None  # write was rolled back

    def test_rollback_on_exception(self, storage, rollup):
        handler = _make_mut(set_counter_raises, CounterInput, True, MODULE)
        result = handler(rollup, advance_data(CounterInput(key="c", value=33)))
        assert result is False  # exception swallowed, status False
        assert get_counter("c") is None  # write was rolled back


class TestQueryLifecycle:
    def test_query_emits_report_for_committed_data(self, storage, rollup):
        # seed via a committing mutation
        mut = _make_mut(set_counter, CounterInput, True, MODULE)
        mut(rollup, advance_data(CounterInput(key="d", value=44)))

        query = _make_url_query(read_counter, CounterQuery, True, MODULE)
        params = URLParameters(path_params={}, query_params={"key": ["d"]})
        result = query(rollup, params)
        assert result is True
        assert len(rollup.reports) == 1
        # report payload is hex of the ascii value "44"
        assert rollup.reports[-1] == bytes2hex(b"44")

    def test_query_missing_key(self, storage, rollup):
        query = _make_url_query(read_counter, CounterQuery, True, MODULE)
        params = URLParameters(path_params={}, query_params={"key": ["nope"]})
        result = query(rollup, params)
        assert result is True
        assert rollup.reports[-1] == bytes2hex(b"missing")
