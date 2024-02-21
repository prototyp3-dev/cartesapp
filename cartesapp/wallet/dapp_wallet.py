from pydantic import BaseModel
from typing import Optional, List, Dict, Tuple, Annotated, get_type_hints
import logging

from cartesi.abi import Address, UInt256, Int256, Bytes, Bool, ABIType

from cartesapp.storage import Entity, helpers
from cartesapp.input import mutation, query
from cartesapp.output import output, add_output, event, emit_event, contract_call, submit_contract_call
from cartesapp.context import get_metadata, get_dapp_address
from cartesapp.utils import int2hex256, hex2562int, uint2hex256, hex2562uint

LOGGER = logging.getLogger(__name__)


# config

ETHER_PORTAL_ADDRESS = "0xFfdbe43d4c855BF7e0f105c400A50857f53AB044"
ERC20_PORTAL_ADDRESS = "0x9C21AEb2093C32DDbC53eEF24B873BDCd1aDa1DB"
ERC721_PORTAL_ADDRESS = "0x237F8DD094C0e47f4236f12b4Fa01d6Dae89fb87"


ether_deposit_template = '''
// Deposit Ether
export async function depositEther(
    client:Signer,
    dappAddress:string,
    amount:ethers.BigNumberish,
    options?:EtherDepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceEtherDeposit(client,dappAddress,amount,options).catch(
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
    dappAddress:string,
    tokenAddress:string,
    amount:ethers.BigNumberish,
    options?:ERC20DepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceERC20Deposit(client,dappAddress,tokenAddress,amount,options).catch(
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
    dappAddress:string,
    tokenAddress:string,
    tokenId:ethers.BigNumberish,
    options?:ERC721DepositOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceERC721Deposit(client,dappAddress,tokenAddress,tokenId,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

def hash_class(s):
    return hash(s.name)

setattr(ABIType, "__hash__", hash_class)
UInt256List = Annotated[List[int], ABIType('uint256[]')]
Int256List = Annotated[List[int], ABIType('int256[]')]


# Model

class Wallet(Entity):
    owner           = helpers.PrimaryKey(str, 42)
    ether           = helpers.Optional("Ether")
    erc20           = helpers.Set("Erc20")
    erc721          = helpers.Set("Erc721")
    erc1155         = helpers.Set("Erc1155")

class Ether(Entity):
    wallet          = helpers.PrimaryKey("Wallet")
    amount          = helpers.Required(str, 66) # hex
    
class Erc20(Entity):
    wallet          = helpers.Required("Wallet")
    address         = helpers.Required(str, 42)
    amount          = helpers.Required(str, 66) # hex
    helpers.PrimaryKey(wallet,address)

class Erc721(Entity):
    wallet          = helpers.Required("Wallet")
    address         = helpers.Required(str, 42)
    ids             = helpers.Set("Erc721Id")
    helpers.PrimaryKey(wallet,address)

class Erc721Id(Entity):
    id              = helpers.Required(str, 66)
    erc721          = helpers.Required("Erc721")
    helpers.PrimaryKey(id,erc721)

class Erc1155(Entity):
    wallet          = helpers.Required("Wallet")
    address         = helpers.Required(str, 42)
    ids             = helpers.Set("Erc1155Id")
    helpers.PrimaryKey(wallet,address)

class Erc1155Id(Entity):
    erc1155         = helpers.Required("Erc1155")
    amount          = helpers.Required(str, 66) # hex


# Helpers

def get_wallet(user_address: str | None = None):
    if user_address is None: # try to get from metadata
        metadata = get_metadata()
        if metadata is None:
            raise Exception("Can't get wallet from metadata (empty metadata)")
        user_address = metadata.msg_sender
    
    wallet = Wallet.select(lambda r: r.owner == user_address.lower()).first()
    if wallet is None:
        wallet = Wallet(owner = user_address.lower())
    return wallet
        
# Inputs

class DepositEtherPayload(BaseModel):
    sender: Address
    amount: UInt256
    execLayerData: Bytes

class WithdrawEtherPayload(BaseModel):
    amount: UInt256
    execLayerData: Bytes

class TransferEtherPayload(BaseModel):
    receiver: Address
    amount: UInt256
    execLayerData: Bytes

class DepositErc20Payload(BaseModel):
    result: Bool
    token: Address
    sender: Address
    amount: UInt256
    execLayerData: Bytes

class WithdrawErc20Payload(BaseModel):
    token: Address
    amount: UInt256
    execLayerData: Bytes

class TransferErc20Payload(BaseModel):
    token: Address
    receiver: Address
    amount: UInt256
    execLayerData: Bytes

class DepositErc721Payload(BaseModel):
    token: Address
    sender: Address
    id: UInt256
    execLayerData: Bytes

class WithdrawErc721Payload(BaseModel):
    token: Address
    id: UInt256
    execLayerData: Bytes

class TransferErc721Payload(BaseModel):
    token: Address
    receiver: Address
    id: UInt256
    execLayerData: Bytes

class BalancePayload(BaseModel):
    address: str


# Output

@event(module_name='wallet')
class EtherEvent(BaseModel):
    user:       Address
    mod_amount: Int256
    balance:    UInt256

@contract_call(module_name='wallet')
class withdrawEther(BaseModel):
    user:       Address
    amount:     UInt256

@event(module_name='wallet')
class Erc20Event(BaseModel):
    user:       Address
    address:    Address
    mod_amount: Int256
    balance:    UInt256

@contract_call(module_name='wallet')
class withdrawErc20(BaseModel):
    user:       Address
    amount:     UInt256


@event(module_name='wallet')
class Erc721Event(BaseModel):
    user:       Address
    address:    Address
    mod_id:     Int256
    ids:        UInt256List

@contract_call(module_name='wallet')
class withdrawErc721(BaseModel):
    sender:     Address
    receiver:   Address
    id:         UInt256


# @event(module_name='wallet')
# class Erc1155Event(BaseModel):
#     user:       Address
#     address:    Address
#     mod_ids:    Int256List
#     mod_amounts:Int256List
#     ids:        UInt256List
#     balances:   UInt256List



###
# Mutations

# Ether

@mutation(
    module_name='wallet',
    msg_sender=ETHER_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=ether_deposit_template # don't create default template
)
def deposit_ether(payload: DepositEtherPayload) -> bool:
    # get wallet
    wallet = get_wallet(payload.sender)

    # get/create ether wallet
    if wallet.ether is None:
        wallet.ether = Ether(wallet=wallet,amount='0x00')
    ether_wallet = wallet.ether

    # add deposit
    new_balance = payload.amount + hex2562uint(ether_wallet.amount)
    ether_wallet.amount = uint2hex256(new_balance)
    
    # send event
    asset_event = EtherEvent(
        user = wallet.owner,
        mod_amount = payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","ether",wallet.owner])

    LOGGER.debug(f"{payload.sender} deposited {payload.amount} ether (wei)")

    return True

@mutation(module_name='wallet')
def EtherWithdraw(payload: WithdrawEtherPayload) -> bool: # camel case name to maintain other hlf standard
    dapp_address = get_dapp_address()
    if dapp_address is None:
        raise Exception("Dapp Address is not set")

    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()

    # get/create ether wallet
    if wallet.ether is None:
        wallet.ether = Ether(wallet=wallet,amount='0x00')
    
    # check balance
    uint_balance = hex2562uint(wallet.ether.amount)
    if uint_balance < payload.amount:
        raise Exception("Wallet has insufficient ether funds")

    new_balance = uint_balance - payload.amount
    wallet.ether.amount = uint2hex256(new_balance)

    # submit contract call
    withdrawal = withdrawEther(
        user = wallet.owner,
        amount = payload.amount
    )
    submit_contract_call(dapp_address,withdrawal,tags=["wallet","ether","withdrawal",wallet.owner])

    # send event
    asset_event = EtherEvent(
        user = wallet.owner,
        mod_amount = -payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","ether",wallet.owner])

    LOGGER.debug(f"{metadata.msg_sender} withdrew {payload.amount} ether (wei)")

    return True

@mutation(module_name='wallet')
def EtherTransfer(payload: TransferEtherPayload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    return transfer_ether(metadata.msg_sender,payload.receiver,payload.amount)

def transfer_ether(sender: str,receiver: str, amount: int):
    # get wallet
    wallet = get_wallet(sender)

    # get/create ether wallet
    if wallet.ether is None:
        wallet.ether = Ether(wallet=wallet,amount='0x0')

    # check balance
    uint_balance = hex2562uint(wallet.ether.amount)
    if uint_balance < amount:
        raise Exception("Wallet has insufficient ether funds")

    new_balance = uint_balance - amount
    wallet.ether.amount = uint2hex256(new_balance)

    # get receiver wallet
    receiver_wallet = get_wallet(receiver)

    # get/create receiver ether wallet
    if receiver_wallet.ether is None:
        receiver_wallet.ether = Ether(wallet=receiver_wallet,amount='0x00')

    uint_receiver_balance = hex2562uint(receiver_wallet.ether.amount)
    new_receiver_balance = uint_receiver_balance + amount
    receiver_wallet.ether.amount = uint2hex256(new_receiver_balance)

    # send event
    ether_easset_eventvent = EtherEvent(
        user = wallet.owner,
        mod_amount = -amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","ether",wallet.owner])

    # send event
    receiver_asset_event = EtherEvent(
        user = receiver_wallet.owner,
        mod_amount = amount,
        balance = new_receiver_balance
    )
    emit_event(receiver_asset_event,tags=["wallet","ether",receiver_wallet.owner])

    LOGGER.debug(f"{sender} transfered {amount} ether (wei) to {receiver}")

    return True


# Erc20

@mutation(
    module_name='wallet',
    msg_sender=ERC20_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=erc20_deposit_template # don't create default template
)
def deposit_erc20(payload: DepositErc20Payload) -> bool:
    if not payload.result:
        raise Exception("Erc20 deposit failed on base layer")

    # get wallet
    wallet = get_wallet(payload.sender)

    # get/create erc20 wallet
    erc20_wallet = Erc20.select(lambda r: r.wallet == wallet and r.address == payload.token.lower()).first()
    if erc20_wallet is None:
        erc20_wallet = Erc20(wallet=wallet,address=payload.token.lower(),amount='0x00')
    
    # add deposit
    new_balance = payload.amount + hex2562uint(erc20_wallet.amount)
    erc20_wallet.amount = uint2hex256(new_balance)
    
    # send event
    asset_event = Erc20Event(
        user = wallet.owner,
        address = erc20_wallet.address,
        mod_amount = payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc20",erc20_wallet.address,wallet.owner])

    LOGGER.debug(f"{payload.sender} deposited {payload.amount} of {erc20_wallet.address} tokens")

    return True

@mutation(module_name='wallet')
def Erc20Withdraw(payload: WithdrawErc20Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()

    # get/create erc20 wallet
    erc20_wallet = Erc20.select(lambda r: r.wallet == wallet and r.address == payload.token.lower()).first()
    if erc20_wallet is None:
        erc20_wallet = Erc20(wallet=wallet,address=payload.token.lower(),amount='0x00')
    
    # check balance
    uint_balance = hex2562uint(erc20_wallet.amount)
    if uint_balance < payload.amount:
        raise Exception("Wallet has insufficient erc20 funds")

    new_balance = uint_balance - payload.amount
    erc20_wallet.amount = uint2hex256(new_balance)

    # submit contract call
    withdrawal = withdrawErc20(
        user = wallet.owner,
        amount = payload.amount
    )
    submit_contract_call(erc20_wallet.address,"transfer",withdrawal,tags=["wallet","erc20","withdrawal",erc20_wallet.address,wallet.owner])

    # send event
    asset_event = Erc20Event(
        user = wallet.owner,
        address = erc20_wallet.address,
        mod_amount = -payload.amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc20",erc20_wallet.address,wallet.owner])

    LOGGER.debug(f"{metadata.msg_sender} withdrew {payload.amount} of {erc20_wallet.address} tokens")

    return True


@mutation(module_name='wallet')
def Erc20Transfer(payload: TransferErc20Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()
    return transfer_erc20(payload.token,metadata.msg_sender,payload.receiver,payload.amount)

def transfer_erc20(token: str, sender: str,receiver: str, amount: int):
    # get wallet
    wallet = get_wallet(sender)

    # get/create erc20 wallet
    erc20_wallet = Erc20.select(lambda r: r.wallet == wallet and r.address == token.lower()).first()
    if erc20_wallet is None:
        erc20_wallet = Erc20(wallet=wallet,address=token.lower(),amount='0x00')
    
    # check balance
    uint_balance = hex2562uint(erc20_wallet.amount)
    if uint_balance < amount:
        raise Exception("Wallet has insufficient erc20 funds")

    new_balance = uint_balance - amount
    erc20_wallet.amount = uint2hex256(new_balance)

    # get receiver wallet
    receiver_wallet = get_wallet(receiver)

    # get/create receiver erc20 wallet
    receiver_erc20_wallet = Erc20.select(lambda r: r.wallet == receiver_wallet and r.address == token.lower()).first()
    if receiver_erc20_wallet is None:
        receiver_erc20_wallet = Erc20(wallet=receiver_wallet,address=token.lower(),amount='0x00')
    
    uint_receiver_balance = hex2562uint(receiver_erc20_wallet.amount)
    new_receiver_balance = uint_receiver_balance + amount
    receiver_erc20_wallet.amount = uint2hex256(new_receiver_balance)

    # send event
    asset_event = Erc20Event(
        user = wallet.owner,
        address = erc20_wallet.address,
        mod_amount = -amount,
        balance = new_balance
    )
    emit_event(asset_event,tags=["wallet","erc20",erc20_wallet.address,wallet.owner])

    # send event
    receiver_asset_event = Erc20Event(
        user = receiver_wallet.owner,
        address = receiver_erc20_wallet.address,
        mod_amount = amount,
        balance = new_receiver_balance
    )
    emit_event(receiver_asset_event,tags=["wallet","erc20",erc20_wallet.address,receiver_wallet.owner])

    LOGGER.debug(f"{sender} transfered {amount} of {token} to {receiver}")

    return True


# Erc721

@mutation(
    module_name='wallet',
    msg_sender=ERC721_PORTAL_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=erc721_deposit_template # don't create default template
)
def deposit_erc721(payload: DepositErc721Payload) -> bool:
    # get wallet
    wallet = get_wallet(payload.sender)

    # get/create erc721 wallet
    erc721_wallet = Erc721.select(lambda r: r.wallet == wallet and r.address == payload.token.lower()).first()
    if erc721_wallet is None:
        erc721_wallet = Erc721(wallet=wallet,address=payload.token.lower())
    
    # add erc721
    Erc721Id(id=uint2hex256(payload.id),erc721=erc721_wallet)

    # send event
    asset_event = Erc721Event(
        user = wallet.owner,
        address = erc721_wallet.address,
        mod_id = payload.id,
        ids = [hex2562uint(a.id) for a in erc721_wallet.ids]
    )
    emit_event(asset_event,tags=["wallet","erc721",erc721_wallet.address,wallet.owner])

    LOGGER.debug(f"{payload.sender} deposited id {payload.id} of {erc721_wallet.address}")

    return True

@mutation(module_name='wallet')
def Erc721Withdraw(payload: WithdrawErc721Payload) -> bool: # camel case name to maintain other hlf standard
    dapp_address = get_dapp_address()
    if dapp_address is None:
        raise Exception("Dapp Address is not set")

    metadata = get_metadata()

    # get wallet
    wallet = get_wallet()

    # get/create erc721 wallet
    erc721_wallet = Erc721.select(lambda r: r.wallet == wallet and r.address == payload.token.lower()).first()
    if erc721_wallet is None:
        erc721_wallet = Erc721(wallet=wallet,address=payload.token.lower())

    # check balance
    erc721_id = erc721_wallet.ids.select(lambda r: r.id == uint2hex256(payload.id)).first()
    if erc721_id is None:
        raise Exception("Wallet has not erc721 id")

    erc721_id.delete()

    # submit contract call
    withdrawal = withdrawErc721(
        sender = dapp_address,
        receiver = wallet.owner,
        id = payload.id
    )
    submit_contract_call(erc721_wallet.address,"safeTransferFrom",withdrawal,tags=["wallet","erc721","withdrawal",erc721_wallet.address,wallet.owner])

    # send event
    asset_event = Erc721Event(
        user = wallet.owner,
        address = erc721_wallet.address,
        mod_id = -payload.id,
        ids = [hex2562uint(a.id) for a in erc721_wallet.ids]
    )
    emit_event(asset_event,tags=["wallet","erc721",erc721_wallet.address,wallet.owner])

    LOGGER.debug(f"{metadata.msg_sender} withdrew id {payload.id} of {erc721_wallet.address}")

    return True


@mutation(module_name='wallet')
def Erc721Transfer(payload: TransferErc721Payload) -> bool: # camel case name to maintain other hlf standard
    metadata = get_metadata()
    return transfer_erc721(payload.token,metadata.msg_sender,payload.receiver,payload.id)

def transfer_erc721(token: str, sender: str,receiver: str, token_id: int):
    # get wallet
    wallet = get_wallet(sender)

    # get/create erc721 wallet
    erc721_wallet = Erc721.select(lambda r: r.wallet == wallet and r.address == token.lower()).first()
    if erc721_wallet is None:
        erc721_wallet = Erc721(wallet=wallet,address=token.lower())
    
    # check balance
    erc721_id = erc721_wallet.ids.select(lambda r: r.id == uint2hex256(token_id)).first()
    if erc721_id is None:
        raise Exception("Wallet has not erc721 id")

    erc721_id.delete()

    # get receiver wallet
    receiver_wallet = get_wallet(receiver)

    # get/create receiver erc721 wallet
    receiver_erc721_wallet = Erc721.select(lambda r: r.wallet == receiver_wallet and r.address == token.lower()).first()
    if receiver_erc721_wallet is None:
        receiver_erc721_wallet = Erc721(wallet=receiver_wallet,address=token.lower())
    
    # add erc721
    Erc721Id(id=uint2hex256(token_id),erc721=receiver_erc721_wallet)

    # send event
    asset_event = Erc721Event(
        user = wallet.owner,
        address = erc721_wallet.address,
        mod_id = -token_id,
        ids = [hex2562uint(a.id) for a in erc721_wallet.ids]
    )
    emit_event(asset_event,tags=["wallet","erc721",erc721_wallet.address,wallet.owner])

    # send event
    receiver_asset_event = Erc721Event(
        user = receiver_wallet.owner,
        address = receiver_erc721_wallet.address,
        mod_id = token_id,
        ids = [hex2562uint(a.id) for a in receiver_erc721_wallet.ids]
    )
    emit_event(receiver_asset_event,tags=["wallet","erc721",erc721_wallet.address,receiver_wallet.owner])

    LOGGER.debug(f"{sender} transfered {token_id} of {token} to {receiver}")

    return True




@output(module_name='wallet')
class WalletOutput(BaseModel):
    ether:      Optional[int]
    erc20:      Optional[Dict[str,int]]
    erc721:     Optional[Dict[str,List[int]]]
    erc1155:    Optional[Dict[str,Tuple[List[int],List[int]]]]


# Queries

@query(module_name='wallet', path_params=['address'])
def balance(payload: BalancePayload) -> bool:
    user_wallet = get_wallet(payload.address)

    wallet = {}
    if user_wallet.ether is not None:
        wallet["ether"] = hex2562uint(user_wallet.ether.amount)
    if len(user_wallet.erc20) > 0:
        wallet["erc20"] = {}
        for asset in user_wallet.erc20:
            wallet["erc20"][asset.address] = hex2562uint(asset.amount)
    if len(user_wallet.erc721) > 0:
        wallet["erc721"] = {}
        for asset in user_wallet.erc721:
            wallet["erc721"][asset.address] = [hex2562uint(a.id) for a in user_wallet.erc721.ids]
    if len(user_wallet.erc1155) > 0:
        wallet["erc1155"] = {}
        for asset in user_wallet.erc1155:
            wallet["erc1155"][asset.address] = (asset.ids,[hex2562int(a) for a in asset.amounts])

    print("=== debug ===")
    print(wallet)
    add_output(WalletOutput.parse_obj(wallet))

    return True

