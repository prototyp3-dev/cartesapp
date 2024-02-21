from pydantic import BaseModel
from typing import Optional, List

from cartesapp.storage import Entity, helpers
from cartesapp.input import query
from cartesapp.output import output, add_output


###
# Indexer model and methods

class Output(Entity):
    id              = helpers.PrimaryKey(int, auto=True)
    output_type     = helpers.Required(str) # helpers.Required(OutputType)
    msg_sender      = helpers.Required(str, 42, lazy=True, index=True)
    block_number    = helpers.Required(int, lazy=True)
    timestamp       = helpers.Required(int, lazy=True, index=True)
    epoch_index     = helpers.Required(int, lazy=True)
    input_index     = helpers.Required(int)
    output_index    = helpers.Required(int)
    output_module   = helpers.Required(str)
    output_class    = helpers.Required(str)
    tags            = helpers.Set("OutputTag")

class OutputTag(Entity):
    id              = helpers.PrimaryKey(int, auto=True)
    name            = helpers.Required(str, index=True)
    output          = helpers.Required(Output, index=True)


def add_output_index(metadata,output_type,output_index,output_module,output_class,tags=None):
    o = Output(
        output_type     = output_type.name.lower(),
        output_class    = output_class,
        output_module   = output_module,
        msg_sender      = metadata.msg_sender.lower(),
        block_number    = metadata.block_number,
        timestamp       = metadata.timestamp,
        epoch_index     = metadata.epoch_index,
        input_index     = metadata.input_index,
        output_index    = output_index
    )
    if tags is not None:
        for tag in tags:
            t = OutputTag(
                name = tag,
                output = o
            )

def get_output_indexes(**kwargs):
    tags = kwargs.get('tags')

    output_query = Output.select()

    tag_query = OutputTag.select()

    if tags is not None and len(tags) > 0:
        tag_query = tag_query.filter(lambda t: t.name in tags)

    if kwargs.get('module') is not None:
        output_query = output_query.filter(lambda o: o.output_module == kwargs.get('module').lower())
    if kwargs.get('output_type') is not None:
        output_query = output_query.filter(lambda o: o.output_type == kwargs.get('output_type').lower())
    if kwargs.get('msg_sender') is not None:
        output_query = output_query.filter(lambda o: o.msg_sender == kwargs.get('msg_sender').lower())
    if kwargs.get('timestamp_gte') is not None:
        output_query = output_query.filter(lambda o: o.timestamp >= kwargs.get('timestamp_gte'))
    if kwargs.get('timestamp_lte') is not None:
        output_query = output_query.filter(lambda o: o.timestamp <= kwargs.get('timestamp_lte'))
    if kwargs.get('input_index') is not None:
        output_query = output_query.filter(lambda o: o.input_index == kwargs.get('input_index'))

    if tags is not None and len(tags) > 0:
        query = helpers.distinct(
            [o.output_type,o.output_module,o.output_class,o.input_index,o.output_index]
            for o in output_query for t in tag_query if t.output == o and helpers.count(t) == len(tags)
        )
    else:
        query = helpers.distinct(
            [o.output_type,o.output_module,o.output_class,o.input_index,o.output_index]
            for o in output_query for t in tag_query if t.output == o
        )

    return query.fetch()




class IndexerPayload(BaseModel):
    tags: Optional[List[str]]
    output_type: Optional[str]
    msg_sender: Optional[str]
    timestamp_gte: Optional[int]
    timestamp_lte: Optional[int]
    module: Optional[str]
    input_index: Optional[int]

class OutputIndex(BaseModel):
    output_type: str
    module: str
    class_name: str
    input_index: int
    output_index: int


@output(module_name='indexer')
class IndexerOutput(BaseModel):
    data:   List[OutputIndex]

@query(module_name='indexer')
def indexer_query(payload: IndexerPayload) -> bool:
    out = get_output_indexes(**payload.dict())

    output_inds = [OutputIndex(output_type=r[0],module=r[1],class_name=r[2],input_index=r[3],output_index=r[4]) for r in out]
    
    add_output(IndexerOutput(data=output_inds))

    return True
