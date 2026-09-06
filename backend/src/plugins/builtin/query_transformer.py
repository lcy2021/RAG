from engine.retrieval import parse_lines
from plugins.define import define_stage

passthrough = define_stage(
    stage="query_transformer",
    name="passthrough",
    config_schema={"type": "object", "additionalProperties": False},
    description="不改写用户问题，原句直接用于检索。适合问题已经规范、作为对照基线。",
)


@passthrough.run
async def run_passthrough(data, params, ctx):
    data["rewritten_query"] = data.get("query", "")
    return data


rewrite = define_stage(
    stage="query_transformer",
    name="rewrite",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "binding_id": {"type": "string"},
            "temperature": {"type": "number"},
        },
    },
    default_params={"temperature": 0.0},
    description="把口语、指代不清的提问改写成独立检索句，保留实体、型号和数字。",
)


@rewrite.run
async def run_rewrite(data, params, ctx):
    """Standalone search query: drop chat filler, keep entities and intent."""
    query = data.get("query") or ""
    text = await ctx.chat_complete(
        [
            {
                "role": "system",
                "content": (
                    "Rewrite the user question as a concise standalone search query. "
                    "Keep entities, numbers, and product names. Output only the query."
                ),
            },
            {"role": "user", "content": query},
        ],
        params.get("binding_id"),
        temperature=float(params.get("temperature") or 0.0),
        max_tokens=128,
    )
    data["rewritten_query"] = text.strip() or query
    return data


hyde = define_stage(
    stage="query_transformer",
    name="hyde",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "n_hypothetical": {"type": "integer"},
            "temperature": {"type": "number"},
            "binding_id": {"type": "string"},
        },
    },
    default_params={"n_hypothetical": 1, "temperature": 0.3},
    description="先让模型写一段假设答案再去检索，缩小「问句」和「文档陈述」之间的向量鸿沟。",
)


@hyde.run
async def run_hyde(data, params, ctx):
    """Embed a hypothetical answer so retrieval matches document style, not the question."""
    query = data.get("query") or ""
    n_docs = max(1, int(params.get("n_hypothetical") or 1))
    hypos: list[str] = []
    for _ in range(n_docs):
        hypo = await ctx.chat_complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Write a short hypothetical answer passage for the question. "
                        "Do not say you lack context. Output only the passage."
                    ),
                },
                {"role": "user", "content": query},
            ],
            params.get("binding_id"),
            temperature=float(params.get("temperature") or 0.3),
            max_tokens=256,
        )
        if hypo.strip():
            hypos.append(hypo.strip())
    data["hypothetical_docs"] = hypos
    data["rewritten_query"] = hypos[0] if hypos else query
    data["search_queries"] = hypos or [query]
    return data


multi_query = define_stage(
    stage="query_transformer",
    name="multi_query",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "n_queries": {"type": "integer"},
            "binding_id": {"type": "string"},
        },
    },
    default_params={"n_queries": 3},
    description="把一个问题扩成多个不同角度的检索句，分别召回后再合并，降低漏召。",
)


@multi_query.run
async def run_multi_query(data, params, ctx):
    """Several paraphrases so one wording mismatch does not miss the corpus."""
    query = data.get("query") or ""
    n_queries = max(1, int(params.get("n_queries") or 3))
    text = await ctx.chat_complete(
        [
            {
                "role": "system",
                "content": (
                    f"Generate {n_queries} diverse search queries for the user question. "
                    "One query per line. No numbering or commentary."
                ),
            },
            {"role": "user", "content": query},
        ],
        params.get("binding_id"),
        temperature=0.4,
        max_tokens=256,
    )
    queries = parse_lines(text, n_queries)
    if query not in queries:
        queries = [query, *queries][:n_queries]
    data["search_queries"] = queries or [query]
    data["rewritten_query"] = queries[0] if queries else query
    return data


QUERY_TRANSFORMER_PLUGINS = [passthrough, rewrite, hyde, multi_query]
