from pydantic import BaseModel
import logging

from cartesapp.output import emit_event, event
from cartesapp.input import mutation
from cartesi import abi

from cartesapplib.wallet import app_wallet
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata

# static conf
OPERATOR_WALLET = f"{1:#042x}".lower()
FEE_AMOUNT = 10_000_000_000_000_000
MINIMUM_COLLECT_FEE_INTERVAL = 86400

# storage
class UserFee(Entity):
    user_address    = helpers.PrimaryKey(str)
    total_amount    = helpers.Required(float, default=0)

class FeeCollected(Entity):
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
    wallet = app_wallet.get_wallet()
    wallet.transfer_ether(OPERATOR_WALLET,FEE_AMOUNT)

    user = UserFee.get(lambda r: r.user_address == msg_sender)
    if user is None: user = UserFee(user_address = msg_sender)

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
    wallet = app_wallet.get_wallet()
    total_amount = wallet.get_ether_balance()
    new_balance = wallet.withdraw_ether(total_amount)

    LOGGER.info(f"{total_amount} eth (wei) wthdrew from {msg_sender}")
    return True

@mutation()
def collect_fee() -> bool:
    metadata = get_metadata()
    msg_sender = metadata.msg_sender.lower()
    if msg_sender != OPERATOR_WALLET:
        msg = f"Sender is not operator: {OPERATOR_WALLET}"
        LOGGER.error(msg)
        return False

    last_fee_collect_ts = helpers.max(r.timestamp for r in FeeCollected)
    if metadata.block_timestamp > last_fee_collect_ts + MINIMUM_COLLECT_FEE_INTERVAL:
        msg = f"Can't collect fee until {last_fee_collect_ts + MINIMUM_COLLECT_FEE_INTERVAL:}"
        LOGGER.error(msg)
        return False

    wallet = app_wallet.get_wallet()
    new_balance = wallet.withdraw_ether(FEE_AMOUNT)

    LOGGER.info(f"{FEE_AMOUNT} eth (wei) wthdrew from {msg_sender}")
    return True
