from pydantic import BaseModel
from typing import Optional, List
import itertools

from cartesapp.output import event, output, add_output, emit_event
from cartesapp.input import query, mutation, index_input
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata
from common.model import UserMessagesStore

# inputs
class MessagesQueryPayload(BaseModel):
    user_address: Optional[str]

# outputs
class UserMessage(BaseModel):
    user_address:    str
    n_messages:      int

@output()
class UserMessages(BaseModel):
    data:   List[UserMessage]
    total:  int

# queries
@query()
def message_counts(payload: MessagesQueryPayload) -> bool:
    user_query = UserMessagesStore.select()

    if payload.user_address is not None:
        user_query = user_query.filter(lambda c: payload.user_address.lower() == c.address)

    user_messages_query = helpers.select((r.address, r.messages) for r in user_query.order_by(UserMessagesStore.address))
    user_messages_counts = [(key, sum(1 for _,_ in value))
        for key, value in itertools.groupby(user_messages_query.fetch(), lambda x: x[0])]

    user_messages_list = list(map(lambda r: UserMessage(**{k: v for k, v in zip(UserMessage.__fields__.keys(), r)}), user_messages_counts))

    data = UserMessages(data=user_messages_list,total=len(user_messages_list))

    add_output(data)

    return True
