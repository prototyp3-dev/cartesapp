
import pytest
import json

from cartesi.abi import decode_to_model

from cartesapp.utils import hex2bytes, hex2str, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from cartesapp.wallet.app_wallet import BalancePayload, deposit_erc20, DepositErc20Payload, ERC20_PORTAL_ADDRESS, \
    Erc20Event, balance, WalletBalance, TransferErc20Payload, Erc20Transfer, WithdrawErc20Payload, WithdrawErc20, Erc20Withdraw

# fix import path to import functions and classes
fix_import_path(f"{get_script_dir()}/..")

AMOUNT = 10_000_000_000_000_000
TOKEN_ADDRESS = f"{1234:#042x}"

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
def deposit_payload() -> DepositErc20Payload:
    return DepositErc20Payload(
        sender = USER1_ADDRESS,
        token = TOKEN_ADDRESS,
        amount=10*AMOUNT,
        exec_layer_data=b''
    )

def test_should_deposit(
        app_client: TestClient,
        deposit_payload: DepositErc20Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        deposit_erc20,
        deposit_payload)
    app_client.send_advance(
        msg_sender=ERC20_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=Erc20Event)
    assert notice_model.mod_amount == deposit_payload.amount


@pytest.fixture()
def balance_payload() -> BalancePayload:
    return BalancePayload(
        address=USER1_ADDRESS
    )

@pytest.mark.order(after="test_should_deposit")
def test_should_have_balance(
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

    assert report_model.erc20 is not None
    assert report_model.erc20.get(TOKEN_ADDRESS) is not None
    assert report_model.erc20[TOKEN_ADDRESS] > 0

@pytest.fixture()
def transfer_payload() -> TransferErc20Payload:
    return TransferErc20Payload(
        receiver= USER2_ADDRESS,
        token = TOKEN_ADDRESS,
        amount=AMOUNT,
        exec_layer_data=b''
    )

def test_should_transfer(
        app_client: TestClient,
        transfer_payload: TransferErc20Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc20Transfer,
        transfer_payload)
    app_client.send_advance(
        msg_sender=USER1_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=Erc20Event)
    assert notice_model.mod_amount == transfer_payload.amount

@pytest.mark.order(after="test_should_transfer")
def test_should_have_balance2(
        app_client: TestClient,
        balance_payload: BalancePayload):
    balance_payload.address = USER2_ADDRESS

    hex_payload = app_client.input_helper.encode_query_json_input(
        balance,
        balance_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = WalletBalance.parse_obj(report_json)

    assert report_model.erc20 is not None
    assert report_model.erc20.get(TOKEN_ADDRESS) is not None
    assert report_model.erc20[TOKEN_ADDRESS] > 0

@pytest.fixture()
def withdraw_payload() -> WithdrawErc20Payload:
    return WithdrawErc20Payload(
        token = TOKEN_ADDRESS,
        amount=AMOUNT,
        exec_layer_data=b''
    )

def test_should_withdraw(
        app_client: TestClient,
        withdraw_payload: WithdrawErc20Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc20Withdraw,
        withdraw_payload)
    app_client.send_advance(
        msg_sender=USER2_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=Erc20Event)
    assert notice_model.mod_amount == -withdraw_payload.amount

    voucher = app_client.rollup.vouchers[-1]['data']['payload']
    voucher_bytes = hex2bytes(voucher)
    voucher_model = decode_to_model(data=voucher_bytes[4:],model=WithdrawErc20)
    assert voucher_model.amount == withdraw_payload.amount

@pytest.mark.order(after="test_should_withdraw")
def test_should_not_have_balance2(
        app_client: TestClient,
        balance_payload: BalancePayload):
    balance_payload.address = USER2_ADDRESS

    hex_payload = app_client.input_helper.encode_query_json_input(
        balance,
        balance_payload)
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    report_json = json.loads(hex2str(report))
    report_model = WalletBalance.parse_obj(report_json)

    assert report_model.erc20 is not None
    assert report_model.erc20.get(TOKEN_ADDRESS) is not None
    assert report_model.erc20[TOKEN_ADDRESS] == 0
