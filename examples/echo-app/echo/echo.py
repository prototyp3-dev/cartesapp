from pydantic import BaseModel
import logging

from cartesapp.output import emit_event
from cartesapp.input import mutation

# inputs
class Payload(BaseModel):
    message: bytes

# mutations
@mutation()
def simple_echo(payload: Payload) -> bool:
    emit_event(payload.message)
    return True
