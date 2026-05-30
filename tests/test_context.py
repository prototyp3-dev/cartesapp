"""Unit tests for the request Context singleton (cartesapp.context)."""
import pytest
from pydantic import BaseModel

from cartesi.models import RollupMetadata

from cartesapp.context import Context, get_metadata, get_rollup, get_app_contract


def make_metadata(**overrides):
    base = dict(
        chain_id=1,
        app_contract="0xapp0000000000000000000000000000000000000",
        msg_sender="0xsender00000000000000000000000000000000000",
        input_index=0,
        block_number=1,
        block_timestamp=1,
        prev_randao="0x0",
    )
    base.update(overrides)
    return RollupMetadata(**base)


class FakeRollup:
    pass


class TestContextLifecycle:
    def test_set_and_clear(self):
        rollup = FakeRollup()
        md = make_metadata()
        Context.set_context(rollup, md, "mymod", query_format="abi")
        assert Context.rollup is rollup
        assert Context.metadata is md
        assert Context.module == "mymod"
        assert Context.configs == {"query_format": "abi"}

        Context.clear_context()
        assert Context.rollup is None
        assert Context.metadata is None
        assert Context.module is None
        assert Context.configs is None

    def test_set_input(self):
        class P(BaseModel):
            x: int
        p = P(x=3)
        Context.set_input(p)
        assert Context.input_payload is p

    def test_get_metadata_raises_without_advance(self):
        Context.clear_context()
        with pytest.raises(Exception, match="No metadata"):
            get_metadata()

    def test_get_rollup_and_app_contract_accessors(self):
        rollup = FakeRollup()
        Context.set_context(rollup, make_metadata(), "m")
        assert get_rollup() is rollup
        # app_contract accessor returns whatever Context holds
        assert get_app_contract() == Context.app_contract


class TestAppContract:
    """app_contract is populated once from the first advance's metadata and then
    kept (set-once / lambda-state semantics)."""

    def test_set_from_metadata_on_advance(self):
        Context.reset()
        md = make_metadata()
        Context.set_context(FakeRollup(), md, "m")
        assert Context.app_contract == md.app_contract
        assert get_app_contract() == md.app_contract

    def test_persists_into_following_inspect(self):
        Context.reset()
        md = make_metadata()
        Context.set_context(FakeRollup(), md, "m")  # advance
        Context.clear_context()
        Context.set_context(FakeRollup(), None, "m")  # inspect, no metadata
        assert Context.app_contract == md.app_contract

    def test_not_overwritten_by_later_advance(self):
        Context.reset()
        first = make_metadata()
        Context.set_context(FakeRollup(), first, "m")
        Context.clear_context()
        later = make_metadata(app_contract="0x" + "ff" * 20)
        Context.set_context(FakeRollup(), later, "m")
        assert Context.app_contract == first.app_contract  # set-once: frozen

    def test_reset_clears_app_contract(self):
        Context.set_context(FakeRollup(), make_metadata(), "m")
        Context.reset()
        assert Context.app_contract is None


class TestContextCounters:
    def test_report_counters_increment_together(self):
        Context.reset()
        Context.inc_reports()
        Context.inc_reports()
        assert Context.n_reports == 2
        assert Context.n_input_reports == 2

    def test_notice_voucher_counters_feed_n_outputs(self):
        Context.reset()
        Context.inc_notices()
        Context.inc_vouchers()
        Context.inc_delegate_call_vouchers()
        assert Context.n_notices == 1
        assert Context.n_vouchers == 1
        assert Context.n_delegate_call_vouchers == 1
        assert Context.n_outputs == 3

    def test_clear_context_resets_only_report_counters(self):
        """clear_context() zeroes the per-input report counters but intentionally
        NOT n_notices/n_vouchers/n_outputs: n_outputs is the GLOBAL output index
        (Rollups 2.0 outputs Merkle tree) and must persist across inputs so voucher
        execution proofs line up with the node. Reports are per-input."""
        Context.reset()
        Context.inc_reports()
        Context.inc_notices()
        Context.clear_context()
        assert Context.n_reports == 0          # reset by clear_context
        assert Context.n_notices == 1          # NOT reset by clear_context
        assert Context.n_outputs == 1          # NOT reset by clear_context

    def test_reset_zeroes_all_counters(self):
        Context.inc_notices()
        Context.inc_reports()
        Context.reset()
        assert Context.n_notices == 0
        assert Context.n_outputs == 0
        assert Context.n_reports == 0
