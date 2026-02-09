import pytest
import json

from cartesi.abi import decode_to_model

from cartesapp.utils import hex2bytes, hex2str, str2hex, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from cartesapp.input import generate_jsonrpc_input
from cartesapplib.indexer.io_index import  IndexerPayload, IndexerOutput, indexer_query

fix_import_path(f"{get_script_dir()}/..")
from url_app.messages import echo_and_update_count, messages, Payload, MessageReceived, Messages, MessagesQueryPayload
from json_app.count import UserMessages
from jsonrpc_app.extended_messages import ExtendedMessages
from json_app.count import message_counts
from jsonrpc_app.extended_messages import messages_and_users

###
# Setup and Aux functions

USER2 = f"{2:#042x}"

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
def send_message_payload() -> Payload:
    return Payload(
        message="Hello World"
    )

@pytest.fixture()
def send_message_payload2() -> Payload:
    return Payload(
        message="Hello World 2"
    )

# test mutation
def test_should_send_messages(
        app_client: TestClient,
        send_message_payload: Payload,
        send_message_payload2: Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        echo_and_update_count,
        send_message_payload)
    app_client.send_advance(hex_payload=hex_payload)

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']

    notice_bytes = hex2bytes(notice)
    notice_bytes = notice_bytes[4:] # skipe notice header
    notice_model = decode_to_model(data=notice_bytes,model=MessageReceived)
    assert notice_model.message == send_message_payload.message
    assert notice_model.index == 1

    app_client.send_advance(hex_payload=hex_payload, msg_sender=USER2)

    assert app_client.rollup.status

    hex_payload2 = app_client.input_helper.encode_mutation_input(
        echo_and_update_count,
        send_message_payload2)
    app_client.send_advance(hex_payload=hex_payload2)

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']

    notice_bytes = hex2bytes(notice)
    notice_bytes = notice_bytes[4:] # skipe notice header
    notice_model = decode_to_model(data=notice_bytes,model=MessageReceived)
    assert notice_model.message == send_message_payload2.message
    assert notice_model.index == 2

@pytest.fixture()
def indexer_query_payload() -> IndexerPayload:
    return IndexerPayload(
        type='notice',
        tags=[USER2],
    )

@pytest.mark.order(after=["test_should_send_messages"])
def test_should_get_events(
    app_client: TestClient,
    indexer_query_payload):

    hex_payload = app_client.input_helper.encode_query_json_input(
        indexer_query,
        indexer_query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = IndexerOutput.parse_obj(report_json)

    assert report_model.total == 1
    assert report_model.data[0].class_name == MessageReceived.__name__

@pytest.mark.order(after=["test_should_send_messages"])
def test_should_get_inputs(
    app_client: TestClient,
    indexer_query_payload):

    indexer_query_payload.type = 'input'
    hex_payload = app_client.input_helper.encode_query_json_input(
        indexer_query,
        indexer_query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = IndexerOutput.parse_obj(report_json)

    assert report_model.total == 1
    assert report_model.data[0].class_name == Payload.__name__

@pytest.mark.order(after=["test_should_send_messages"])
def test_should_get_inputs2(
    app_client: TestClient,
    indexer_query_payload):

    indexer_query_payload.type = 'input'
    indexer_query_payload.tags_or = True
    hex_payload = app_client.input_helper.encode_query_json_input(
        indexer_query,
        indexer_query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = IndexerOutput.parse_obj(report_json)

    assert report_model.total == 1
    assert report_model.data[0].class_name == Payload.__name__

@pytest.mark.order(after=["test_should_send_messages"])
def test_should_get_inputs3(
    app_client: TestClient,
    indexer_query_payload):

    indexer_query_payload.type = 'input'
    indexer_query_payload.tags = None
    hex_payload = app_client.input_helper.encode_query_json_input(
        indexer_query,
        indexer_query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = IndexerOutput.parse_obj(report_json)

    assert report_model.total == 3
    assert report_model.data[0].class_name == Payload.__name__
