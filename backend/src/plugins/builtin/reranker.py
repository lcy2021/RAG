from engine.retrieval import parse_json_object
from plugins.define import define_stage
from plugins.params import param_int, retrieval_query

none_reranker = define_stage(
    stage="reranker",
    name="none",
    config_schema={"type": "object", "additionalProperties": False},
    description="跳过精排，直接使用粗召排序。适合对照实验或召回已经很准的场景。",
)


@none_reranker.run
async def run_none(data, params, ctx):
    return data


bge_reranker = define_stage(
    stage="reranker",
    name="bge-reranker",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "top_n": {"type": "integer"},
            "binding_id": {"type": "string"},
        },
    },
    default_params={"top_n": 5},
    description=(
        "LLM 占位精排：用对话模型交叉打分后只留 Top-N。"
        "不是 BAAI/bge-reranker 等真 Cross-Encoder；"
        "专用 rerank 服务（Xinference/TEI 的 /rerank）请自行开发插件接入。"
    ),
)


@bge_reranker.run
async def run_bge(data, params, ctx):
    """Cross-encoder style scores via the generator binding (lab stand-in for BGE)."""
    retrieved = list(data.get("retrieved") or [])
    top_n = param_int(params, "top_n", 5)
    query = retrieval_query(data)
    scored: list[tuple[float, dict]] = []
    for item in retrieved:
        raw = await ctx.chat_complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Score how relevant the passage is to the question. "
                        'Return JSON {"score": <float 0 to 1>} only.'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {query}\nPassage: {item.get('content')}",
                },
            ],
            params.get("binding_id"),
            temperature=0.0,
            max_tokens=64,
        )
        try:
            score = float(parse_json_object(raw).get("score", 0))
        except (ValueError, TypeError):
            score = 0.0
        cloned = dict(item)
        cloned["rerank_score"] = score
        scored.append((score, cloned))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = []
    for rank, (_, item) in enumerate(scored[: max(top_n, 0)], start=1):
        item["rank"] = rank
        ranked.append(item)
    data["retrieved"] = ranked
    return data


RERANKER_PLUGINS = [none_reranker, bge_reranker]
