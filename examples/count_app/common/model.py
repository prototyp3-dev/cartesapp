from pydantic import BaseModel
from typing import Optional, List

from cartesapp.output import event, output
from cartesapp.storage import Entity, helpers


# storage
class UserMessagesStore(Entity):
    address         = helpers.PrimaryKey(str, 42)
    messages        = helpers.Set("MessagesStore")

class MessagesStore(Entity):
    message         = helpers.Required(str)
    created_at      = helpers.Required(int)
    user            = helpers.Required(UserMessagesStore)
