from pydantic import BaseModel
import logging

from cartesi.abi import Address

from cartesapp.input import mutation
from cartesapp.context import Context

LOGGER = logging.getLogger(__name__)


# config

DAPP_RELAY_ADDRESS = "0xF5DE34d6BbC0446E2a45719E718efEbaaE179daE"


dapp_addresss_template = '''
// DApp Relay
export async function dappRelay(
    client:Signer,
    dappAddress:string,
    options?:AdvanceInputOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};
    const output = await advanceDAppRelay(client,dappAddress,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });
    return output;
}
'''

# Inputs

class DappRelayPayload(BaseModel):
    dapp_address: Address

@mutation(
    module_name='relay',
    msg_sender=DAPP_RELAY_ADDRESS,
    no_header=True,
    packed=True,
    specialized_template=dapp_addresss_template # don't create default template
)
def dapp_relay(payload: DappRelayPayload) -> bool:
    if Context.dapp_address is not None:
        msg = f"DApp address already set"
        LOGGER.error(msg)
        # add_output(msg,tags=['error'])
        return False
    
    Context.dapp_address = payload.dapp_address

    return True