import pytest
import json

from cartesi.abi import decode_to_model, encode_model

from cartesapp.utils import hex2bytes, hex2str, fix_import_path, get_script_dir
from cartesapp.testclient import TestClient
from cartesapp.wallet.app_wallet import BalancePayload, BatchValue, deposit_erc1155_single, deposit_erc1155_batch, DepositErc1155SinglePayload, DepositErc1155BatchPayload, \
    ERC1155_SINGLE_PORTAL_ADDRESS, ERC1155_BATCH_PORTAL_ADDRESS, Erc1155Event, TransferErc1155SinglePayload, TransferErc1155BatchPayload, \
    Erc1155SingleTransfer, Erc1155BatchTransfer, WithdrawErc1155SinglePayload, WithdrawErc1155BatchPayload, WithdrawErc1155Single, WithdrawErc1155Batch,\
    Erc1155SingleWithdraw,  Erc1155BatchWithdraw, balance, WalletBalance

# fix import path to import functions and classes
fix_import_path(f"{get_script_dir()}/..")

TOKEN_ID1 = 1
TOKEN_ID2 = 2
AMOUNT = 100
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
def deposit_payload() -> DepositErc1155SinglePayload:
    return DepositErc1155SinglePayload(
        sender = USER1_ADDRESS,
        token = TOKEN_ADDRESS,
        id = TOKEN_ID1,
        amount=10*AMOUNT,
        exec_layer_data=b''
    )

