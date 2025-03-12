import pytest

from cartesapp.utils import bytes2hex, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient

# fix import path to import functions and classes
fix_import_path(f"{get_script_dir()}/..")
from echo.echo import Payload, echo_mutation, echo_query

###
# Tests

# test application setup
@pytest.fixture(scope='session')
def app_client() -> TestClient:
    client = TestClient(
        f"{get_script_dir()}/.." # optional: chdir to inspect modules to import (e.g. check for */settings.py)
    )
    return client

# test payload
@pytest.fixture()
def echo_payload() -> Payload:
    return Payload(
        message=b"Hello World"
    )

# test mutation
def test_should_echo_event(
        app_client: TestClient,
        echo_payload: Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        echo_mutation,
        echo_payload)
    app_client.send_advance(hex_payload=hex_payload)

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    assert notice == bytes2hex(echo_payload.message)

# test inspect
def test_should_echo_output(
    app_client: TestClient,
    echo_payload):

    hex_payload = app_client.input_helper.encode_query_input(
        echo_query,
        echo_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    assert report == bytes2hex(echo_payload.message)
