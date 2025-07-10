from pydantic import BaseModel
from typing import Optional, List, Dict, Tuple, Annotated, get_type_hints
import logging

from cartesi.abi import Address, UInt256, UInt64, Int256, Bytes, ABIType, decode_to_model

from cartesapp.storage import Entity, helpers
from cartesapp.input import mutation, query
from cartesapp.output import output, add_output, event, emit_event, contract_call, submit_contract_call
from cartesapp.context import get_metadata, get_app_contract
from cartesapp.utils import int2hex256, hex2562int, uint2hex256, hex2562uint

LOGGER = logging.getLogger(__name__)


# config

ETHER_PORTAL_ADDRESS = "0xc70076a466789B595b50959cdc261227F0D70051"
ERC20_PORTAL_ADDRESS = "0xc700D6aDd016eECd59d989C028214Eaa0fCC0051"
ERC721_PORTAL_ADDRESS = "0xc700d52F5290e978e9CAe7D1E092935263b60051"
ERC1155_SINGLE_PORTAL_ADDRESS = "0xc700A261279aFC6F755A3a67D86ae43E2eBD0051"
ERC1155_BATCH_PORTAL_ADDRESS = "0xc700A2e5531E720a2434433b6ccf4c0eA2400051"


ether_deposit_template = '''
// Deposit Ether
export async function depositEther(
    client:Signer,
    appContract:string,
    amount:ethers.BigNumberish,
    options?:EtherDepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceEtherDeposit(client,appContract,amount,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

erc20_deposit_template = '''
// Deposit Erc20
export async function depositErc20(
    client:Signer,
    appContract:string,
    tokenAddress:string,
    amount:ethers.BigNumberish,
    options?:ERC20DepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceERC20Deposit(client,appContract,tokenAddress,amount,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

erc721_deposit_template = '''
// Deposit Erc721
export async function depositErc721(
    client:Signer,
    appContract:string,
    tokenAddress:string,
    tokenId:ethers.BigNumberish,
    options?:ERC721DepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceERC721Deposit(client,appContract,tokenAddress,tokenId,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

erc1155_single_deposit_template = ''
'''
// Deposit Erc1155 single
export async function depositErc1155Single(
    client:Signer,
    appContract:string,
    tokenAddress:string,
    tokenId:ethers.BigNumberish,
    amount:ethers.BigNumberish,
    options?:ERC721DepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceERC1155SingleDeposit(client,appContract,tokenAddress,tokenId,amount,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

erc1155_batch_deposit_template = ''
'''
// Deposit Erc1155 batch
export async function depositErc1155Batch(
    client:Signer,
    appContract:string,
    tokenAddress:string,
    tokenIds:ethers.BigNumberish,
    amounts:ethers.BigNumberish,
    options?:ERC721DepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceERC1155BatchDeposit(client,appContract,tokenAddress,tokenIds,amounts,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

# Settings

def get_settings_module():
    import types
    module_name = "wallet.settings"
    mod = types.ModuleType(module_name)
    mod.NOTICE_FORMAT = "header_abi"
    return mod


# Model

class WalletStore(Entity):
    owner           = helpers.PrimaryKey(str, 66) # normally address (42 bytes), but it can be any internal ids (non-withdrawable)
    ether           = helpers.Optional("Ether")
    erc20           = helpers.Set("Erc20")
    erc721          = helpers.Set("Erc721")
    erc1155         = helpers.Set("Erc1155")

class Ether(Entity):
    wallet          = helpers.PrimaryKey("WalletStore")
    amount          = helpers.Required(str, 66) # hex

class Erc20(Entity):
    wallet          = helpers.Required("WalletStore")
    address         = helpers.Required(str, 42)
    amount          = helpers.Required(str, 66) # hex
    helpers.PrimaryKey(wallet,address)

class Erc721(Entity):
    wallet          = helpers.Required("WalletStore")
    address         = helpers.Required(str, 42)
    ids             = helpers.Set("Erc721Id")
    helpers.PrimaryKey(wallet,address)

class Erc721Id(Entity):
    token_id        = helpers.Required(str, 66)
    erc721          = helpers.Required("Erc721")
    helpers.PrimaryKey(token_id,erc721)

class Erc1155(Entity):
    wallet          = helpers.Required("WalletStore")
    address         = helpers.Required(str, 42)
    ids             = helpers.Set("Erc1155Id")
    helpers.PrimaryKey(wallet,address)

class Erc1155Id(Entity):
    erc1155         = helpers.Required("Erc1155")
    token_id        = helpers.Required(str, 66)
    amount          = helpers.Required(str, 66) # hex
    helpers.PrimaryKey(token_id,erc1155)


# Inputs

class DepositEtherPayload(BaseModel):
    sender: Address
    amount: UInt256
    exec_layer_data: Bytes

class WithdrawEtherPayload(BaseModel):
    amount: UInt256
    exec_layer_data: Bytes

class TransferEtherPayload(BaseModel):
    receiver: Address
    amount: UInt256
    exec_layer_data: Bytes

class DepositErc20Payload(BaseModel):
    token: Address
    sender: Address
    amount: UInt256
    exec_layer_data: Bytes

class WithdrawErc20Payload(BaseModel):
    token: Address
    amount: UInt256
    exec_layer_data: Bytes

class TransferErc20Payload(BaseModel):
    token: Address
    receiver: Address
    amount: UInt256
    exec_layer_data: Bytes

class DepositErc721Payload(BaseModel):
    token: Address
    sender: Address
    id: UInt256
    exec_layer_data: Bytes

class WithdrawErc721Payload(BaseModel):
    token: Address
    id: UInt256
    exec_layer_data: Bytes

class TransferErc721Payload(BaseModel):
    token: Address
    receiver: Address
    id: UInt256
    exec_layer_data: Bytes

class DepositErc1155SinglePayload(BaseModel):
    token: Address
    sender: Address
    id: UInt256
    amount: UInt256
    exec_layer_data: Bytes

class WithdrawErc1155SinglePayload(BaseModel):
    token: Address
    id: UInt256
    amount: UInt256
    exec_layer_data: Bytes

class TransferErc1155SinglePayload(BaseModel):
    token: Address
    receiver: Address
    id: UInt256
    amount: UInt256
    exec_layer_data: Bytes

class DepositErc1155BatchPayload(BaseModel):
    token: Address
    sender: Address
    batch_value: Bytes

class BatchValue(BaseModel):
    ids: List[UInt256]
    amounts: List[UInt256]
    base_layer_data: Bytes
    exec_layer_data: Bytes

class WithdrawErc1155BatchPayload(BaseModel):
    token: Address
    ids: List[UInt256]
    amounts: List[UInt256]
    exec_layer_data: Bytes

class TransferErc1155BatchPayload(BaseModel):
    token: Address
    receiver: Address
    ids: List[UInt256]
    amounts: List[UInt256]
    exec_layer_data: Bytes

class BalancePayload(BaseModel):
    address: str


# Output

@event(module_name='wallet')
class EtherEvent(BaseModel):
    timestamp:  UInt64
    user:       Address
    mod_amount: Int256
    balance:    UInt256

@event(module_name='wallet')
class Erc20Event(BaseModel):
    timestamp:  UInt64
    user:       Address
    address:    Address
    mod_amount: Int256
    balance:    UInt256

@contract_call(module_name='wallet')
class WithdrawErc20(BaseModel):
    user:       Address
    amount:     UInt256

@event(module_name='wallet')
class Erc721Event(BaseModel):
    timestamp:  UInt64
    user:       Address
    address:    Address
    mod_id:     Int256
    ids:        List[UInt256]

@contract_call(module_name='wallet')
class WithdrawErc721(BaseModel):
    sender:     Address
    receiver:   Address
    id:         UInt256

@event(module_name='wallet')
class Erc1155Event(BaseModel):
    timestamp:  UInt64
    user:       Address
    address:    Address
    mod_ids:    List[Int256]
    mod_amounts:List[Int256]
    ids:        List[UInt256]
    amounts:    List[UInt256]

@contract_call(module_name='wallet')
class WithdrawErc1155Single(BaseModel):
    sender:     Address
    receiver:   Address
    id:         UInt256
    amount:     UInt256
    data:       Bytes

@contract_call(module_name='wallet')
class WithdrawErc1155Batch(BaseModel):
    sender:     Address
    receiver:   Address
    ids:        List[UInt256]
    amounts:    List[UInt256]
    data:       Bytes

@output(module_name='wallet')
class WalletBalance(BaseModel):
    ether:      Optional[int]
    erc20:      Optional[Dict[str,int]]
    erc721:     Optional[Dict[str,List[int]]]
    erc1155:    Optional[Dict[str,Dict[int,int]]]


###
# Wallet model

class Wallet:
    _store: WalletStore
    def __init__(self,wallet_store):
        self._store = wallet_store

    def owner(self) -> str:
        return self._store.owner

    def balance(self) -> WalletBalance:
        wallet = {}
        if self._store.ether is not None:
            wallet["ether"] = self.get_ether_balance()
        if len(self._store.erc20) > 0:
            wallet["erc20"] = {}
            for asset in self._store.erc20:
                wallet["erc20"][asset.address] = hex2562uint(asset.amount)
        if len(self._store.erc721) > 0:
            wallet["erc721"] = {}
            for asset in self._store.erc721:
                wallet["erc721"][asset.address] = [hex2562uint(a.token_id) for a in self._store.erc721.ids]
        if len(self._store.erc1155) > 0:
            wallet["erc1155"] = {}
            for asset in self._store.erc1155:
                wallet["erc1155"][asset.address] = {hex2562uint(r.token_id):hex2562uint(r.amount) for r in asset.ids}

        return WalletBalance.parse_obj(wallet)

    def get_ether(self) -> Ether:
        if self._store.ether is None:
            self._store.ether = Ether(wallet=self._store.owner,amount=uint2hex256(0))
        return self._store.ether

    def get_ether_balance(self) -> int:
        return hex2562uint(self.get_ether().amount)

    def deposit_ether(self,amount: int) -> int:
        ether_wallet = self.get_ether()

        # add deposit
        new_balance = amount + hex2562uint(ether_wallet.amount)
        ether_wallet.amount = uint2hex256(new_balance)

        return new_balance

    def withdraw_ether(self,amount: int) -> int:
        ether_wallet = self.get_ether()

        # check balance
        uint_balance = hex2562uint(ether_wallet.amount)
        if uint_balance < amount:
            raise Exception(f"Wallet {self.owner()} has insufficient ether funds")

        new_balance = uint_balance - amount
        ether_wallet.amount = uint2hex256(new_balance)

        return new_balance

    def transfer_ether(self, receiver: str, amount: int) -> Tuple[int,int]:
        new_balance = self.withdraw_ether(amount)
        new_receiver_balance = get_wallet(receiver).deposit_ether(amount)

        return new_balance, new_receiver_balance

    def get_erc20(self, token: str) -> Erc20:
        erc20_wallet = self._store.erc20.select(lambda r: r.address == token.lower()).get()
        if erc20_wallet is None:
            erc20_wallet = self._store.erc20.create(address=token.lower(),amount=uint2hex256(0))

        return erc20_wallet

    def get_erc20_balance(self, token: str) -> int:
        return hex2562uint(self.get_erc20(token).amount)

    def deposit_erc20(self, token: str, amount: int) -> int:
        erc20_wallet = self.get_erc20(token)

        # add deposit
        new_balance = amount + hex2562uint(erc20_wallet.amount)
        erc20_wallet.amount = uint2hex256(new_balance)

        return new_balance

    def withdraw_erc20(self, token: str, amount: int) -> int:
        erc20_wallet = self.get_erc20(token)

        # check balance
        uint_balance = hex2562uint(erc20_wallet.amount)
        if uint_balance < amount:
            raise Exception(f"Wallet {self.owner()} has insufficient erc20 {token} funds")

        new_balance = uint_balance - amount
        erc20_wallet.amount = uint2hex256(new_balance)

        return new_balance

    def transfer_erc20(self, token: str, receiver: str, amount: int) -> Tuple[int,int]:
        new_balance = self.withdraw_erc20(token,amount)
        new_receiver_balance = get_wallet(receiver).deposit_erc20(token,amount)

        return new_balance, new_receiver_balance

    def get_erc721(self, token: str) -> Erc721:
        erc721_wallet = self._store.erc721.select(lambda r: r.address == token.lower()).get()
        if erc721_wallet is None:
            erc721_wallet = self._store.erc721.create(address=token.lower())

        return erc721_wallet

    def has_erc721_id(self, token: str) -> bool:
        return helpers.count(r for r in self.get_erc721(token).ids if r.token_id == token) > 0

    def get_erc721_balance(self, token: str) -> List[int]:
        return [hex2562uint(r.token_id) for r in self.get_erc721(token).ids]
    get_erc721_ids = get_erc721_balance

    def deposit_erc721(self, token: str, id: int) -> List[int]:
        erc721_wallet = self.get_erc721(token)
        erc721_id = Erc721Id.get(lambda r: r.token_id == uint2hex256(id))

        if erc721_id is not None:
            raise Exception(f"Id {id} already have owner {erc721_id.erc721.wallet.owner()}")

        # add erc721
        erc721_wallet.ids.create(token_id=uint2hex256(id))

        return [hex2562uint(r.token_id) for r in erc721_wallet.ids]

    def withdraw_erc721(self, token: str, id: int) -> List[int]:
        erc721_wallet = self.get_erc721(token)
        erc721_id = Erc721Id.get(lambda r: r.token_id == uint2hex256(id))

        if erc721_id is None:
            raise Exception(f"Id {id} have no owner")

        if erc721_id not in erc721_wallet.ids:
            raise Exception(f"Not owner of id {id}")

        # remove erc721
        erc721_id.delete()

        return [hex2562uint(r.token_id) for r in erc721_wallet.ids]

    def transfer_erc721(self, token: str, receiver: str, amount: int) -> Tuple[List[int],List[int]]:
        new_balance = self.withdraw_erc721(token,amount)
        new_receiver_balance = get_wallet(receiver).deposit_erc721(token,amount)

        return new_balance, new_receiver_balance

    def get_erc1155(self, token: str) -> Erc721:
        erc1155_wallet = self._store.erc1155.select(lambda r: r.address == token.lower()).get()
        if erc1155_wallet is None:
            erc1155_wallet = self._store.erc1155.create(address=token.lower())

        return erc1155_wallet

    def get_erc1155_id_list(self, token: str) -> Tuple[List[int],List[int]]:
        erc1155_wallet = self.get_erc1155(token)
        return tuple(zip(*[[hex2562uint(r.token_id),hex2562uint(r.amount)] for r in erc1155_wallet.ids]))

    def get_erc1155_balance(self, token: str) -> Dict[int,int]:
            erc1155_wallet = self.get_erc1155(token)
            return {hex2562uint(r.token_id):hex2562uint(r.amount) for r in erc1155_wallet.ids}

    def get_erc1155_id(self, token: str, id: int) -> Erc1155Id:
        erc1155_wallet = self.get_erc1155(token)
        erc1155_id = helpers.select(r for r in erc1155_wallet.ids if r.token_id == uint2hex256(id)).get()
        if erc1155_id is None:
            erc1155_id = erc1155_wallet.ids.create(token_id=uint2hex256(id),amount=uint2hex256(0))
        return erc1155_id

    def get_erc1155_id_balance(self, token: str, id: int) -> int:
        erc1155_id = self.get_erc1155_id(token, id)
        return hex2562uint(erc1155_id.amount)

    def deposit_erc1155(self, token: str, id: int, amount: int) -> Tuple[List[int],List[int]]:
        erc1155_id = self.get_erc1155_id(token, id)

        # add deposit
        new_balance = amount + hex2562uint(erc1155_id.amount)
        erc1155_id.amount = uint2hex256(new_balance)

        return self.get_erc1155_id_list(token)

    def withdraw_erc1155(self, token: str, id: int, amount: int) -> Tuple[List[int],List[int]]:
        erc1155_id = self.get_erc1155_id(token, id)

        # check balance
        uint_balance = hex2562uint(erc1155_id.amount)
        if uint_balance < amount:
            raise Exception(f"Wallet {self.owner()} has insufficient erc1155 {token} {id} funds")

        new_balance = uint_balance - amount
        erc1155_id.amount = uint2hex256(new_balance)

        return self.get_erc1155_id_list(token)

    def transfer_erc1155(self, token: str, receiver: str, id: int, amount: int) -> Tuple[Tuple[List[int],List[int]],Tuple[List[int],List[int]]]:
        new_balance = self.withdraw_erc1155(token,id,amount)
        new_receiver_balance = get_wallet(receiver).deposit_erc1155(token,id,amount)

        return new_balance, new_receiver_balance

# Helpers

def get_wallet(owner: str | None = None) -> Wallet:
    if owner is None: # try to get from metadata
        metadata = get_metadata()
        if metadata is None:
            raise Exception("Can't get wallet from metadata (empty metadata)")
        owner = metadata.msg_sender

    wallet_st = WalletStore.select(lambda r: r.owner == owner.lower()).first()
    if wallet_st is None:
        wallet_st = WalletStore(owner = owner.lower())
    return Wallet(wallet_st)


###
# Mutations

# Ether

@mutation(
    module_name='wallet',
    msg_sender=ETHER_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=False #ether_deposit_template # don't create default template
)
def deposit_ether(payload: DepositEtherPayload) -> bool:
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet(payload.sender)
    new_balance = wallet.deposit_ether(payload.amount)

    # send event
    asset_event = EtherEvent(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        mod_amount = payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","ether","deposit",wallet.owner()])

    LOGGER.debug(f"{payload.sender} deposited {payload.amount} ether (wei)")
    return True

@mutation(module_name='wallet')
def EtherWithdraw(payload: WithdrawEtherPayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance = wallet.withdraw_ether(payload.amount)

    # submit contract call (address.call{ether_value}())
    submit_contract_call(wallet.owner(),payload.amount,tags=["wallet","ether","withdrawal",wallet.owner()])

    # send event
    asset_event = EtherEvent(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        mod_amount = -payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","ether","withdrawal",wallet.owner()])

    LOGGER.debug(f"{wallet.owner()} withdrew {payload.amount} ether (wei)")
    return True

@mutation(module_name='wallet')
def EtherTransfer(payload: TransferEtherPayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()

    new_balance, new_receiver_balance = \
        wallet.transfer_ether(payload.receiver,payload.amount)

    # send event
    asset_event = EtherEvent(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        mod_amount = -payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","ether","transfer",wallet.owner()])

    # send event
    receiver_asset_event = EtherEvent(
        timestamp = metadata.block_timestamp,
        user = payload.receiver,
        mod_amount = payload.amount,
        balance = new_receiver_balance
    )
    emit_event(receiver_asset_event,tags=["wallet","ether","transfer",payload.receiver])

    LOGGER.debug(f"{wallet.owner()} transfered {payload.amount} ether (wei) to {payload.receiver}")
    return True


# Erc20

@mutation(
    module_name='wallet',
    msg_sender=ERC20_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=False #erc20_deposit_template # don't create default template
)
def deposit_erc20(payload: DepositErc20Payload) -> bool:
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet(payload.sender)
    new_balance = wallet.deposit_erc20(payload.token,payload.amount)

    # send event
    asset_event = Erc20Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_amount = payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc20","deposit",payload.token,wallet.owner()])

    LOGGER.debug(f"{payload.sender} deposited {payload.amount} of {payload.token} tokens")
    return True

@mutation(module_name='wallet')
def Erc20Withdraw(payload: WithdrawErc20Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance = wallet.withdraw_erc20(payload.token,payload.amount)

    # submit contract call
    withdrawal = WithdrawErc20(
        user = wallet.owner(),
        amount = payload.amount
    )
    submit_contract_call(payload.token,"transfer",withdrawal,tags=["wallet","erc20","withdrawal",payload.token,wallet.owner()])

    # send event
    asset_event = Erc20Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_amount = -payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc20","withdrawal",payload.token,wallet.owner()])

    LOGGER.debug(f"{metadata.msg_sender} withdrew {payload.amount} of {payload.token} tokens")
    return True

@mutation(module_name='wallet')
def Erc20Transfer(payload: TransferErc20Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance, new_receiver_balance = \
            wallet.transfer_erc20(payload.token,payload.receiver,payload.amount)

    # send event
    asset_event = Erc20Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_amount = -payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc20","transfer",payload.token,wallet.owner()])

    # send event
    receiver_asset_event = Erc20Event(
        timestamp = metadata.block_timestamp,
        user = payload.receiver,
        address = payload.token,
        mod_amount = payload.amount,
        balance = new_receiver_balance
    )
    emit_event(receiver_asset_event,tags=["wallet","erc20","transfer",payload.token,payload.receiver])

    LOGGER.debug(f"{metadata.msg_sender} transfered {payload.amount} of {payload.token} to {payload.receiver}")

    return True


# Erc721

@mutation(
    module_name='wallet',
    msg_sender=ERC721_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=False #erc721_deposit_template # don't create default template
)
def deposit_erc721(payload: DepositErc721Payload) -> bool:
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet(payload.sender)
    new_ids_balance = wallet.deposit_erc721(payload.token,payload.id)

    # send event
    asset_event = Erc721Event(
        timestamp =metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_id = payload.id,
        ids = new_ids_balance
    )
    emit_event(asset_event,tags=["wallet","erc721","deposit",payload.token,wallet.owner()])

    LOGGER.debug(f"{payload.sender} deposited id {payload.id} of {payload.token} token")
    return True

@mutation(module_name='wallet')
def Erc721Withdraw(payload: WithdrawErc721Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_ids_balance = wallet.withdraw_erc721(payload.token,payload.id)

    # submit contract call
    withdrawal = WithdrawErc721(
        sender = metadata.app_contract,
        receiver = wallet.owner(),
        id = payload.id
    )
    submit_contract_call(payload.token,"safeTransferFrom",withdrawal,tags=["wallet","erc721","withdrawal",payload.token,wallet.owner()])

    # send event
    asset_event = Erc721Event(
        timestamp =metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_id = -payload.id,
        ids = new_ids_balance
    )
    emit_event(asset_event,tags=["wallet","erc721","withdrawal",payload.token,wallet.owner()])

    LOGGER.debug(f"{metadata.msg_sender} withdrew id {payload.id} of {payload.token} token")
    return True

@mutation(module_name='wallet')
def Erc721Transfer(payload: TransferErc721Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance, new_receiver_balance = \
            wallet.transfer_erc721(payload.token,payload.receiver,payload.id)

    # send event
    asset_event = Erc721Event(
        timestamp =metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_id = -payload.id,
        ids = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc721","transfer",payload.token,wallet.owner()])

    # send event
    receiver_asset_event = Erc721Event(
        timestamp =metadata.block_timestamp,
        user = payload.receiver,
        address = payload.token,
        mod_id = payload.id,
        ids = new_receiver_balance
    )
    emit_event(receiver_asset_event,tags=["wallet","erc721","transfer",payload.token,payload.id,payload.receiver])

    LOGGER.debug(f"{metadata.msg_sender} transfered id {payload.id} of {payload.token} token to {payload.receiver}")
    return True

# Erc1155

@mutation(
    module_name='wallet',
    msg_sender=ERC1155_SINGLE_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=False #erc1155_single_deposit_template # don't create default template
)
def deposit_erc1155_single(payload: DepositErc1155SinglePayload) -> bool:
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet(payload.sender)
    new_balance = wallet.deposit_erc1155(payload.token,payload.id,payload.amount)

    # send event
    asset_event = Erc1155Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_ids = [payload.id],
        mod_amounts = [payload.amount],
        ids = new_balance[0],
        amounts = new_balance[1]
    )
    emit_event(asset_event,tags=["wallet","erc1155","deposit",payload.token,payload.id,wallet.owner()])

    LOGGER.debug(f"{payload.sender} deposited id {payload.id} the {payload.amount} amount of {payload.token} token")
    return True

@mutation(module_name='wallet')
def Erc1155SingleWithdraw(payload: WithdrawErc1155SinglePayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance = wallet.withdraw_erc1155(payload.token,payload.id,payload.amount)

    # submit contract call
    withdrawal = WithdrawErc1155Single(
        sender = metadata.app_contract,
        receiver = wallet.owner(),
        id = payload.id,
        amount = payload.amount,
        data = b''
    )
    submit_contract_call(payload.token,"safeTransferFrom",withdrawal,tags=["wallet","erc1155","withdrawal",payload.token,payload.id,wallet.owner()])

    # send event
    asset_event = Erc1155Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_ids = [-payload.id],
        mod_amounts = [-payload.amount],
        ids = new_balance[0],
        amounts = new_balance[1]
    )
    emit_event(asset_event,tags=["wallet","erc1155","withdrawal",payload.token,payload.id,wallet.owner()])

    LOGGER.debug(f"{metadata.msg_sender} withdrew id {payload.id} the {payload.amount} amount of {payload.token} token")
    return True

@mutation(module_name='wallet')
def Erc1155SingleTransfer(payload: TransferErc1155SinglePayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance, new_receiver_balance = \
        wallet.transfer_erc1155(payload.token,payload.receiver,payload.id,payload.amount)

    # send event
    asset_event = Erc1155Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_ids = [-payload.id],
        mod_amounts = [-payload.amount],
        ids = new_balance[0],
        amounts = new_balance[1]
    )
    emit_event(asset_event,tags=["wallet","erc1155","transfer",payload.token,payload.id,wallet.owner()])

    # send event
    receiver_asset_event = Erc1155Event(
        timestamp =metadata.block_timestamp,
        user = payload.receiver,
        address = payload.token,
        mod_ids = [payload.id],
        mod_amounts = [payload.amount],
        ids = new_receiver_balance[0],
        amounts = new_receiver_balance[1]
    )
    emit_event(receiver_asset_event,tags=["wallet","erc1155","transfer",payload.token,payload.id,payload.receiver])

    LOGGER.debug(f"{metadata.msg_sender} transfered id {payload.id} the {payload.amount} amount of {payload.token} token to {payload.receiver}")
    return True

@mutation(
    module_name='wallet',
    msg_sender=ERC1155_BATCH_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=False #erc1155_batch_deposit_template # don't create default template
)
def deposit_erc1155_batch(payload: DepositErc1155BatchPayload) -> bool:
    metadata = get_metadata()

    batch_value: BatchValue = decode_to_model(payload.batch_value,BatchValue)
    # get wallet
    wallet = get_wallet(payload.sender)
    new_balance = [[],[]]
    for i in range(min(len(batch_value.ids),len(batch_value.amounts))):
        new_balance = wallet.deposit_erc1155(payload.token,batch_value.ids[i],batch_value.amounts[i])

    # send event
    asset_event = Erc1155Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_ids = batch_value.ids,
        mod_amounts = batch_value.amounts,
        ids = new_balance[0],
        amounts = new_balance[1]
    )
    tags = ["wallet","erc1155","deposit",payload.token,wallet.owner()]
    tags.extend(batch_value.ids)
    emit_event(asset_event,tags=tags)

    LOGGER.debug(f"{payload.sender} deposited ids {batch_value.ids} the {batch_value.amounts} amounts of {payload.token} token")
    return True

@mutation(module_name='wallet')
def Erc1155BatchWithdraw(payload: WithdrawErc1155BatchPayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance = [[],[]]
    for i in range(min(len(payload.ids),len(payload.amounts))):
        new_balance = wallet.withdraw_erc1155(payload.token,payload.ids[i],payload.amounts[i])

    # submit contract call
    withdrawal = WithdrawErc1155Batch(
        sender = metadata.app_contract,
        receiver = wallet.owner(),
        ids = payload.ids,
        amounts = payload.amounts,
        data = b''
    )
    tags = ["wallet","erc1155","withdrawal",payload.token,wallet.owner()]
    tags.extend(payload.ids)
    submit_contract_call(payload.token,"safeBatchTransferFrom",withdrawal,tags=tags)

    # send event
    asset_event = Erc1155Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_ids = list(map(lambda x: -x, payload.ids)),
        mod_amounts = list(map(lambda x: -x, payload.amounts)),
        ids = new_balance[0],
        amounts = new_balance[1]
    )
    emit_event(asset_event,tags=tags)

    LOGGER.debug(f"{metadata.msg_sender} withdrew ids {payload.ids} the {payload.amounts} amounts of {payload.token} token")
    return True

@mutation(module_name='wallet')
def Erc1155BatchTransfer(payload: TransferErc1155BatchPayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()
    new_balance = [[],[]]
    new_receiver_balance = [[],[]]
    for i in range(min(len(payload.ids),len(payload.amounts))):
        new_balance, new_receiver_balance = \
            wallet.transfer_erc1155(payload.token,payload.receiver,payload.ids[i],payload.amounts[i])

    # send event
    asset_event = Erc1155Event(
        timestamp = metadata.block_timestamp,
        user = wallet.owner(),
        address = payload.token,
        mod_ids = list(map(lambda x: -x, payload.ids)),
        mod_amounts = list(map(lambda x: -x, payload.amounts)),
        ids = new_balance[0],
        amounts = new_balance[1]
    )
    tags = ["wallet","erc1155","transfer",payload.token,wallet.owner()]
    tags.extend(payload.ids)
    emit_event(asset_event,tags=["wallet","erc1155",payload.token,wallet.owner()])

    # send event
    receiver_asset_event = Erc1155Event(
        timestamp =metadata.block_timestamp,
        user = payload.receiver,
        address = payload.token,
        mod_ids = payload.ids,
        mod_amounts = payload.amounts,
        ids = new_receiver_balance[0],
        amounts = new_receiver_balance[1]
    )
    tags = ["wallet","erc1155","transfer",payload.token,payload.receiver]
    tags.extend(payload.ids)
    emit_event(receiver_asset_event,tags=tags)

    LOGGER.debug(f"{metadata.msg_sender} transfered ids {payload.ids} the {payload.amounts} amounts of {payload.token} token to {payload.receiver}")
    return True

# Queries
@query(module_name='wallet', path_params=['address'])
def balance(payload: BalancePayload) -> bool:
    user_balance = get_wallet(payload.address).balance()
    add_output(user_balance)
    return True
