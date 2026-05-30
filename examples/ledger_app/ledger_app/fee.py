from pydantic import BaseModel
import logging

from cartesapp.output import emit_event, event
from cartesapp.input import mutation
from cartesi import abi

from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata, get_ledger

# static conf
OPERATOR_WALLET = f"{1:#042x}".lower()
FEE_AMOUNT = 10_000_000_000_000_000
MINIMUM_COLLECT_FEE_INTERVAL = 86400

# storage
class LedgerUserFee(Entity):
    user_address    = helpers.PrimaryKey(str)
    total_amount    = helpers.Required(float, default=0)

class LedgerFeeCollected(Entity):
    timestamp = helpers.Required(int, unsigned=True)

@event()
class AmountPayed(BaseModel):
    amount: abi.UInt256
    sender: abi.Address
    receiver: abi.Address

LOGGER = logging.getLogger(__name__)

# mutations
@mutation()
def pay_fee() -> bool:
    msg_sender = get_metadata().msg_sender.lower()
    ledger = get_ledger()
    ether_asset_info = ledger.retrieve_asset(base_token = True, force_find = True)
    account_info_from = ledger.retrieve_account(account=msg_sender)
    account_info_to = ledger.retrieve_account(account=OPERATOR_WALLET)
    ledger.transfer(ether_asset_info['asset_id'], account_info_from['account_id'], account_info_to['account_id'], FEE_AMOUNT)

    user = LedgerUserFee.get(lambda r: r.user_address == msg_sender)
    if user is None: user = LedgerUserFee(user_address = msg_sender)

    user.set(total_amount=user.total_amount+float(FEE_AMOUNT))

    e = AmountPayed(
        amount=FEE_AMOUNT,
        sender=msg_sender,
        receiver=OPERATOR_WALLET
    )
    emit_event(e,tags=[msg_sender])

    LOGGER.info(f"{FEE_AMOUNT} eth (wei) fee payed from {msg_sender} to {OPERATOR_WALLET} for a total of {user.total_amount}")
    return True

@mutation()
def withdraw_all() -> bool:
    msg_sender = get_metadata().msg_sender.lower()
    ledger = get_ledger()
    ether_asset_info = ledger.retrieve_asset(base_token = True, force_find = True)
    account_info = ledger.retrieve_account(account=msg_sender)
    total_amount = ledger.balance(ether_asset_info['asset_id'], account_info['account_id'])
    ledger.withdraw(ether_asset_info['asset_id'], account_info['account_id'], total_amount)

    LOGGER.info(f"{total_amount} eth (wei) wthdrew from {msg_sender}")
    return True

@mutation(msg_sender=OPERATOR_WALLET)
def collect_fee() -> bool:
    metadata = get_metadata()
    msg_sender = metadata.msg_sender.lower()

    last_fee_collect_ts = helpers.max(r.timestamp for r in LedgerFeeCollected)
    if metadata.block_timestamp > last_fee_collect_ts + MINIMUM_COLLECT_FEE_INTERVAL:
        msg = f"Can't collect fee until {last_fee_collect_ts + MINIMUM_COLLECT_FEE_INTERVAL:}"
        LOGGER.error(msg)
        return False

    ledger = get_ledger()
    ether_asset_info = ledger.retrieve_asset(base_token = True, force_find = True)
    account_info = ledger.retrieve_account(account=msg_sender)
    current_balance = ledger.balance(ether_asset_info['asset_id'], account_info['account_id'])
    if current_balance < FEE_AMOUNT:
        msg = f"Not enough balance ({current_balance} of {FEE_AMOUNT})"
        LOGGER.error(msg)
        return False

    ledger.withdraw(ether_asset_info['asset_id'], account_info['account_id'], FEE_AMOUNT)

    LOGGER.info(f"{FEE_AMOUNT} eth (wei) wthdrew from {msg_sender}")
    return True
