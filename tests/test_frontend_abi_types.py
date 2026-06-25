"""Unit tests for the named-tuple ABI type generation used by the frontend
codegen (cartesapp.template_generator.get_named_abi_types_from_model).

viem/abitype's parseAbiParameters needs nested tuple components to be named,
so the frontend `abiTypes` must alias each field inside a tuple, e.g.
List[Names] -> '(bytes32[] names)[]'. Component names do not affect ABI
encoding bytes, so this is purely a frontend-codegen concern.
"""
from typing import List

from pydantic import BaseModel

from cartesi import abi

from cartesapp.template_generator import get_named_abi_types_from_model


class Names(BaseModel):
    names: List[abi.Bytes32]


class ListOfNames(BaseModel):
    names_list: List[Names]


class AdvancePayload(BaseModel):
    value: abi.UInt256
    data: abi.Bytes


class Pair(BaseModel):
    a: abi.UInt256
    b: abi.UInt256


class HasPair(BaseModel):
    pair: Pair


class HasScalars(BaseModel):
    ids: List[abi.UInt256]
    name: str


def test_list_of_nested_model_gets_named_components():
    # The requested case from the framework author.
    assert get_named_abi_types_from_model(ListOfNames) == ['(bytes32[] names)[]']


def test_simple_model_unchanged():
    # No regression vs cartesi.abi.get_abi_types_from_model for flat models.
    assert get_named_abi_types_from_model(AdvancePayload) == ['uint256', 'bytes']
    assert get_named_abi_types_from_model(AdvancePayload) == \
        abi.get_abi_types_from_model(AdvancePayload)


def test_single_nested_model_gets_named_components():
    assert get_named_abi_types_from_model(HasPair) == ['(uint256 a,uint256 b)']


def test_list_of_scalars_and_scalar():
    assert get_named_abi_types_from_model(HasScalars) == ['uint256[]', 'string']
