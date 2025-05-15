
import pytest
import json

from cartesi.abi import decode_to_model

from cartesapp.utils import hex2bytes, hex2str, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from cartesapp.wallet.app_wallet import BalancePayload, deposit_erc721, DepositErc721Payload, ERC721_PORTAL_ADDRESS, \
    Erc721Event, balance, WalletBalance, TransferErc721Payload, Erc721Transfer, WithdrawErc721Payload, WithdrawErc721, Erc721Withdraw

# fix import path to import functions and classes
fix_import_path(f"{get_script_dir()}/..")

TOKEN_ID = 1
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
def deposit_payload() -> DepositErc721Payload:
    return DepositErc721Payload(
        sender = USER1_ADDRESS,
        token = TOKEN_ADDRESS,
        id=TOKEN_ID,
        exec_layer_data=b''
    )

def test_should_deposit(
        app_client: TestClient,
        deposit_payload: DepositErc721Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        deposit_erc721,
        deposit_payload)
    app_client.send_advance(
        msg_sender=ERC721_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=Erc721Event)
    assert notice_model.mod_id == deposit_payload.id


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

    assert report_model.erc721 is not None
    assert report_model.erc721.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID in report_model.erc721[TOKEN_ADDRESS]

@pytest.fixture()
def transfer_payload() -> TransferErc721Payload:
    return TransferErc721Payload(
        receiver= USER2_ADDRESS,
        token = TOKEN_ADDRESS,
        id=TOKEN_ID,
        exec_layer_data=b''
    )

def test_should_transfer(
        app_client: TestClient,
        transfer_payload: TransferErc721Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc721Transfer,
        transfer_payload)
    app_client.send_advance(
        msg_sender=USER1_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=Erc721Event)
    assert notice_model.mod_id == transfer_payload.id

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

    assert report_model.erc721 is not None
    assert report_model.erc721.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID in report_model.erc721[TOKEN_ADDRESS]

@pytest.fixture()
def withdraw_payload() -> WithdrawErc721Payload:
    return WithdrawErc721Payload(
        token = TOKEN_ADDRESS,
        id=TOKEN_ID,
        exec_layer_data=b''
    )

def test_should_withdraw(
        app_client: TestClient,
        withdraw_payload: WithdrawErc721Payload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc721Withdraw,
        withdraw_payload)
    app_client.send_advance(
        msg_sender=USER2_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes[4:],model=Erc721Event)
    assert notice_model.mod_id == -withdraw_payload.id

    voucher = app_client.rollup.vouchers[-1]['data']['payload']
    voucher_bytes = hex2bytes(voucher)
    voucher_model = decode_to_model(data=voucher_bytes[4:],model=WithdrawErc721)
    assert voucher_model.id == withdraw_payload.id

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

    assert report_model.erc721 is not None
    assert report_model.erc721.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID not in report_model.erc721[TOKEN_ADDRESS]