def test_should_deposit(
        app_client: TestClient,
        deposit_payload: DepositErc1155SinglePayload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        deposit_erc1155_single,
        deposit_payload)
    app_client.send_advance(
        msg_sender=ERC1155_SINGLE_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    assert notice_model.mod_ids[0] == deposit_payload.id
    assert notice_model.mod_amounts[0] == deposit_payload.amount

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

    assert report_model.erc1155 is not None
    assert report_model.erc1155.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID1 in report_model.erc1155[TOKEN_ADDRESS]
    assert report_model.erc1155[TOKEN_ADDRESS][TOKEN_ID1] > 0

@pytest.fixture()
def transfer_payload() -> TransferErc1155SinglePayload:
    return TransferErc1155SinglePayload(
        receiver= USER2_ADDRESS,
        token = TOKEN_ADDRESS,
        id = TOKEN_ID1,
        amount=AMOUNT,
        exec_layer_data=b''
    )

def test_should_transfer(
        app_client: TestClient,
        transfer_payload: TransferErc1155SinglePayload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc1155SingleTransfer,
        transfer_payload)
    app_client.send_advance(
        msg_sender=USER1_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    assert notice_model.mod_ids[0] == transfer_payload.id
    assert notice_model.mod_amounts[0] == transfer_payload.amount

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

    assert report_model.erc1155 is not None
    assert report_model.erc1155.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID1 in report_model.erc1155[TOKEN_ADDRESS].keys()
    assert report_model.erc1155[TOKEN_ADDRESS][TOKEN_ID1] > 0

@pytest.fixture()
def withdraw_payload() -> WithdrawErc1155SinglePayload:
    return WithdrawErc1155SinglePayload(
        token = TOKEN_ADDRESS,
        id = TOKEN_ID1,
        amount=AMOUNT,
        exec_layer_data=b''
    )

def test_should_withdraw(
        app_client: TestClient,
        withdraw_payload: WithdrawErc1155SinglePayload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc1155SingleWithdraw,
        withdraw_payload)
    app_client.send_advance(
        msg_sender=USER2_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    assert notice_model.mod_ids[0] == -withdraw_payload.id
    assert notice_model.mod_amounts[0] == -withdraw_payload.amount

    voucher = app_client.rollup.vouchers[-1]['data']['payload']
    voucher_bytes = hex2bytes(voucher)
    voucher_model = decode_to_model(data=voucher_bytes[4:],model=WithdrawErc1155Single)
    assert voucher_model.amount == withdraw_payload.amount and voucher_model.id == withdraw_payload.id

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

    assert report_model.erc1155 is not None
    assert report_model.erc1155.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID1 not in report_model.erc1155[TOKEN_ADDRESS].keys() or \
        report_model.erc1155[TOKEN_ADDRESS][TOKEN_ID1] == 0


# 1155 batch tests

@pytest.fixture()
def batch_deposit_payload() -> DepositErc1155BatchPayload:
    batch = BatchValue(
        ids = [TOKEN_ID1,TOKEN_ID2],
        amounts = [AMOUNT,AMOUNT],
        base_layer_data = b'',
        exec_layer_data=b'',
    )
    return DepositErc1155BatchPayload(
        sender = USER2_ADDRESS,
        token = TOKEN_ADDRESS,
        batch_value =  encode_model(batch),
    )

@pytest.mark.order(after="test_should_withdraw")
def test_should_deposit_batch(
        app_client: TestClient,
        batch_deposit_payload: DepositErc1155BatchPayload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        deposit_erc1155_batch,
        batch_deposit_payload)
    app_client.send_advance(
        msg_sender=ERC1155_BATCH_PORTAL_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    batch_value = decode_to_model(data=batch_deposit_payload.batch_value,model=BatchValue)
    assert set(notice_model.mod_ids) - set(batch_value.ids) == set()
    assert set(notice_model.mod_amounts) == set(batch_value.amounts)

@pytest.mark.order(after="test_should_deposit_batch",before="test_should_transfer_batch")
def test_should_have_balance_batch(
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

    assert report_model.erc1155 is not None
    assert report_model.erc1155.get(TOKEN_ADDRESS) is not None
    assert TOKEN_ID1 in report_model.erc1155[TOKEN_ADDRESS].keys()
    assert report_model.erc1155[TOKEN_ADDRESS][TOKEN_ID1] > 0
    assert TOKEN_ID2 in report_model.erc1155[TOKEN_ADDRESS].keys()
    assert report_model.erc1155[TOKEN_ADDRESS][TOKEN_ID2] > 0


@pytest.fixture()
def transfer_batch_payload() -> TransferErc1155BatchPayload:
    return TransferErc1155BatchPayload(
        receiver= USER1_ADDRESS,
        token = TOKEN_ADDRESS,
        ids = [TOKEN_ID1,TOKEN_ID2],
        amounts=[AMOUNT,AMOUNT],
        exec_layer_data=b''
    )

@pytest.mark.order(after="test_should_deposit_batch")
def test_should_transfer_batch(
        app_client: TestClient,
        transfer_batch_payload: TransferErc1155BatchPayload):

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc1155BatchTransfer,
        transfer_batch_payload)
    app_client.send_advance(
        msg_sender=USER2_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-2]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    assert notice_model.user == USER2_ADDRESS
    assert set(notice_model.mod_ids) - set([-i for i in transfer_batch_payload.ids]) == set()
    assert set(notice_model.mod_amounts) == set([-i for i in transfer_batch_payload.amounts])

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    assert notice_model.user == USER1_ADDRESS
    assert set(notice_model.mod_ids) - set(transfer_batch_payload.ids) == set()
    assert set(notice_model.mod_amounts) == set(transfer_batch_payload.amounts)

@pytest.fixture()
def withdraw_batch_payload() -> WithdrawErc1155BatchPayload:
    return WithdrawErc1155BatchPayload(
        token = TOKEN_ADDRESS,
        ids = [TOKEN_ID1,TOKEN_ID2],
        amounts=[AMOUNT,AMOUNT],
        exec_layer_data=b''
    )

@pytest.mark.order(after="test_should_transfer_batch")
def test_should_withdraw_tokens_batch(
        app_client: TestClient,
        withdraw_batch_payload: WithdrawErc1155BatchPayload):

    withdraw_payload = WithdrawErc1155BatchPayload(
        token = TOKEN_ADDRESS,
        ids = [TOKEN_ID1,TOKEN_ID2],
        amounts = [AMOUNT,AMOUNT],
        exec_layer_data=b''
    )

    hex_payload = app_client.input_helper.encode_mutation_input(
        Erc1155BatchWithdraw,
        withdraw_payload)
    app_client.send_advance(
        msg_sender=USER1_ADDRESS,
        hex_payload=hex_payload
    )

    assert app_client.rollup.status

    notice = app_client.rollup.notices[-1]['data']['payload']
    notice_bytes = hex2bytes(notice)
    notice_model = decode_to_model(data=notice_bytes,model=Erc1155Event)
    assert notice_model.user == USER1_ADDRESS
    assert set(notice_model.mod_ids) - set([-i for i in withdraw_batch_payload.ids]) == set()
    assert set(notice_model.mod_amounts) == set([-i for i in withdraw_batch_payload.amounts])

    voucher = app_client.rollup.vouchers[-1]['data']['payload']
    voucher_bytes = hex2bytes(voucher)
    voucher_model = decode_to_model(data=voucher_bytes[4:],model=WithdrawErc1155Batch)
    assert set(voucher_model.ids) == set(withdraw_batch_payload.ids)
    assert set(voucher_model.amounts) == set(withdraw_batch_payload.amounts)
