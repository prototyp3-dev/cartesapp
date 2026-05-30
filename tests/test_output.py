"""Unit tests for output normalization (cartesapp.output)."""
import base64
import json

import pytest
from pydantic import BaseModel

from cartesi import abi
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.output import (
    normalize_output, normalize_voucher, normalize_jsonrpc_output,
)
from cartesapp.utils import OutputFormat, str2bytes, hex2bytes


class SampleModel(BaseModel):
    n: abi.UInt256
    data: abi.Bytes


# extract_module_name() needs a dotted __module__; pytest imports test files as
# top-level modules, so patch it to a package-like value.
SampleModel.__module__ = "sample.models"


class TestNormalizeOutputScalars:
    def test_bytes_passthrough(self):
        assert normalize_output(b"\x01\x02", OutputFormat.json) == (b"\x01\x02", "bytes")

    def test_int_to_32_bytes(self):
        payload, name = normalize_output(5, OutputFormat.json)
        assert name == "int"
        assert payload == (5).to_bytes(32, "big")

    def test_plain_string(self):
        assert normalize_output("hello", OutputFormat.json) == (str2bytes("hello"), "str")

    def test_hex_string(self):
        payload, name = normalize_output("0xdeadbeef", OutputFormat.json)
        assert name == "hex"
        assert payload == hex2bytes("deadbeef")

    def test_dict_to_json(self):
        payload, name = normalize_output({"a": 1}, OutputFormat.json)
        assert name == "dict"
        assert json.loads(payload) == {"a": 1}

    def test_list_to_json(self):
        payload, name = normalize_output([1, 2, 3], OutputFormat.json)
        assert name == "list"
        assert json.loads(payload) == [1, 2, 3]


class TestNormalizeOutputModel:
    def test_abi_encoding(self):
        m = SampleModel(n=7, data=b"hi")
        payload, name = normalize_output(m, OutputFormat.abi)
        assert name == "sample.SampleModel"
        assert payload == abi.encode_model(m)

    def test_packed_abi_encoding(self):
        m = SampleModel(n=7, data=b"hi")
        payload, _ = normalize_output(m, OutputFormat.packed_abi)
        assert payload == abi.encode_model(m, True)

    def test_header_abi_prepends_selector(self):
        m = SampleModel(n=7, data=b"hi")
        payload, _ = normalize_output(m, OutputFormat.header_abi)
        header = ABIFunctionSelectorHeader(
            function="sample.SampleModel",
            argument_types=abi.get_abi_types_from_model(m),
        ).to_bytes()
        assert payload == header + abi.encode_model(m)
        assert len(header) == 4

    def test_json_encoding(self):
        m = SampleModel(n=7, data=b"hi")
        payload, _ = normalize_output(m, OutputFormat.json)
        # JSON output is the pydantic-serialized model
        assert json.loads(payload)["n"] == 7


class TestNormalizeVoucher:
    def test_value_only_positive(self):
        payload, value, name = normalize_voucher(10)
        assert payload == b"" and value == 10 and name == "bytes"

    def test_value_only_non_positive_raises(self):
        with pytest.raises(Exception, match="Invalid voucher value"):
            normalize_voucher(0)
        with pytest.raises(Exception, match="Invalid voucher value"):
            normalize_voucher(-5)

    def test_bytes_payload(self):
        payload, value, name = normalize_voucher(b"\xaa\xbb")
        assert payload == b"\xaa\xbb" and value == 0 and name == "bytes"

    def test_hex_payload(self):
        payload, value, name = normalize_voucher("0xaabb")
        assert payload == hex2bytes("aabb") and value == 0 and name == "hex"

    def test_model_builds_selector_plus_data(self):
        m = SampleModel(n=1, data=b"x")
        payload, value, name = normalize_voucher(m)
        assert value == 0 and name == "SampleModel"
        assert len(payload) > 4  # 4-byte selector + encoded args

    def test_model_with_value(self):
        m = SampleModel(n=1, data=b"x")
        payload, value, name = normalize_voucher(m, 99)
        assert value == 99 and name == "SampleModel"

    def test_explicit_selector_model_value(self):
        m = SampleModel(n=1, data=b"x")
        payload, value, name = normalize_voucher("transfer", m, 3)
        assert value == 3 and name == "SampleModel"
        assert len(payload) > 4

    def test_invalid_arg_count_raises(self):
        with pytest.raises(Exception, match="Invalid number of arguments"):
            normalize_voucher("a", "b", "c", "d")


class TestNormalizeJsonrpcOutput:
    def test_string_result(self):
        payload, name = normalize_jsonrpc_output("ok", OutputFormat.json, req_id=1)
        decoded = json.loads(payload)
        assert decoded == {"jsonrpc": "2.0", "result": "ok", "id": 1}
        assert name == "str"

    def test_bytes_result_base64(self):
        payload, name = normalize_jsonrpc_output(b"\x01\x02", OutputFormat.json, req_id=2)
        decoded = json.loads(payload)
        assert name == "bytes"
        assert base64.b64decode(decoded["result"]) == b"\x01\x02"

    def test_error_response(self):
        payload, _ = normalize_jsonrpc_output("boom", OutputFormat.json, req_id=3, error=True)
        decoded = json.loads(payload)
        assert decoded["error"]["message"] == "boom"
        assert decoded["error"]["code"] == 1
        assert decoded["id"] == 3
        assert "result" not in decoded

    def test_int_result(self):
        payload, name = normalize_jsonrpc_output(42, OutputFormat.json, req_id=4)
        assert json.loads(payload)["result"] == 42 and name == "int"
