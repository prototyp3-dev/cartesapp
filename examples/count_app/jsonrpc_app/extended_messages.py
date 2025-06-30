from pydantic import BaseModel
from typing import Optional, List

from cartesapp.output import event, output, add_output, emit_event
from cartesapp.input import query, mutation, index_input
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata
from common.model import UserMessagesStore, MessagesStore

# inputs
class MessagesQueryPayload(BaseModel):
    user_address: Optional[str]

# outputs
class ExtendedMessage(BaseModel):
    index:          int
    message:        str
    user:           str
    created_at:     int

@output()
class ExtendedMessages(BaseModel):
    data:   List[ExtendedMessage]
    total:  int

# queries
@query()
def messages_and_users(payload: MessagesQueryPayload) -> bool:
    user_query = UserMessagesStore.select()

    if payload.user_address is not None:
        user_query = user_query.filter(lambda c: payload.user_address.lower() == c.address)

    messages_query = helpers.select((helpers.raw_sql('ROW_NUMBER() OVER (ORDER BY "r"."id" ASC)') ,r.message,r.user.address,r.created_at,) for r in MessagesStore if r.user in user_query)
    user_messages_list = list(map(lambda r: ExtendedMessage(**{k: v for k, v in zip(ExtendedMessage.__fields__.keys(), r)}), messages_query.fetch()))

    data = ExtendedMessages(data=user_messages_list,total=len(user_messages_list))

    add_output(data)

    return True
