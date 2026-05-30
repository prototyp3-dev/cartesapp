import pytest
import json
import os

CONDITION = os.getenv('CARTESAPP_TEST_CLIENT') != 'cartesi_machine'
pytestmark = pytest.mark.skipif(CONDITION, reason="Does not run on host")

from cartesi import abi
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.utils import bytes2hex, str2hex, hex2bytes, uint2hex256, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from model import BalancePayload, DepositErc721Payload, ERC721_PORTAL_ADDRESS, \
    TransferErc721Payload, WithdrawErc721Payload, Erc721Voucher, generate_json_input, \
    DataBytes

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
    client = TestClient()
    return client

@pytest.fixture()
def deposit_payload() -> DepositErc721Payload:
    data_bytes = DataBytes(
        base_layer_data=b'',
        exec_layer_data=b''
    )
    return DepositErc721Payload(
        sender = USER1_ADDRESS,
        token = TOKEN_ADDRESS,
        token_id=TOKEN_ID,
        data_bytes=abi.encode_model(data_bytes)
    )

def test_should_deposit(
        app_client: TestClient,
        deposit_payload: DepositErc721Payload):

    hex_payload = bytes2hex(abi.encode_model(deposit_payload,True))
    app_client.send_advance(
        msg_sender=ERC721_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

@pytest.fixture()
def balance_payload() -> BalancePayload:
    return BalancePayload(
        account=USER1_ADDRESS,
        token=TOKEN_ADDRESS,
        token_id=uint2hex256(TOKEN_ID)
    )

@pytest.mark.order(after="test_should_deposit",before="test_should_transfer")
def test_should_have_balance(
    app_client: TestClient,
    balance_payload: BalancePayload):

    payload = generate_json_input("ledger_getBalance",balance_payload)
    hex_payload = str2hex(json.dumps(payload))
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    assert int(report,16) == 1

@pytest.fixture()
def transfer_payload() -> TransferErc721Payload:
    return TransferErc721Payload(
        receiver=bytes.fromhex(f"{'0'*24}{USER2_ADDRESS[2:]}"),
        token = TOKEN_ADDRESS,
        token_id=TOKEN_ID,
        exec_layer_data=b''
    )

@pytest.mark.order(after="test_should_deposit")
def test_should_transfer(
        app_client: TestClient,
        transfer_payload: TransferErc721Payload):

    header = ABIFunctionSelectorHeader(
        function="TransferErc721",
        argument_types=abi.get_abi_types_from_model(model=TransferErc721Payload)
    ).to_bytes()
    hex_payload = bytes2hex(header + abi.encode_model(transfer_payload))
    app_client.send_advance(
        msg_sender=USER1_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

@pytest.mark.order(after="test_should_transfer",before="test_should_withdraw")
def test_should_have_balance2(
        app_client: TestClient,
        balance_payload: BalancePayload):
    balance_payload.account = USER2_ADDRESS

    payload = generate_json_input("ledger_getBalance",balance_payload)
    hex_payload = str2hex(json.dumps(payload))
    app_client.send_inspect(hex_payload=hex_payload)

    assert app_client.rollup.status

    report = app_client.rollup.reports[-1]['data']['payload']
    assert int(report,16) == 1

@pytest.fixture()
def withdraw_payload() -> WithdrawErc721Payload:
    return WithdrawErc721Payload(
        token = TOKEN_ADDRESS,
        token_id=TOKEN_ID,
        exec_layer_data=b''
    )

@pytest.mark.order(after="test_should_transfer")
def test_should_withdraw(
        app_client: TestClient,
        withdraw_payload: WithdrawErc721Payload):

    header = ABIFunctionSelectorHeader(
        function="WithdrawErc721",
        argument_types=abi.get_abi_types_from_model(model=WithdrawErc721Payload)
    ).to_bytes()
    hex_payload = bytes2hex(header + abi.encode_model(withdraw_payload))
    app_client.send_advance(
        msg_sender=USER2_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    voucher = app_client.rollup.vouchers[-1]['data']['payload']
    voucher_bytes = hex2bytes(voucher)
    voucher_model = abi.decode_to_model(data=voucher_bytes[4:],model=Erc721Voucher)
    assert voucher_model.token_id == withdraw_payload.token_id

@pytest.mark.order(after="test_should_withdraw")
def test_should_not_have_balance2(
        app_client: TestClient,
        balance_payload: BalancePayload):
    balance_payload.account = USER2_ADDRESS

    payload = generate_json_input("ledger_getBalance",balance_payload)
    hex_payload = str2hex(json.dumps(payload))
    app_client.send_inspect(hex_payload=hex_payload)

    assert not app_client.rollup.status # asset removed
