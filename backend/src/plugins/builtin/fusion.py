from engine.retrieval import reciprocal_rank_fusion
from plugins.define import define_stage
from plugins.params import param_int

rrf = define_stage(
    stage="fusion",
    name="rrf",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"k": {"type": "integer"}},
    },
    default_params={"k": 60},
    description="用 Reciprocal Rank Fusion 合并多路召回结果，互补向量检索与关键词检索的盲区。",
)


@rrf.run
async def run_rrf(data, params, ctx):
    lists = data.get("retrieved_lists") or {}
    ranked = [items for items in lists.values() if items]
    if not ranked:
        data["retrieved"] = data.get("retrieved") or []
        return data
    if len(ranked) == 1:
        data["retrieved"] = ranked[0]
        return data
    fused = reciprocal_rank_fusion(ranked, k=param_int(params, "k", 60))
    data["retrieved"] = fused
    return data


FUSION_PLUGINS = [rrf]
