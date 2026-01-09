from pydantic import BaseModel
import logging

from cartesapp.output import emit_event, add_output
from cartesapp.input import mutation, query

LOGGER = logging.getLogger(__name__)

# inputs
class Payload(BaseModel):
    message: bytes

class QueryPayload(BaseModel):
    message: str

# mutations
@mutation()
def echo_mutation(payload: Payload) -> bool:
    LOGGER.info(f"Received advance payload = 0x{payload.message.hex()}")
    emit_event(payload.message)
    return True

# queries
@query()
def echo_query(payload: QueryPayload) -> bool:
    LOGGER.info(f"Received inspect payload = 0x{payload.message.hex()}")
    add_output(payload.message)
    return True
