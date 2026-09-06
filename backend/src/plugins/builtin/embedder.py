from plugins.define import define_stage
from plugins.params import param_int

_EMBEDDER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "binding_id": {"type": "string"},
        "batch_size": {"type": "integer"},
    },
}


def _embedder(name: str, default_batch_size: int, description: str):
    plugin = define_stage(
        stage="embedder",
        name=name,
        config_schema=_EMBEDDER_SCHEMA,
        default_params={"batch_size": default_batch_size},
        description=description,
    )

    @plugin.run
    async def run_embedder(data, params, ctx):
        chunks = data.get("chunks") or []
        targets = [chunk for chunk in chunks if chunk.get("embed") is not False]
        if not targets:
            data["embeddings"] = []
            data["embedder_plugin"] = name
            return data
        batch_size = param_int(params, "batch_size", default_batch_size)
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        binding_id = params.get("binding_id")
        vectors: list[list[float]] = []
        texts = [chunk["content"] for chunk in targets]
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(await ctx.embed_texts(batch, binding_id))
        for chunk, vector in zip(targets, vectors, strict=True):
            chunk["embedding"] = vector
            chunk["dim"] = len(vector)
        data["embeddings"] = vectors
        data["embedder_plugin"] = name
        return data

    return plugin


openai_embedder = _embedder(
    "openai_embedder",
    64,
    "用 OpenAI 兼容 Embedding API 把切块变成向量；入库与查询必须用同一模型。",
)
local_embedder = _embedder(
    "local_embedder",
    32,
    "调用本地 OpenAI 兼容服务（如 vLLM/Ollama）做向量化，密钥走 model binding，不进 params。",
)

EMBEDDER_PLUGINS = [openai_embedder, local_embedder]
