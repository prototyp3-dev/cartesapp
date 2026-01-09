import pytest
import json

from cartesi.abi import decode_to_model

from cartesapp.utils import hex2bytes, hex2str, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from cartesapplib.wallet.app_wallet import BalancePayload, deposit_ether, DepositEtherPayload, ETHER_PORTAL_ADDRESS, \
    EtherEvent, balance, WalletBalance

# fix import path to import functions and classes
fix_import_path(f"{get_script_dir()}/..")
from app.fee import pay_fee, withdraw_all, FEE_AMOUNT, OPERATOR_WALLET

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

    hex_payload = app_client.input_helper.encode_mutation_input(
        deposit_ether,
        deposit_payload)
    app_client.send_advance(
        msg_sender=ETHER_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=EtherEvent)
    assert notice_model.mod_amount == deposit_payload.amount

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
        address=OPERATOR_WALLET
    )

@pytest.mark.order(after="test_should_pay_fee")
def test_operator_should_have_balance(
    app_client: TestClient,
    balance_payload: BalancePayload):

    hex_payload = app_client.input_helper.encode_query_json_input(
        balance,
        balance_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = WalletBalance.parse_obj(report_json)

    assert report_model.ether is not None
    assert report_model.ether == FEE_AMOUNT

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

    balance_payload.address = OPERATOR_WALLET

    hex_payload = app_client.input_helper.encode_query_json_input(
        balance,
        balance_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = WalletBalance.parse_obj(report_json)

    assert report_model.ether is not None
    assert report_model.ether == 0
