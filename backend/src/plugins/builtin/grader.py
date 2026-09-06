from engine.retrieval import parse_json_object
from plugins.define import define_stage
from plugins.params import param_float, retrieval_query

crag = define_stage(
    stage="grader",
    name="crag",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "accept_threshold": {"type": "number"},
            "binding_id": {"type": "string"},
        },
    },
    default_params={"accept_threshold": 0.5},
    description="Corrective RAG：判断检索是否够用；整体过低则丢掉段落，避免用错知识生成。",
)


@crag.run
async def run_crag(data, params, ctx):
    """Corrective RAG: keep passages only when the grader is confident they help."""
    retrieved = list(data.get("retrieved") or [])
    threshold = param_float(params, "accept_threshold", 0.5)
    query = retrieval_query(data)
    kept: list[dict] = []
    grades: list[float] = []
    for item in retrieved:
        raw = await ctx.chat_complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Judge if the passage can answer the question. "
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
        grades.append(score)
        if score >= threshold:
            cloned = dict(item)
            cloned["grade"] = score
            kept.append(cloned)
    max_grade = max(grades) if grades else 0.0
    if max_grade < threshold:
        data["retrieved"] = []
        data["crag_action"] = "reject"
    else:
        for rank, item in enumerate(kept, start=1):
            item["rank"] = rank
        data["retrieved"] = kept
        data["crag_action"] = "correct"
    data["crag_max_score"] = max_grade
    return data


GRADER_PLUGINS = [crag]
