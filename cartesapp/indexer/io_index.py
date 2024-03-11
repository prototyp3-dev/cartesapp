from pydantic import BaseModel
from typing import Optional, List

from cartesapp.storage import Entity, helpers
from cartesapp.input import query
from cartesapp.output import output, add_output, IOType


###
# Indexer model and methods

class InOut(Entity):
    id              = helpers.PrimaryKey(int, auto=True)
    type            = helpers.Required(str) # helpers.Required(OutputType)
    msg_sender      = helpers.Required(str, 42, lazy=True, index=True)
    block_number    = helpers.Required(int, lazy=True)
    timestamp       = helpers.Required(int, lazy=True, index=True)
    epoch_index     = helpers.Required(int, lazy=True)
    input_index     = helpers.Required(int)
    output_index    = helpers.Optional(int)
    module          = helpers.Required(str)
    data_class      = helpers.Required(str)
    tags            = helpers.Set("Tag")

class Tag(Entity):
    id              = helpers.PrimaryKey(int, auto=True)
    name            = helpers.Required(str, index=True)
    inout           = helpers.Required(InOut, index=True)


def add_input_index(metadata,module,klass,tags=None):
    o = InOut(
        type            = IOType['input'].name.lower(),
        data_class      = klass,
        module          = module,
        msg_sender      = metadata.msg_sender.lower(),
        block_number    = metadata.block_number,
        timestamp       = metadata.timestamp,
        epoch_index     = metadata.epoch_index,
        input_index     = metadata.input_index
    )
    if tags is not None:
        for tag in tags:
            t = Tag(
                name = tag,
                inout = o
            )

def add_output_index(metadata,output_type,output_index,output_module,output_class,tags=None):
    o = InOut(
        type            = output_type.name.lower(),
        data_class      = output_class,
        module          = output_module,
        msg_sender      = metadata.msg_sender.lower(),
        block_number    = metadata.block_number,
        timestamp       = metadata.timestamp,
        epoch_index     = metadata.epoch_index,
        input_index     = metadata.input_index,
        output_index    = output_index
    )
    if tags is not None:
        for tag in tags:
            t = Tag(
                name = tag,
                inout = o
            )

def get_indexes(**kwargs):
    tags = kwargs.get('tags')

    idx_query = InOut.select()

    tag_query = Tag.select()

    if tags is not None and len(tags) > 0:
        tag_query = tag_query.filter(lambda t: t.name in tags)

    if kwargs.get('module') is not None:
        idx_query = idx_query.filter(lambda o: o.module == kwargs.get('module').lower())
    if kwargs.get('type') is not None:
        idx_query = idx_query.filter(lambda o: o.type == kwargs.get('type').lower())
    if kwargs.get('msg_sender') is not None:
        idx_query = idx_query.filter(lambda o: o.msg_sender == kwargs.get('msg_sender').lower())
    if kwargs.get('timestamp_gte') is not None:
        idx_query = idx_query.filter(lambda o: o.timestamp >= kwargs.get('timestamp_gte'))
    if kwargs.get('timestamp_lte') is not None:
        idx_query = idx_query.filter(lambda o: o.timestamp <= kwargs.get('timestamp_lte'))
    if kwargs.get('input_index') is not None:
        idx_query = idx_query.filter(lambda o: o.input_index == kwargs.get('input_index'))

    if tags is not None and len(tags) > 0:
        query = helpers.distinct(
            [o.type,o.module,o.data_class,o.input_index,o.output_index]
            for o in idx_query for t in tag_query if t.output == o and helpers.count(t) == len(tags)
        )
    else:
        query = helpers.distinct(
            [o.type,o.module,o.data_class,o.input_index,o.output_index]
            for o in idx_query for t in tag_query if t.output == o
        )

    return query.fetch()




class IndexerPayload(BaseModel):
    tags: Optional[List[str]]
    type: Optional[str]
    msg_sender: Optional[str]
    timestamp_gte: Optional[int]
    timestamp_lte: Optional[int]
    module: Optional[str]
    input_index: Optional[int]

class OutputIndex(BaseModel):
    type: str
    module: str
    class_name: str
    input_index: int
    output_index: int


@output(module_name='indexer')
class IndexerOutput(BaseModel):
    data:   List[OutputIndex]

@query(module_name='indexer')
def indexer_query(payload: IndexerPayload) -> bool:
    out = get_indexes(**payload.dict())

    output_inds = [OutputIndex(type=r[0],module=r[1],class_name=r[2],input_index=r[3],output_index=r[4]) for r in out]
    
    add_output(IndexerOutput(data=output_inds))

    return True
