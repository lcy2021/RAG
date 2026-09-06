# Plugin params / 插件参数

> **中文** ↓ · **[English](#english)** · [架构](../design.md)

页面上的参数表单由 `plugins.config_schema` 生成；密钥不是 params，只用 `binding_id`。每个插件带 `description`（用途），插件中心与流水线下拉框应展示该字段。

合并：`default_params` ← 流水线 `bindings[].params` ← 变体 `slot_overrides.params`，校验后写入 `rag_runs.resolved_params`。同一插件不同 params 也是合法对比轴。

Catalog follows the techniques in [小林 RAG 面试题](https://www.xiaolinnote.com/ai/rag/rag_info.html): chunking, query rewrite, hybrid recall, RRF, rerank, CRAG, span metrics.

| Stage | Plugin | Params |
|---|---|---|
| chunker | `recursive` | `chunk_size`, `overlap`, `separators` (default `["\\n\\n","\\n",". "," ",""]`; omit → same) |
| chunker | `semantic` | `similarity_threshold`, `max_tokens`, `binding_id` |
| chunker | `parent_child` | `parent_max_tokens`, `child_max_tokens`, `overlap` |
| chunker | `heading` | `chunk_size`, `overlap` |
| embedder | `openai_embedder` / `local_embedder` | `binding_id`, `batch_size` |
| indexer | `pgvector` | `metric` (cosine\|l2\|ip) |
| query_transformer | `passthrough` | — |
| query_transformer | `rewrite` | `binding_id`, `temperature` |
| query_transformer | `hyde` | `n_hypothetical`, `temperature`, `binding_id` |
| query_transformer | `multi_query` | `n_queries`, `binding_id` |
| retriever | `dense` | `top_k`, `score_threshold`, `binding_id` |
| retriever | `bm25` | `top_k`, `k1`, `b` |
| fusion | `rrf` | `k` |
| reranker | `none` | — |
| reranker | `bge-reranker` | `top_n`, `binding_id` (LLM stand-in via chat; **not** a real BGE Cross-Encoder) |
| grader | `crag` | `accept_threshold`, `binding_id` |
| compressor | `none` / `top_n` | `n` |
| generator | `chat` | `binding_id`, `temperature`, `max_tokens` |
| evaluator | `recall_at_k` / `mrr` / `faithfulness` | `k` / — / `binding_id` |

Multi-recall: set retriever slot `mode=ensemble` with `dense` + `bm25`, then `fusion=rrf`. GraphRAG is out of scope (see design.md).

**Rerank models:** Credentials are only `vector` | `llm`. Builtin `bge-reranker` scores passages with a chat LLM. For `BAAI/bge-reranker-v2-m3` (Xinference/TEI `/rerank`), write a custom `reranker` stage plugin — see [custom-plugins.md](custom-plugins.md).
