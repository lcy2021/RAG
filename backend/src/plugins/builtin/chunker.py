from engine.headings import split_by_heading
from engine.retrieval import cosine_similarity, split_sentences
from engine.textsplit import DEFAULT_SEPARATORS, split_recursive
from plugins.define import define_stage
from plugins.params import param_float, param_int, text_unit_count

_RECURSIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "chunk_size": {"type": "integer"},
        "overlap": {"type": "integer"},
        "separators": {"type": "array", "items": {"type": "string"}},
    },
}

recursive = define_stage(
    stage="chunker",
    name="recursive",
    config_schema=_RECURSIVE_SCHEMA,
    default_params={
        "chunk_size": 512,
        "overlap": 64,
        "separators": list(DEFAULT_SEPARATORS),
    },
    description="按固定长度切块并保留 overlap，减少句子被拦腰截断后检索丢上下文。",
)


@recursive.run
async def run_recursive(data, params, ctx):
    text = data.get("raw_text") or ""
    pieces = split_recursive(
        text,
        chunk_size=param_int(params, "chunk_size", 512),
        overlap=param_int(params, "overlap", 64),
        separators=params.get("separators"),
    )
    data["chunks"] = _as_chunks(pieces, "recursive")
    data["chunker_plugin"] = "recursive"
    return data


semantic = define_stage(
    stage="chunker",
    name="semantic",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "similarity_threshold": {"type": "number"},
            "max_tokens": {
                "type": "integer",
                "description": "Max characters per chunk (same units as recursive chunk_size).",
            },
            "binding_id": {"type": "string"},
        },
    },
    default_params={"similarity_threshold": 0.8, "max_tokens": 512},
    description="按相邻句向量相似度合并，在话题转换处切开，避免把无关段落压进同一向量。",
)


@semantic.run
async def run_semantic(data, params, ctx):
    """Merge adjacent sentences while cosine similarity stays above the threshold."""
    sentences = split_sentences(data.get("raw_text") or "")
    if not sentences:
        data["chunks"] = []
        data["chunker_plugin"] = "semantic"
        return data
    max_chars = param_int(params, "max_tokens", 512)
    threshold = param_float(params, "similarity_threshold", 0.8)
    vectors = await ctx.embed_texts(sentences, params.get("binding_id"))
    groups: list[str] = []
    current = sentences[0]
    for index in range(1, len(sentences)):
        similar = cosine_similarity(vectors[index - 1], vectors[index]) >= threshold
        candidate = f"{current} {sentences[index]}".strip()
        if similar and len(candidate) <= max_chars:
            current = candidate
            continue
        groups.append(current)
        current = sentences[index]
    groups.append(current)
    data["chunks"] = _as_chunks(groups, "semantic")
    data["chunker_plugin"] = "semantic"
    return data


parent_child = define_stage(
    stage="chunker",
    name="parent_child",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "parent_max_tokens": {
                "type": "integer",
                "description": "Parent chunk size in characters.",
            },
            "child_max_tokens": {
                "type": "integer",
                "description": "Child chunk size in characters.",
            },
            "overlap": {"type": "integer"},
        },
    },
    default_params={"parent_max_tokens": 1024, "child_max_tokens": 256, "overlap": 32},
    description="子块用于精确检索，命中后再取出父块给生成模型，兼顾精度与上下文完整。",
)


@parent_child.run
async def run_parent_child(data, params, ctx):
    """Small children for retrieval, large parents returned to the generator."""
    parent_size = param_int(params, "parent_max_tokens", 1024)
    child_size = param_int(params, "child_max_tokens", 256)
    overlap = param_int(params, "overlap", 32)
    parents = split_recursive(data.get("raw_text") or "", chunk_size=parent_size, overlap=0)
    chunks: list[dict] = []
    ordinal = 0
    for parent_ordinal, parent in enumerate(parents):
        chunks.append(
            {
                "ordinal": ordinal,
                "content": parent,
                "token_count": text_unit_count(parent),
                "metadata": {"role": "parent", "parent_ordinal": parent_ordinal},
                "embed": False,
            }
        )
        parent_index = ordinal
        ordinal += 1
        child_overlap = min(overlap, max(child_size - 1, 0))
        children = split_recursive(parent, chunk_size=child_size, overlap=child_overlap)
        for child in children:
            chunks.append(
                {
                    "ordinal": ordinal,
                    "content": child,
                    "token_count": text_unit_count(child),
                    "metadata": {
                        "role": "child",
                        "parent_ordinal": parent_ordinal,
                        "parent_index": parent_index,
                    },
                }
            )
            ordinal += 1
    data["chunks"] = chunks
    data["chunker_plugin"] = "parent_child"
    return data


heading = define_stage(
    stage="chunker",
    name="heading",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "chunk_size": {"type": "integer"},
            "overlap": {"type": "integer"},
        },
    },
    default_params={"chunk_size": 1024, "overlap": 0},
    description="按 Markdown 标题切章节，适合手册、文档站等有层级结构的语料。",
)


@heading.run
async def run_heading(data, params, ctx):
    """Split on Markdown headings, then recursive-split oversized sections."""
    limit = param_int(params, "chunk_size", 1024)
    overlap = param_int(params, "overlap", 0)
    pieces: list[str] = []
    metas: list[dict] = []
    for section in split_by_heading(data.get("raw_text") or ""):
        content = section["content"]
        if len(content) <= limit:
            pieces.append(content)
            metas.append({"title": section["title"]})
            continue
        split_overlap = overlap if overlap < limit else 0
        for part in split_recursive(content, chunk_size=limit, overlap=split_overlap):
            pieces.append(part)
            metas.append({"title": section["title"]})
    data["chunks"] = [
        {
            "ordinal": index,
            "content": piece,
            "token_count": text_unit_count(piece),
            "metadata": metas[index],
        }
        for index, piece in enumerate(pieces)
    ]
    data["chunker_plugin"] = "heading"
    return data


def _as_chunks(pieces: list[str], plugin: str) -> list[dict]:
    return [
        {
            "ordinal": index,
            "content": piece,
            "token_count": text_unit_count(piece),
            "metadata": {"chunker": plugin},
        }
        for index, piece in enumerate(pieces)
    ]


CHUNKER_PLUGINS = [recursive, semantic, parent_child, heading]
