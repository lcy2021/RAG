from engine.retrieval import parse_json_object
from plugins.define import define_stage
from plugins.params import param_int


def _quotes(data: dict) -> list[str]:
    spans = data.get("gold_quotes") or []
    quotes = []
    for span in spans:
        if isinstance(span, str) and span.strip():
            quotes.append(span.strip())
        elif isinstance(span, dict) and span.get("quote"):
            quotes.append(str(span["quote"]).strip())
    return quotes


def _retrieved_text(data: dict, k: int | None = None) -> str:
    items = list(data.get("retrieved") or [])
    if k is not None:
        items = items[:k]
    return "\n".join(str(item.get("content") or "") for item in items)


recall_at_k = define_stage(
    stage="evaluator",
    name="recall_at_k",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"k": {"type": "integer"}},
    },
    default_params={"k": 10},
    description="评测检索：原文依据（gold span）是否出现在 Top-K 段落中，不依赖切块 ID。",
)


@recall_at_k.run
async def run_recall(data, params, ctx):
    """Span-level recall: gold quote appears in any of the top-k passages."""
    k = param_int(params, "k", 10)
    quotes = _quotes(data)
    blob = _retrieved_text(data, k)
    if not quotes:
        data.setdefault("metrics", {})["recall_at_k"] = None
        return data
    hits = sum(1 for quote in quotes if quote and quote in blob)
    data.setdefault("metrics", {})["recall_at_k"] = hits / len(quotes)
    return data


mrr = define_stage(
    stage="evaluator",
    name="mrr",
    config_schema={"type": "object", "additionalProperties": False},
    description="评测检索：第一条命中金标的排名倒数，衡量相关段落排得有多靠前。",
)


@mrr.run
async def run_mrr(data, params, ctx):
    quotes = _quotes(data)
    retrieved = list(data.get("retrieved") or [])
    if not quotes:
        data.setdefault("metrics", {})["mrr"] = None
        return data
    rank = None
    for index, item in enumerate(retrieved, start=1):
        content = item.get("content") or ""
        if any(quote in content for quote in quotes if quote):
            rank = index
            break
    data.setdefault("metrics", {})["mrr"] = (1.0 / rank) if rank else 0.0
    return data


faithfulness = define_stage(
    stage="evaluator",
    name="faithfulness",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"binding_id": {"type": "string"}},
    },
    description="评测生成：答案是否能被检索段落支撑，用于量化幻觉。",
)


@faithfulness.run
async def run_faithfulness(data, params, ctx):
    answer = data.get("answer") or ""
    passages = _retrieved_text(data)
    raw = await ctx.chat_complete(
        [
            {
                "role": "system",
                "content": (
                    "Score whether the answer is grounded in the passages. "
                    'Return JSON {"score": <float 0 to 1>} only.'
                ),
            },
            {"role": "user", "content": f"Passages:\n{passages}\n\nAnswer:\n{answer}"},
        ],
        params.get("binding_id"),
        temperature=0.0,
        max_tokens=64,
    )
    try:
        score = float(parse_json_object(raw).get("score", 0))
    except (ValueError, TypeError):
        score = 0.0
    data.setdefault("metrics", {})["faithfulness"] = score
    return data


EVALUATOR_PLUGINS = [recall_at_k, mrr, faithfulness]
