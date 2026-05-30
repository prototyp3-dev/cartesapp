"""Unit tests for the per-format input decode strategies (cartesapp.input).

These cover the pure functions extracted from the request wrappers:
_decode_advance_payload (ABI), _decode_url_params (URL), _decode_json_request
(JSON/JSON-RPC), plus the mutation/query persistence policies.
"""
from typing import List, Optional

import pytest
from pydantic import BaseModel, create_model

from cartesi import abi, URLParameters
from cartesi.models import RollupMetadata

from cartesapp import input as cinput
from cartesapp.input import (
    _decode_advance_payload, _decode_url_params, _decode_json_request,
    _finalize_mutation, _finalize_query,
)
from cartesapp.context import Context
from cartesapp.utils import InputFormat


class AdvancePayload(BaseModel):
    value: abi.UInt256
    data: abi.Bytes


class UrlQuery(BaseModel):
    name: str
    tags: Optional[List[str]] = None


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


class TestDecodeAdvancePayload:
    def test_no_header_decodes_full_payload(self):
        payload = abi.encode_model(AdvancePayload(value=5, data=b"hi"))
        out = _decode_advance_payload(payload, AdvancePayload, True, {})
        assert out[0].value == 5
        assert out[0].data == b"hi"

    def test_header_offset_is_stripped(self):
        payload = abi.encode_model(AdvancePayload(value=9, data=b"x"))
        framed = b"\xaa\xbb\xcc\xdd" + payload
        out = _decode_advance_payload(framed, AdvancePayload, True, {"has_header": True})
        assert out[0].value == 9

    def test_no_param_returns_empty(self):
        out = _decode_advance_payload(b"", AdvancePayload, False, {})
        assert out == []

    def test_packed_roundtrip(self):
        m = AdvancePayload(value=3, data=b"ab")
        packed = abi.encode_model(m, True)
        out = _decode_advance_payload(packed, AdvancePayload, True, {"packed": True})
        assert out[0].value == 3 and out[0].data == b"ab"

    def test_proxy_overrides_msg_sender(self):
        Context.metadata = make_metadata()
        addr = bytes.fromhex("11" * 20)
        payload = abi.encode_model(AdvancePayload(value=1, data=b"z"))
        out = _decode_advance_payload(addr + payload, AdvancePayload, True, {"has_proxy": True})
        assert Context.metadata.msg_sender == "0x" + "11" * 20
        assert out[0].value == 1

    def test_proxy_with_header_offset(self):
        Context.metadata = make_metadata()
        addr = bytes.fromhex("22" * 20)
        payload = abi.encode_model(AdvancePayload(value=2, data=b"y"))
        framed = b"\x00\x00\x00\x00" + addr + payload
        out = _decode_advance_payload(framed, AdvancePayload, True, {"has_header": True, "has_proxy": True})
        assert Context.metadata.msg_sender == "0x" + "22" * 20
        assert out[0].value == 2

    def test_proxy_short_payload_raises(self):
        """Safe fix: a truncated proxy payload must not silently yield a
        malformed/empty msg_sender."""
        Context.metadata = make_metadata()
        short = bytes.fromhex("33" * 10)  # only 10 bytes, need 20
        with pytest.raises(Exception, match="too short"):
            _decode_advance_payload(short, AdvancePayload, True, {"has_proxy": True})


class TestDecodeUrlParams:
    def test_scalar_query_param(self):
        params = URLParameters(path_params={}, query_params={"name": ["alice"]})
        out = _decode_url_params(UrlQuery, params, {})
        assert out[0].name == "alice"

    def test_list_query_param(self):
        params = URLParameters(path_params={}, query_params={"name": ["a"], "tags": ["x", "y"]})
        out = _decode_url_params(UrlQuery, params, {})
        assert out[0].tags == ["x", "y"]

    def test_path_param(self):
        class PathQ(BaseModel):
            id: str
        params = URLParameters(path_params={"id": "42"}, query_params={})
        out = _decode_url_params(PathQ, params, {})
        assert out[0].id == "42"

    def test_extended_splittable_param(self):
        ext = create_model("UrlQuerySplittable", part=(int, None), __base__=UrlQuery)
        func_configs = {"extended_model": ext}
        params = URLParameters(path_params={}, query_params={"name": ["x"], "part": ["2"]})
        out = _decode_url_params(UrlQuery, params, func_configs)
        assert out[0].name == "x"
        assert func_configs["extended_params"].part == 2


class TestDecodeJsonRequest:
    def test_json_dict_params(self):
        fc = {}
        out = _decode_json_request(
            UrlQuery, True, {"method": "m", "params": {"name": "a", "tags": ["t"]}}, fc)
        assert out[0].name == "a" and out[0].tags == ["t"]
        assert fc["query_format"] == InputFormat.json

    def test_jsonrpc_list_params_and_id(self):
        fc = {}
        out = _decode_json_request(
            UrlQuery, True,
            {"jsonrpc": "2.0", "id": 9, "method": "m", "params": ["a", ["t"]]}, fc)
        assert fc["query_format"] == InputFormat.jsonrpc
        assert fc["id"] == 9
        assert out[0].name == "a" and out[0].tags == ["t"]

    def test_jsonrpc_missing_id_raises(self):
        with pytest.raises(Exception, match="Missing id"):
            _decode_json_request(UrlQuery, True, {"jsonrpc": "2.0", "method": "m"}, {})

    def test_scalar_params_single_field(self):
        class Single(BaseModel):
            val: str
        fc = {}
        out = _decode_json_request(Single, True, {"method": "m", "params": "hello"}, fc)
        assert out[0].val == "hello"

    def test_extended_splittable_list_params(self):
        ext = create_model("UrlQuerySplittable2", part=(int, None), __base__=UrlQuery)
        fc = {"extended_model": ext}
        out = _decode_json_request(
            UrlQuery, True, {"method": "m", "params": ["x", ["t"], 5]}, fc)
        assert out[0].name == "x"
        assert fc["extended_params"].part == 5

    def test_no_param_still_sets_query_format(self):
        fc = {}
        out = _decode_json_request(UrlQuery, False, {"method": "m"}, fc)
        assert out == []
        assert fc["query_format"] == InputFormat.json


class TestPersistencePolicies:
    def test_mutation_commits_on_truthy(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cinput.helpers, "commit", lambda: calls.append("commit"))
        monkeypatch.setattr(cinput.helpers, "rollback", lambda: calls.append("rollback"))
        monkeypatch.setattr(cinput.os, "sync", lambda: calls.append("sync"))
        _finalize_mutation(True)
        assert calls == ["commit", "sync"]

    def test_mutation_rolls_back_on_falsy(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cinput.helpers, "commit", lambda: calls.append("commit"))
        monkeypatch.setattr(cinput.helpers, "rollback", lambda: calls.append("rollback"))
        monkeypatch.setattr(cinput.os, "sync", lambda: calls.append("sync"))
        _finalize_mutation(False)
        assert calls == ["rollback"]

    def test_query_always_rolls_back(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cinput.helpers, "rollback", lambda: calls.append("rollback"))
        _finalize_query()
        assert calls == ["rollback"]
