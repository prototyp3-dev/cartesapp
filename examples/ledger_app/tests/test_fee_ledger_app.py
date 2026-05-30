import pytest
import json
import os

CONDITION = os.getenv('CARTESAPP_TEST_CLIENT') != 'cartesi_machine'
pytestmark = pytest.mark.skipif(CONDITION, reason="Does not run on host")

from cartesi import abi

from cartesapp.utils import bytes2hex, str2hex, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from model import BalancePayload, DepositEtherPayload, ETHER_PORTAL_ADDRESS, generate_json_input

# fix import path to import functions and classes
fix_import_path(f"{get_script_dir()}/..")
from ledger_app.fee import pay_fee, withdraw_all, FEE_AMOUNT, OPERATOR_WALLET

USER1_ADDRESS = f"{1000:#042x}"
USER2_ADDRESS = f"{1001:#042x}"


###
# Tests

# test application setup
@pytest.fixture(scope='session')
def app_client() -> TestClient:
    client = TestClient(
        f"{get_script_dir()}/.." # optional: chdir to inspect modules to import (e.g. check for */settings.py)
    )
    return client

@pytest.fixture()
def deposit_payload() -> DepositEtherPayload:
    return DepositEtherPayload(
        sender= USER1_ADDRESS,
        amount=10*FEE_AMOUNT,
        exec_layer_data=b''
    )

def test_should_deposit_eth(
        app_client: TestClient,
        deposit_payload: DepositEtherPayload):

    hex_payload = bytes2hex(abi.encode_model(deposit_payload,True))
    app_client.send_advance(
        msg_sender=ETHER_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

# should pay fee
@pytest.mark.order(after="test_should_deposit_eth")
def test_should_pay_fee(app_client: TestClient):
    hex_payload = app_client.input_helper.encode_mutation_input(pay_fee)
    app_client.send_advance(
        msg_sender=USER1_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

@pytest.fixture()
def balance_payload() -> BalancePayload:
    return BalancePayload(
        account=OPERATOR_WALLET
    )

@pytest.mark.order(after="test_should_pay_fee")
def test_operator_should_have_balance(
    app_client: TestClient,
    balance_payload: BalancePayload):

    payload = generate_json_input("ledger_getBalance",balance_payload)
    hex_payload = str2hex(json.dumps(payload))
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    assert int(report,16) == FEE_AMOUNT

@pytest.mark.order(after="test_operator_should_have_balance")
def test_should_withdraw_all(app_client: TestClient):
    hex_payload = app_client.input_helper.encode_mutation_input(withdraw_all)
    app_client.send_advance(
        msg_sender=OPERATOR_WALLET,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

@pytest.mark.order(after="test_should_withdraw_all")
def test_operator_should_not_have_balance(
    app_client: TestClient,
    balance_payload: BalancePayload):

    balance_payload.account = OPERATOR_WALLET

    payload = generate_json_input("ledger_getBalance",balance_payload)
    hex_payload = str2hex(json.dumps(payload))
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    assert int(report,16) == 0
