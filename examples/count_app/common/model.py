from pydantic import BaseModel
from typing import Optional, List

from cartesi.abi import Address, Int, String, UInt256

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

class UserMessage(BaseModel):
    user_address:    str
    n_messages:      int

@output()
class UserMessages(BaseModel):
    data:   List[UserMessage]
    total:  int

class ExtendedMessage(BaseModel):
    index:          int
    message:        str
    user:           str
    created_at:     int

@output()
class ExtendedMessages(BaseModel):
    data:   List[ExtendedMessage]
    total:  int
