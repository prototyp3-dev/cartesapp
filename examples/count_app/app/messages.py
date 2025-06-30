from pydantic import BaseModel
from typing import Optional, List

from cartesi.abi import Address, Int, String, UInt256

from cartesapp.output import event, output, add_output, emit_event
from cartesapp.input import query, mutation, index_input
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata

from common.model import UserMessagesStore, MessagesStore

# inputs
class Payload(BaseModel):
    message: str

class MessagesQueryPayload(BaseModel):
    user_address: Optional[str]

# outputs
@event()
class MessageReceived(BaseModel):
    message: String
    user_address: Address
    timestamp: UInt256
    index: Int

class Message(BaseModel):
    message:        str
    created_at:     int

@output()
class Messages(BaseModel):
    data:   List[Message]
    total:  int

# mutations
@mutation()
def echo_and_update_count(payload: Payload) -> bool:
    metadata = get_metadata()
    msg_sender = metadata.msg_sender.lower()

    user = UserMessagesStore.get(lambda r: msg_sender == r.address)
    if not user: user = UserMessagesStore(address = msg_sender)

    message = MessagesStore(user=user,message=payload.message,created_at=metadata.block_timestamp)

    e = MessageReceived(
        message=payload.message,
        user_address=msg_sender,
        timestamp=metadata.block_timestamp,
        index=len(user.messages)
    )

    index_input(tags=[msg_sender])
    emit_event(e,tags=[msg_sender])

    return True

# queries
@query()
def messages(payload: MessagesQueryPayload) -> bool:
    messages_query = MessagesStore.select()

    if payload.user_address is not None:
        messages_query = messages_query.filter(lambda r: payload.user_address.lower() == r.user.address)

    query_result = messages_query.fetch()
    messages = [Message.parse_obj(r.to_dict()) for r in query_result]
    data = Messages(data=messages,total=len(messages))

    add_output(data)

    return True
