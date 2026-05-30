"""Unit tests for mutation/query registration in Manager.

Functions are fabricated with a dotted __module__ (so extract_module_name works)
and registered through the public decorator-backing ``add`` methods, then routed
with ``add_to_router=True`` against fresh router instances. No Pony binding and
no cartesi-machine are required.
"""
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from cartesi import abi, ABIRouter, URLRouter, JSONRouter
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.manager import Manager
from cartesapp.input import Mutation, Query
from cartesapp.setting import Setting


class MutPayload(BaseModel):
    n: abi.UInt256


class QueryPayload(BaseModel):
    name: str


def register_mutation(module, name, configs=None, params=1):
    if params == 0:
        def fn(): return True
    elif params == 1:
        def fn(payload: MutPayload): return True
    else:
        def fn(a: MutPayload, b: MutPayload): return True
    fn.__module__ = f"{module}.file"
    fn.__name__ = name
    Mutation.add(fn, **(configs or {}))
    return fn


def register_query(module, name, configs=None, params=1):
    if params == 0:
        def fn(): return True
    elif params == 1:
        def fn(payload: QueryPayload): return True
    else:
        def fn(a: QueryPayload, b: QueryPayload): return True
    fn.__module__ = f"{module}.file"
    fn.__name__ = name
    Query.add(fn, **(configs or {}))
    return fn


def set_query_format(module, fmt):
    Setting.settings[module] = SimpleNamespace(QUERY_FORMAT=fmt)


class TestMutationRegistration:
    def test_computed_header_attached_to_router(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "do_thing")
        Manager._register_mutations(True)

        assert "mymod.do_thing" in Manager.mutations_info
        ops = Manager.abi_router.advance_ops
        assert len(ops) == 1
        expected = ABIFunctionSelectorHeader(
            function="mymod.do_thing",
            argument_types=abi.get_abi_types_from_model(MutPayload),
        ).to_bytes()
        assert ops[0].header_bytes == expected

    def test_no_module_header_uses_bare_function_name(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "bare", {"no_module_header": True})
        Manager._register_mutations(True)
        expected = ABIFunctionSelectorHeader(
            function="bare",
            argument_types=abi.get_abi_types_from_model(MutPayload),
        ).to_bytes()
        assert Manager.abi_router.advance_ops[0].header_bytes == expected

    def test_fixed_header_is_routed(self):
        """Regression lock for the fixed_header fix: previously the literal header
        was never attached, so the handler matched every advance input."""
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "fixed_fn", {"fixed_header": "0xdeadbeef"})
        Manager._register_mutations(True)
        ops = Manager.abi_router.advance_ops
        assert ops[0].header_bytes == bytes.fromhex("deadbeef")

    def test_fixed_header_bytes(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "fixed_b", {"fixed_header": b"\x01\x02\x03\x04"})
        Manager._register_mutations(True)
        assert Manager.abi_router.advance_ops[0].header_bytes == b"\x01\x02\x03\x04"

    def test_no_header_matches_without_selector(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "nh", {"no_header": True})
        Manager._register_mutations(True)
        assert Manager.abi_router.advance_ops[0].header_bytes is None

    def test_disabled_endpoint_is_skipped(self):
        Manager.abi_router = ABIRouter()
        Manager.disabled_endpoints = ["mymod.skip"]
        register_mutation("mymod", "skip")
        Manager._register_mutations(True)
        assert "mymod.skip" not in Manager.mutations_info
        assert len(Manager.abi_router.advance_ops) == 0

    def test_duplicate_selector_raises(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "a", {"fixed_header": "0x11111111"})
        register_mutation("mymod", "b", {"fixed_header": "0x11111111"})
        with pytest.raises(Exception, match="Duplicate mutation selector"):
            Manager._register_mutations(True)

    def test_too_many_params_raises(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "two", params=2)
        with pytest.raises(Exception, match="more than one parameter"):
            Manager._register_mutations(True)

    def test_proxy_clones_model_and_sets_msg_sender(self):
        Manager.abi_router = ABIRouter()
        proxy_addr = "0x" + "ab" * 20
        register_mutation("mymod", "prox", {"proxy": proxy_addr})
        Manager._register_mutations(True)
        info = Manager.mutations_info["mymod.prox"]
        assert info["model"].__name__.endswith("Proxy")
        assert Manager.abi_router.advance_ops[0].msg_sender == proxy_addr.lower()

    def test_proxy_with_msg_sender_conflict_raises(self):
        Manager.abi_router = ABIRouter()
        register_mutation("mymod", "bad", {"proxy": "0x" + "ab" * 20, "msg_sender": "0x" + "cd" * 20})
        with pytest.raises(Exception, match="Can't use proxy with msg_sender"):
            Manager._register_mutations(True)

    def test_explicit_msg_sender_filter(self):
        Manager.abi_router = ABIRouter()
        sender = "0x" + "ee" * 20
        register_mutation("mymod", "filtered", {"msg_sender": sender})
        Manager._register_mutations(True)
        assert Manager.abi_router.advance_ops[0].msg_sender == sender.lower()


class TestQueryRegistration:
    def setup_routers(self):
        Manager.url_router = URLRouter()
        Manager.json_router = JSONRouter()

    def test_url_query(self):
        self.setup_routers()
        set_query_format("qmod", "url")
        register_query("qmod", "my_query")
        Manager._register_queries(True)
        info = Manager.queries_info["qmod.my_query"]
        assert info["query_type"] == "queryUrlPayload"
        assert info["selector"] == "qmod/my_query"
        assert any(r.path == "qmod/my_query" for r in Manager.url_router.routes)

    def test_url_query_with_path_params(self):
        self.setup_routers()
        set_query_format("qmod", "url")
        register_query("qmod", "by_id", {"path_params": ["name"]})
        Manager._register_queries(True)
        assert Manager.queries_info["qmod.by_id"]["selector"] == "qmod/by_id/{name}"

    def test_jsonrpc_query_selector(self):
        self.setup_routers()
        set_query_format("qmod", "jsonrpc")
        register_query("qmod", "get_thing")
        Manager._register_queries(True)
        info = Manager.queries_info["qmod.get_thing"]
        assert info["query_type"] == "queryJsonrpcPayload"
        assert info["selector"] == "qmod_getThing"

    def test_default_is_json_query(self):
        self.setup_routers()
        # no QUERY_FORMAT configured for the module -> json
        register_query("qmod", "plain")
        Manager._register_queries(True)
        info = Manager.queries_info["qmod.plain"]
        assert info["query_type"] == "queryJsonPayload"
        assert info["selector"] == "qmod_plain"

    def test_too_many_params_raises(self):
        self.setup_routers()
        register_query("qmod", "two", params=2)
        with pytest.raises(Exception, match="more than one parameter"):
            Manager._register_queries(True)

    def test_disabled_endpoint_is_skipped(self):
        self.setup_routers()
        Manager.disabled_endpoints = ["qmod.hidden"]
        register_query("qmod", "hidden")
        Manager._register_queries(True)
        assert "qmod.hidden" not in Manager.queries_info

    def test_duplicate_url_selector_raises(self):
        self.setup_routers()
        set_query_format("qmod", "url")
        register_query("qmod", "dup")
        register_query("qmod", "dup")
        with pytest.raises(Exception, match="Duplicate query selector"):
            Manager._register_queries(True)
