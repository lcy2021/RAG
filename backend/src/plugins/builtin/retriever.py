from engine.retrieval import bm25_scores, reciprocal_rank_fusion, tokenize
from plugins.define import define_stage
from plugins.params import param_float, param_int


def _store_list(data: dict, name: str, retrieved: list[dict]) -> None:
    lists = data.setdefault("retrieved_lists", {})
    lists[name] = retrieved
    data["retrieved"] = retrieved


def _row_to_hit(row: dict, rank: int, retriever: str) -> dict:
    content = row.get("expanded_content") or row.get("content") or ""
    return {
        "chunk_id": row["chunk_id"],
        "content": content,
        "child_content": row.get("content"),
        "score": float(row["score"]) if row.get("score") is not None else None,
        "rank": rank,
        "retriever": retriever,
        "metadata": row.get("metadata") or {},
    }


dense = define_stage(
    stage="retriever",
    name="dense",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "top_k": {"type": "integer"},
            "score_threshold": {"type": "number"},
            "binding_id": {"type": "string"},
        },
    },
    default_params={"top_k": 20},
    description="用查询向量在 pgvector 里做语义近邻检索；同义词、换说法也能命中。",
)


@dense.run
async def run_dense(data, params, ctx):
    queries = data.get("search_queries") or [data.get("rewritten_query") or data.get("query") or ""]
    collection_id = data["vector_collection_id"]
    top_k = param_int(params, "top_k", 20)
    ranked_lists: list[list[dict]] = []
    for query in queries:
        if not query:
            continue
        vectors = await ctx.embed_texts([query], params.get("binding_id"))
        if not vectors:
            continue
        rows = await ctx.kb_repo.dense_search(
            vector_collection_id=collection_id,
            query_embedding=vectors[0],
            top_k=top_k,
            score_threshold=params.get("score_threshold"),
        )
        ranked_lists.append(
            [_row_to_hit(row, rank, "dense") for rank, row in enumerate(rows, start=1)]
        )
    if len(ranked_lists) > 1:
        retrieved = reciprocal_rank_fusion(ranked_lists, k=60)[:top_k]
        for item in retrieved:
            item["retriever"] = "dense"
    elif ranked_lists:
        retrieved = ranked_lists[0]
    else:
        retrieved = []
    _store_list(data, "dense", retrieved)
    return data


bm25 = define_stage(
    stage="retriever",
    name="bm25",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "top_k": {"type": "integer"},
            "k1": {"type": "number"},
            "b": {"type": "number"},
        },
    },
    default_params={"top_k": 20, "k1": 1.2, "b": 0.75},
    description="BM25 关键词检索，擅长型号、缩写、数字等精确匹配；可与 dense 组成多路召回。",
)


@bm25.run
async def run_bm25(data, params, ctx):
    query = data.get("rewritten_query") or data.get("query") or ""
    extra_queries = data.get("search_queries") or [query]
    collection_id = data["vector_collection_id"]
    top_k = param_int(params, "top_k", 20)
    corpus = await ctx.kb_repo.list_collection_chunks(collection_id)
    tokenized_docs = [tokenize(row.get("expanded_content") or row["content"]) for row in corpus]
    ranked_lists: list[list[dict]] = []
    for search_query in extra_queries:
        scores = bm25_scores(
            tokenize(search_query),
            tokenized_docs,
            k1=param_float(params, "k1", 1.2),
            b=param_float(params, "b", 0.75),
        )
        indexed = list(zip(scores, corpus, strict=True))
        indexed.sort(key=lambda pair: pair[0], reverse=True)
        hits = []
        for rank, (score, row) in enumerate(indexed[:top_k], start=1):
            if score <= 0:
                continue
            hit = _row_to_hit({**row, "score": score}, rank, "bm25")
            hits.append(hit)
        ranked_lists.append(hits)
    if len(ranked_lists) > 1:
        retrieved = reciprocal_rank_fusion(ranked_lists, k=60)[:top_k]
        for item in retrieved:
            item["retriever"] = "bm25"
    elif ranked_lists:
        retrieved = ranked_lists[0]
    else:
        retrieved = []
    _store_list(data, "bm25", retrieved)
    return data


RETRIEVER_PLUGINS = [dense, bm25]
