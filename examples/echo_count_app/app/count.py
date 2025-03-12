from pydantic import BaseModel
from typing import Optional, List

from cartesi.abi import Address, Int, String

from cartesapp.output import event, output, add_output, emit_event
from cartesapp.input import query, mutation, index_input
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata


# storage
class UserMessagesStore(Entity):
    user_address    = helpers.PrimaryKey(str)
    n_messages      = helpers.Required(int, default=0)

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
    index: Int

class UserMessage(BaseModel):
    user_address:    str
    n_messages:      int

@output()
class UserMessages(BaseModel):
    data:   List[UserMessage]
    total:  int

# mutations
@mutation()
def echo_and_update_count(payload: Payload) -> bool:
    msg_sender = get_metadata().msg_sender.lower()

    user = UserMessagesStore.get(lambda r: r.user_address == msg_sender)
    if user is None: user = UserMessagesStore(user_address = msg_sender)

    user.set(n_messages=user.n_messages+1)

    e = MessageReceived(
        message=payload.message,
        user_address=msg_sender,
        index=user.n_messages
    )

    index_input(tags=[msg_sender])
    emit_event(e,tags=[msg_sender])

    return True

# queries
@query()
def message_counts(payload: MessagesQueryPayload) -> bool:
    messages_query = UserMessagesStore.select()

    if payload.user_address is not None:
        messages_query = messages_query.filter(lambda c: payload.user_address.lower() == c.user_address)

    messages = [UserMessage.parse_obj(r.to_dict()) for r in messages_query.fetch()]
    data = UserMessages(data=messages,total=len(messages))

    add_output(data)

    return True
