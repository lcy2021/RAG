from plugins.define import define_stage

pgvector = define_stage(
    stage="indexer",
    name="pgvector",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"metric": {"type": "string", "enum": ["cosine", "l2", "ip"]}},
    },
    default_params={"metric": "cosine"},
    description="把切块向量写入 PostgreSQL pgvector，并按 collection 做 ANN 检索。",
)


@pgvector.run
async def run_pgvector(data, params, ctx):
    version_id = data["document_version_id"]
    collection_id = data["vector_collection_id"]
    chunker = data.get("chunker_plugin") or "recursive"
    embedder = data.get("embedder_plugin") or "openai_embedder"
    stored = 0
    ids_by_ordinal: dict[int, object] = {}
    for chunk in data.get("chunks") or []:
        metadata = chunk.get("metadata") or {}
        parent_index = metadata.get("parent_index")
        parent_id = ids_by_ordinal.get(parent_index) if parent_index is not None else None
        row = await ctx.kb_repo.insert_chunk(
            document_version_id=version_id,
            chunker_plugin=chunker,
            ordinal=int(chunk["ordinal"]),
            content=chunk["content"],
            token_count=chunk.get("token_count"),
            metadata=metadata,
            parent_chunk_id=parent_id,
        )
        ids_by_ordinal[int(chunk["ordinal"])] = row["id"]
        if chunk.get("embed") is False:
            continue
        embedding = chunk.get("embedding")
        if embedding is None:
            raise ValueError("indexer requires embeddings on retrievable chunks")
        dim = int(chunk.get("dim") or len(embedding))
        await ctx.kb_repo.insert_embedding(
            chunk_id=row["id"],
            vector_collection_id=collection_id,
            embedder_plugin=embedder,
            embedding=embedding,
            dim=dim,
        )
        await ctx.kb_repo.update_collection_dim(collection_id, dim)
        stored += 1
    data["indexed_count"] = stored
    return data


INDEXER_PLUGINS = [pgvector]
