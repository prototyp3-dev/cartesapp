from pydantic import BaseModel
import logging

from cartesapp.output import event, output, add_output, emit_event
from cartesapp.input import query, mutation
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata


# inputs
class UserMessages(Entity):
    address         = helpers.PrimaryKey(str)
    n_messages      = helpers.Required(int, default=0)

# inputs
class Payload(BaseModel):
    message: str

# mutations
@mutation()
def echo_and_update_count(payload: Payload) -> bool:
    msg_sender = get_metadata().msg_sender

    user = UserMessages.get(lambda r: r.address == msg_sender)
    if user is None: user = UserMessages(address = msg_sender)

    user.set(n_messages=user.n_messages+1)

    emit_event(payload.message,tags=[msg_sender])

    return True

# queries
@query()
def message_counts() -> bool:
    data = [r.to_dict() for r in UserMessages.select()]
    
    add_output(data)

    return True
