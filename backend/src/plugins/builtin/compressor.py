from plugins.define import define_stage
from plugins.params import param_int

none_compressor = define_stage(
    stage="compressor",
    name="none",
    config_schema={"type": "object", "additionalProperties": False},
    description="不压缩上下文，把当前检索结果原样交给生成器。",
)


@none_compressor.run
async def run_none(data, params, ctx):
    return data


top_n = define_stage(
    stage="compressor",
    name="top_n",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"n": {"type": "integer"}},
    },
    default_params={"n": 5},
    description="只保留排序后的前 N 条段落，控制 prompt 长度、降低噪音和费用。",
)


@top_n.run
async def run_top_n(data, params, ctx):
    """Keep the first n passages after rerank to fit the context window."""
    retrieved = list(data.get("retrieved") or [])
    limit = max(0, param_int(params, "n", 5))
    clipped = retrieved[:limit]
    for rank, item in enumerate(clipped, start=1):
        item["rank"] = rank
    data["retrieved"] = clipped
    return data


COMPRESSOR_PLUGINS = [none_compressor, top_n]
