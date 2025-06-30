from pydantic import BaseModel
from typing import Optional, List

from cartesapp.storage import Entity, helpers
from cartesapp.input import query
from cartesapp.output import output, add_output, IOType
from cartesapp.utils import int2hex256, hex2562int


# Settings

def get_settings_module():
    import types
    module_name = "io_index.settings"
    mod = types.ModuleType(module_name)
    return mod


###
# Indexer model and methods

class InOut(Entity):
    id              = helpers.PrimaryKey(int, auto=True)
    type            = helpers.Required(str) # helpers.Required(OutputType)
    msg_sender      = helpers.Required(str, 42, lazy=True, index=True)
    block_number    = helpers.Required(int, lazy=True, unsigned=True)
    block_timestamp = helpers.Required(int, lazy=True, index=True, unsigned=True)
    input_index     = helpers.Required(int, unsigned=True)
    output_index    = helpers.Optional(int, unsigned=True)
    app_contract    = helpers.Optional(str, 42, index=True, nullable=True)
    module          = helpers.Required(str)
    class_name      = helpers.Required(str)
    value           = helpers.Optional(int, lazy=True, size=64, index=True)
    eth_value       = helpers.Optional(str, 66, lazy=True) # hex encoded eth value
    tags            = helpers.Set("Tag")

class Tag(Entity):
    id              = helpers.PrimaryKey(int, auto=True)
    name            = helpers.Required(str, index=True)
    inout           = helpers.Required(InOut, index=True)


def add_input_index(metadata,app_contract,module,klass,tags=None,value=None):
    o = InOut(
        type            = IOType['input'].name.lower(),
        class_name      = klass,
        module          = module,
        msg_sender      = metadata.msg_sender.lower(),
        block_number    = metadata.block_number,
        block_timestamp = metadata.block_timestamp,
        input_index     = metadata.input_index,
        app_contract    = metadata.app_contract,
        value           = value
    )
    if app_contract is not None:
        o.app_contract = app_contract
    if tags is not None:
        for tag in tags:
            Tag(
                name = tag,
                inout = o
            )

def add_output_index(metadata,app_contract,output_type,output_index,output_module,output_class,tags=None,value=None,eth_value=None):
    o = InOut(
        type            = output_type.name.lower(),
        class_name      = output_class,
        module          = output_module,
        msg_sender      = metadata.msg_sender.lower(),
        block_number    = metadata.block_number,
        block_timestamp = metadata.block_timestamp,
        input_index     = metadata.input_index,
        app_contract    = metadata.app_contract,
        output_index    = output_index,
        value           = value,
    )
    if eth_value is not None:
        o.eth_value = eth_value if isinstance(eth_value, str) else int2hex256(eth_value)
    if app_contract is not None:
        o.app_contract = app_contract
    if tags is not None:
        helpers.get
        for tag in tags:
            Tag(
                name = tag,
                inout = o
            )



def get_indexes(**kwargs):
    tags = kwargs.get('tags')

    idx_query = InOut.select()

    if kwargs.get('module') is not None:
        idx_query = idx_query.filter(lambda o: o.module == kwargs.get('module').lower())
    if kwargs.get('type') is not None:
        idx_query = idx_query.filter(lambda o: o.type == kwargs.get('type').lower())
    if kwargs.get('msg_sender') is not None:
        idx_query = idx_query.filter(lambda o: o.msg_sender == kwargs.get('msg_sender').lower())
    if kwargs.get('block_timestamp_gte') is not None:
        idx_query = idx_query.filter(lambda o: o.block_timestamp >= kwargs.get('block_timestamp_gte'))
    if kwargs.get('block_timestamp_lte') is not None:
        idx_query = idx_query.filter(lambda o: o.block_timestamp <= kwargs.get('block_timestamp_lte'))
    if kwargs.get('value_gte') is not None:
        idx_query = idx_query.filter(lambda o: o.value >= kwargs.get('value_gte'))
    if kwargs.get('value_lte') is not None:
        idx_query = idx_query.filter(lambda o: o.value <= kwargs.get('value_lte'))
    if kwargs.get('eth_value_gte') is not None:
        idx_query = idx_query.filter(lambda o: o.eth_value >= kwargs.get('eth_value_gte'))
    if kwargs.get('eth_value_lte') is not None:
        idx_query = idx_query.filter(lambda o: o.eth_value <= kwargs.get('eth_value_lte'))
    if kwargs.get('input_index') is not None:
        idx_query = idx_query.filter(lambda o: o.input_index == kwargs.get('input_index'))
    if kwargs.get('input_index_lte') is not None:
        idx_query = idx_query.filter(lambda o: o.input_index <= kwargs.get('input_index'))
    if kwargs.get('input_index_gte') is not None:
        idx_query = idx_query.filter(lambda o: o.input_index >= kwargs.get('input_index'))
    if kwargs.get('app_contract') is not None:
        idx_query = idx_query.filter(lambda o: o.app_contract == kwargs.get('app_contract'))

    if tags is not None and len(tags) > 0:
        if kwargs.get('tags_or') is not None and kwargs['tags_or']:
            tags_fn = lambda t: t.name in tags
        else:
            tags_fn = lambda t: t.name in tags and helpers.count(t) == len(tags)
        reponse_query = helpers.distinct(
            o for o in idx_query for t in Tag if t.inout == o and tags_fn(t)
        )
    else:
        reponse_query = helpers.distinct(
            o for o in idx_query
        )

    total = reponse_query.count()

    if kwargs.get('order_by') is not None:
        order_dict = {"asc":lambda d: d,"desc":helpers.desc}
        order_dir_list = []
        order_by_list = kwargs.get('order_by').split(',')
        if kwargs.get('order_dir') is not None:
            order_dir_list = kwargs.get('order_dir').split(',')
        for idx,ord in enumerate(order_by_list):
            if idx < len(order_dir_list): dir_order = order_dict[order_dir_list[idx]]
            else: dir_order = order_dict["asc"]
            reponse_query = reponse_query.order_by(dir_order(getattr(InOut,ord)))

    out = []
    page = 1
    if kwargs.get('page') is not None:
        page = kwargs.get('page')
        if kwargs.get('page_size') is not None:
            out = reponse_query.page(page,kwargs.get('page_size'))
        else:
            out = reponse_query.page(page)
    else:
        out = reponse_query.fetch()


    return out, total, page


class IndexerPayload(BaseModel):
    tags: Optional[List[str]]
    type: Optional[str]
    msg_sender: Optional[str]
    block_timestamp_gte: Optional[int]
    block_timestamp_lte: Optional[int]
    value_gte: Optional[int]
    value_lte: Optional[int]
    eth_value_gte: Optional[str]
    eth_value_lte: Optional[str]
    module: Optional[str]
    input_index: Optional[int]
    app_contract: Optional[str]
    order_by:       Optional[str]
    order_dir:      Optional[str]
    page:           Optional[int]
    page_size:      Optional[int]

class OutputIndex(BaseModel):
    type: str
    module: str
    class_name: str
    input_index: int
    output_index: Optional[int]
    app_contract: Optional[str]


@output(module_name='indexer')
class IndexerOutput(BaseModel):
    data:   List[OutputIndex]
    total:  int
    page:   int

@query(module_name='indexer')
def indexer_query(payload: IndexerPayload) -> bool:
    out, total, page = get_indexes(**payload.dict())

    output_inds = [OutputIndex.parse_obj(r.to_dict()) for r in out]

    add_output(IndexerOutput(data=output_inds,total=total,page=page))

    return True
