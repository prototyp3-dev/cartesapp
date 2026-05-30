"""Unit tests for cartesapp.utils conversion and helper functions."""
import os

import pytest

from cartesapp import utils
from cartesapp.utils import (
    hex2bytes, bytes2hex, str2bytes, str2hex, hex2str, bytes2str,
    int2hex256, hex2562int, uint2hex256, hex2562uint,
    convert_camel_case, str2bool, is_hex,
    deep_merge_dicts, extract_module_name, get_modules,
    IOType, OutputFormat, InputFormat,
)


class TestByteHexConversions:
    def test_hex2bytes_with_and_without_prefix(self):
        assert hex2bytes("0xdeadbeef") == b"\xde\xad\xbe\xef"
        assert hex2bytes("deadbeef") == b"\xde\xad\xbe\xef"

    def test_bytes2hex_roundtrip(self):
        data = b"\x00\x01\xff"
        assert bytes2hex(data) == "0x0001ff"
        assert hex2bytes(bytes2hex(data)) == data

    def test_str_hex_roundtrip(self):
        assert str2hex("hi") == "0x6869"
        assert hex2str(str2hex("hello world")) == "hello world"
        assert bytes2str(str2bytes("abc")) == "abc"


class TestIntHexConversions:
    def test_uint_roundtrip(self):
        assert hex2562uint(uint2hex256(255)) == 255
        # zero-padded to 64 hex chars
        assert len(uint2hex256(1)) == 66  # '0x' + 64

    def test_signed_positive_roundtrip(self):
        assert hex2562int(int2hex256(42)) == 42

    def test_signed_negative_roundtrip(self):
        assert hex2562int(int2hex256(-42)) == -42

    def test_signed_negative_one(self):
        # -1 is all FFs in two's complement
        assert int2hex256(-1) == "0x" + "f" * 64
        assert hex2562int(int2hex256(-1)) == -1


class TestConvertCamelCase:
    @pytest.mark.parametrize("inp,expected", [
        ("my_query", "myQuery"),
        ("MyQuery", "myQuery"),
        ("simple", "simple"),
        ("a_b_c", "aBC"),
    ])
    def test_to_camel(self, inp, expected):
        assert convert_camel_case(inp) == expected

    def test_title_first(self):
        assert convert_camel_case("my_query", title_first=True) == "MyQuery"


class TestStr2Bool:
    @pytest.mark.parametrize("val", ["yes", "true", "t", "1", "y", "TRUE", "Yes"])
    def test_truthy(self, val):
        assert str2bool(val) is True

    @pytest.mark.parametrize("val", ["no", "false", "0", "", "maybe", None])
    def test_falsy(self, val):
        assert str2bool(val) is False


class TestIsHex:
    @pytest.mark.parametrize("val,expected", [
        ("0xdeadbeef", True),
        ("deadbeef", True),
        ("ff", True),
        ("nothex", False),
        ("", False),
    ])
    def test_is_hex(self, val, expected):
        assert is_hex(val) == expected


class TestDeepMergeDicts:
    def test_nested_merge(self):
        a = {"machine": {"entrypoint": "x", "keep": 1}, "top": 1}
        b = {"machine": {"entrypoint": "y"}, "other": 2}
        merged = deep_merge_dicts(a, b)
        assert merged == {
            "machine": {"entrypoint": "y", "keep": 1},
            "top": 1,
            "other": 2,
        }

    def test_does_not_mutate_inputs(self):
        a = {"x": {"y": 1}}
        b = {"x": {"z": 2}}
        deep_merge_dicts(a, b)
        assert a == {"x": {"y": 1}}  # original untouched at top level


class TestExtractModuleName:
    def test_returns_second_to_last_segment(self):
        assert extract_module_name("echo.echo") == "echo"
        assert extract_module_name("pkg.sub.module") == "sub"


class TestGetModules:
    def test_discovers_packages_skips_dotdirs_and_tests(self, tmp_path):
        (tmp_path / "moda").mkdir()
        (tmp_path / "moda" / "settings.py").write_text("FILES=['m']\n")
        (tmp_path / "moda" / "m.py").write_text("\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("\n")
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "h.py").write_text("\n")

        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            modules = get_modules()
        finally:
            os.chdir(cwd)

        assert "moda" in modules
        # tests/ and dotdirs are excluded
        assert not any(m.startswith("tests") for m in modules)
        assert not any("hidden" in m for m in modules)


class TestEnumValues:
    def test_output_format_members(self):
        assert {f.name for f in OutputFormat} == {"abi", "packed_abi", "json", "header_abi"}

    def test_input_format_members(self):
        assert {f.name for f in InputFormat} == {"abi", "url", "json", "jsonrpc"}

    def test_iotype_members_are_distinct(self):
        # delegate_call_voucher must not alias input (regression lock for bug #2)
        names = [f.name for f in IOType]
        values = [f.value for f in IOType]
        assert set(names) == {"report", "notice", "voucher", "input", "delegate_call_voucher"}
        assert len(values) == len(set(values))  # no aliasing
        assert IOType.delegate_call_voucher is not IOType.input
        assert IOType.delegate_call_voucher.name == "delegate_call_voucher"
