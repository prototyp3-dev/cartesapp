

from cartesapp.output import event, output, add_output, emit_event
from cartesapp.input import query, mutation, index_input
from cartesapp.storage import Entity, helpers
from cartesapp.context import get_metadata
from common.model import UserMessage, UserMessages, MessagesQueryPayload, UserMessagesStore

# queries
@query()
def message_counts(payload: MessagesQueryPayload) -> bool:
    user_query = UserMessagesStore.select()

    if payload.user_address is not None:
        user_query = user_query.filter(lambda c: payload.user_address.lower() == c.address)

    user_messages_query = helpers.select((r.address, helpers.count(r.messages)) for r in user_query)
    user_messages_list = list(map(lambda r: UserMessage(**{k: v for k, v in zip(UserMessage.__fields__.keys(), r)}), user_messages_query.fetch()))

    data = UserMessages(data=user_messages_list,total=len(user_messages_list))

    add_output(data)

    return True
