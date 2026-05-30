from pydantic import BaseModel
from typing import Optional, Dict, Any, List #, Dict, Tuple, Annotated, get_type_hints

from cartesi.abi import Address, UInt256, Bytes, Bytes32, Bool

from test_config import ETHER_PORTAL_ADDRESS, ERC20_PORTAL_ADDRESS, ERC721_PORTAL_ADDRESS, \
    ERC1155_SINGLE_PORTAL_ADDRESS, ERC1155_BATCH_PORTAL_ADDRESS

class DepositEtherPayload(BaseModel):
    sender: Address
    amount: UInt256
    exec_layer_data: Bytes

class DepositErc20Payload(BaseModel):
    token: Address
    sender: Address
    amount: UInt256
    exec_layer_data: Bytes

class DepositErc20v1_5Payload(BaseModel):
    success: Bool
    token: Address
    sender: Address
    amount: UInt256
    exec_layer_data: Bytes

class DepositErc721Payload(BaseModel):
    token: Address
    sender: Address
    token_id: UInt256
    data_bytes: Bytes

class DataBytes(BaseModel):
    base_layer_data: Bytes
    exec_layer_data: Bytes

class DepositErc1155SinglePayload(BaseModel):
    token: Address
    sender: Address
    token_id: UInt256
    amount: UInt256
    data_bytes: Bytes

class DepositErc1155BatchPayload(BaseModel):
    token: Address
    sender: Address
    batch_bytes: Bytes

class BatchBytes(BaseModel):
    token_ids: List[UInt256]
    amounts: List[UInt256]
    base_layer_data: Bytes
    exec_layer_data: Bytes

class WithdrawEtherPayload(BaseModel):
    amount: UInt256
    exec_layer_data: Bytes

class WithdrawErc20Payload(BaseModel):
    token: Address
    amount: UInt256
    exec_layer_data: Bytes

class WithdrawErc721Payload(BaseModel):
    token: Address
    token_id: UInt256
    exec_layer_data: Bytes

class WithdrawErc1155SinglePayload(BaseModel):
    token: Address
    token_id: UInt256
    amount: UInt256
    exec_layer_data: Bytes

class WithdrawErc1155BatchPayload(BaseModel):
    token: Address
    token_ids: List[UInt256]
    amounts: List[UInt256]
    exec_layer_data: Bytes

class TransferEtherPayload(BaseModel):
    receiver: Bytes32
    amount: UInt256
    exec_layer_data: Bytes

class TransferErc20Payload(BaseModel):
    token: Address
    receiver: Bytes32
    amount: UInt256
    exec_layer_data: Bytes

class TransferErc721Payload(BaseModel):
    token: Address
    receiver: Bytes32
    token_id: UInt256
    exec_layer_data: Bytes

class TransferErc1155SinglePayload(BaseModel):
    token: Address
    receiver: Bytes32
    token_id: UInt256
    amount: UInt256
    exec_layer_data: Bytes

class TransferErc1155BatchPayload(BaseModel):
    token: Address
    receiver: Bytes32
    token_ids: List[UInt256]
    amounts: List[UInt256]
    exec_layer_data: Bytes

class Erc20Voucher(BaseModel):
    receiver:       Address
    amount:         UInt256

class Erc721Voucher(BaseModel):
    sender:         Address
    receiver:       Address
    token_id:       UInt256

class Erc1155SingleVoucher(BaseModel):
    sender:         Address
    receiver:       Address
    token_id:       UInt256
    amount:         UInt256
    data:           Bytes

class Erc1155BatchVoucher(BaseModel):
    sender:         Address
    receiver:       Address
    token_ids:       List[UInt256]
    amounts:         List[UInt256]
    data:           Bytes

class BalancePayload(BaseModel):
    account: str
    token: Optional[str]
    token_id: Optional[str]
    exec_layer_data: Optional[str]

class SupplyPayload(BaseModel):
    token: Optional[str]
    token_id: Optional[str]
    exec_layer_data: Optional[str]

def generate_json_input(selector, model: BaseModel) -> dict:
    request_data: Dict[str,Any] = {"method":selector}
    model_dict = model.dict(exclude_none=True)
    if len(model_dict) > 0:
        request_data["params"] = []
        for val in model_dict.values():
            if val is None:
                break
            request_data["params"].append(val)

    return request_data
