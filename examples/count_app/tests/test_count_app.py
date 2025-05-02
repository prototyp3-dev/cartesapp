import pytest
import json

from cartesi.abi import decode_to_model

from cartesapp.utils import hex2bytes, hex2str, str2hex, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from cartesapp.indexer.io_index import IndexerPayload, IndexerOutput, indexer_query
from cartesapp.input import generate_jsonrpc_input

fix_import_path(f"{get_script_dir()}/..")
from common.model import Payload, MessageReceived, Messages, UserMessages, ExtendedMessages, MessagesQueryPayload
from app.messages import echo_and_update_count, messages
from json_app.count import message_counts
from jsonrpc_app.extended_messages import messages_and_users

###
# Setup and Aux functions

USER2 = f"{2:#042x}"
USER3 = f"{3:#042x}"

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

# test mutation
def test_should_send_message_event(
        app_client: TestClient,
        send_message_payload: Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        echo_and_update_count,
        send_message_payload)
    app_client.send_advance(hex_payload=hex_payload)

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']

    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=MessageReceived)
    assert notice_model.message == send_message_payload.message
    assert notice_model.index == 1

@pytest.mark.order(after="test_should_send_message_event")
def test_should_send_message_event_other_user(
        app_client: TestClient,
        send_message_payload: Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        echo_and_update_count,
        send_message_payload)
    app_client.send_advance(hex_payload=hex_payload, msg_sender=USER2)

    assert app_client.rollup.status


@pytest.fixture()
def send_message_payload2() -> Payload:
    return Payload(
        message="Hello World 2"
    )

@pytest.mark.order(after="test_should_send_message_event_other_user")
def test_should_send_another_message_event(
        app_client: TestClient,
        send_message_payload2: Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        echo_and_update_count,
        send_message_payload2)
    app_client.send_advance(hex_payload=hex_payload)

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']

    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=MessageReceived)
    assert notice_model.message == send_message_payload2.message
    assert notice_model.index == 2

# test inspect

@pytest.fixture()
def query_payload() -> MessagesQueryPayload:
    return MessagesQueryPayload()

@pytest.mark.order(after=["test_should_send_another_message_event","test_should_send_message_event_other_user"])
def test_should_get_messages(
    app_client: TestClient,
    query_payload):

    hex_payload = app_client.input_helper.encode_query_url_input(
        messages,
        query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = Messages.parse_obj(report_json)

    assert report_model.total == 3

@pytest.mark.order(after=["test_should_send_another_message_event","test_should_send_message_event_other_user"])
def test_should_get_messages_filter(
    app_client: TestClient,
    query_payload):

    query_payload.user_address = USER2
    hex_payload = app_client.input_helper.encode_query_url_input(
        messages,
        query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = Messages.parse_obj(report_json)

    assert report_model.total == 1


@pytest.fixture()
def indexer_query_payload() -> IndexerPayload:
    return IndexerPayload(
        type='notice',
        tags=[USER2]
    )

@pytest.mark.order(after=["test_should_send_message_event_other_user"])
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

@pytest.mark.order(after=["test_should_send_message_event_other_user"])
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

@pytest.mark.order(after=["test_should_send_another_message_event","test_should_send_message_event_other_user"])
def test_should_count_messages(
    app_client: TestClient,
    query_payload):

    hex_payload = app_client.input_helper.encode_query_json_input(
        message_counts,
        query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = UserMessages.parse_obj(report_json)

    assert report_model.total == 2

@pytest.mark.order(after=["test_should_send_another_message_event","test_should_send_message_event_other_user"])
def test_should_count_message_filter(
    app_client: TestClient,
    query_payload):

    query_payload.user_address = USER2
    hex_payload = app_client.input_helper.encode_query_json_input(
        message_counts,
        query_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = UserMessages.parse_obj(report_json)

    assert report_model.total == 1
    assert report_model.data[0].user_address == USER2
    assert report_model.data[0].n_messages == 1

@pytest.mark.order(after=["test_should_send_another_message_event","test_should_send_message_event_other_user"])
def test_should_get_extended_messages(
    app_client: TestClient,
    query_payload):

    input_dict = generate_jsonrpc_input(
        messages_and_users,
        query_payload)
    hex_payload = str2hex(json.dumps(input_dict))
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    assert input_dict.get("id") == report_json.get("id")

    report_model = ExtendedMessages.parse_obj(report_json.get("result"))
    assert report_model.total == 3

@pytest.mark.order(after=["test_should_send_another_message_event","test_should_send_message_event_other_user"])
def test_should_get_extended_messages_filter(
    app_client: TestClient,
    query_payload):

    query_payload.user_address = USER2
    input_dict = generate_jsonrpc_input(
        messages_and_users,
        query_payload)
    hex_payload = str2hex(json.dumps(input_dict))
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    assert input_dict.get("id") == report_json.get("id")

    report_model = ExtendedMessages.parse_obj(report_json.get("result"))

    assert report_model.total == 1
    assert report_model.data[0].user == USER2
