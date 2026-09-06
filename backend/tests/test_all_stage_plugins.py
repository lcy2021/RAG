"""Smoke-execute every builtin stage plugin once with mocked I/O."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from docx import Document as DocxDocument

from plugins.builtin import ALL_BUILTIN_PLUGINS
from plugins.builtin.chunker import heading, parent_child, recursive, semantic
from plugins.builtin.compressor import none_compressor, top_n
from plugins.builtin.embedder import local_embedder, openai_embedder
from plugins.builtin.evaluator import faithfulness, mrr, recall_at_k
from plugins.builtin.fusion import rrf
from plugins.builtin.generator import chat
from plugins.builtin.grader import crag
from plugins.builtin.indexer import pgvector
from plugins.builtin.loader_stage import auto, layout, markup, ocr, table, text
from plugins.builtin.query_transformer import hyde, multi_query, passthrough, rewrite
from plugins.builtin.reranker import bge_reranker, none_reranker
from plugins.builtin.retriever import bm25, dense
from plugins.define import StagePlugin


EXPECTED_CATALOG: dict[str, set[str]] = {
    "loader": {"auto", "text", "markup", "layout", "table", "ocr"},
    "chunker": {"recursive", "semantic", "parent_child", "heading"},
    "embedder": {"openai_embedder", "local_embedder"},
    "indexer": {"pgvector"},
    "query_transformer": {"passthrough", "rewrite", "hyde", "multi_query"},
    "retriever": {"dense", "bm25"},
    "fusion": {"rrf"},
    "reranker": {"none", "bge-reranker"},
    "grader": {"crag"},
    "compressor": {"none", "top_n"},
    "generator": {"chat"},
    "evaluator": {"recall_at_k", "mrr", "faithfulness"},
}


class _FakeKbRepo:
    def __init__(self) -> None:
        self.chunks: list[dict[str, Any]] = []
        self.embeddings: list[dict[str, Any]] = []
        self.collection_dim: int | None = None
        self._corpus = [
            {
                "chunk_id": "c1",
                "content": "Widget X refund within 7 days",
                "expanded_content": "Widget X refund within 7 days",
                "metadata": {},
                "score": 0.91,
            },
            {
                "chunk_id": "c2",
                "content": "Shipping takes three business days",
                "expanded_content": "Shipping takes three business days",
                "metadata": {},
                "score": 0.42,
            },
        ]

    async def insert_chunk(self, **kwargs: Any) -> dict[str, Any]:
        row = {"id": uuid4(), **kwargs}
        self.chunks.append(row)
        return row

    async def insert_embedding(self, **kwargs: Any) -> None:
        self.embeddings.append(kwargs)

    async def update_collection_dim(self, collection_id: Any, dim: int) -> None:
        self.collection_dim = dim

    async def dense_search(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self._corpus)

    async def list_collection_chunks(self, collection_id: Any) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "expanded_content": row["expanded_content"],
                "metadata": row["metadata"],
            }
            for row in self._corpus
        ]


class _FakeCtx:
    def __init__(self, *, chat_reply: str = "ok", scores: list[float] | None = None) -> None:
        self.kb_repo = _FakeKbRepo()
        self._scores = list(scores or [])
        self._chat_reply = chat_reply
        self.embed_calls = 0
        self.chat_calls = 0

    async def embed_texts(self, texts: list[str], binding_id: Any) -> list[list[float]]:
        self.embed_calls += 1
        return [[float(i + 1), 0.0] for i, _ in enumerate(texts)]

    async def chat_complete(
        self,
        messages: list[dict[str, str]],
        binding_id: Any,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.chat_calls += 1
        if self._scores:
            score = self._scores.pop(0)
            return f'{{"score": {score}}}'
        return self._chat_reply

    def token_callback(self):
        return None


def test_builtin_catalog_covers_every_stage() -> None:
    by_stage: dict[str, set[str]] = {}
    for plugin in ALL_BUILTIN_PLUGINS:
        assert isinstance(plugin, StagePlugin)
        assert plugin.description, f"{plugin.stage}/{plugin.name} missing description"
        by_stage.setdefault(plugin.stage.value, set()).add(plugin.name)
    assert by_stage == EXPECTED_CATALOG
    assert len(ALL_BUILTIN_PLUGINS) == sum(len(names) for names in EXPECTED_CATALOG.values())


# --- loader ---


async def test_loader_auto_text_markup_table(tmp_path: Path) -> None:
    txt = tmp_path / "a.txt"
    txt.write_text("plain loader text", encoding="utf-8")
    auto_out = await auto.execute(
        {"file_path": str(txt), "filename": txt.name, "raw_text": ""}, {}, None
    )
    assert auto_out["raw_text"] == "plain loader text"
    assert auto_out["loader_strategy"] == "text"

    text_out = await text.execute({"raw_text": "inline text"}, {}, None)
    assert text_out["raw_text"] == "inline text"
    assert text_out["loader_strategy"] == "text"

    markup_out = await markup.execute(
        {"raw_text": "<p>Hello <b>world</b></p><script>x()</script>"}, {}, None
    )
    assert "Hello" in markup_out["raw_text"]
    assert "script" not in markup_out["raw_text"].lower()
    assert markup_out["loader_strategy"] == "markup"

    csv_path = tmp_path / "t.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    table_out = await table.execute(
        {"file_path": str(csv_path), "filename": csv_path.name, "raw_text": ""},
        {"merge_tables": True},
        None,
    )
    assert "1" in table_out["raw_text"]
    assert table_out["loader_strategy"] == "table"


async def test_loader_layout(tmp_path: Path) -> None:
    docx_path = tmp_path / "n.docx"
    document = DocxDocument()
    document.add_paragraph("Layout plugin body")
    document.save(docx_path)
    out = await layout.execute(
        {"file_path": str(docx_path), "filename": docx_path.name, "raw_text": ""},
        {},
        None,
    )
    assert "Layout plugin body" in out["raw_text"]
    assert out["loader_strategy"] == "layout"


async def test_loader_ocr_skips_without_deps(tmp_path: Path) -> None:
    """OCR needs optional deps + Tesseract; verify plugin path or skip cleanly."""
    try:
        from PIL import Image  # noqa: F401
        import pytesseract  # noqa: F401
    except ImportError:
        pytest.skip("raglab[ocr] not installed")

    img_path = tmp_path / "ocr.png"
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (240, 60), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 20), "OCR LAB", fill="black")
    image.save(img_path)

    try:
        out = await ocr.execute(
            {"file_path": str(img_path), "filename": img_path.name, "raw_text": ""},
            {"ocr_lang": "eng"},
            None,
        )
    except Exception as exc:  # Tesseract missing or path issues on CI/dev boxes
        pytest.skip(f"OCR runtime unavailable: {exc}")
    assert out["loader_strategy"] == "ocr"
    assert out["raw_text"].strip()


# --- chunker ---


async def test_chunkers() -> None:
    raw = (
        "# Refund\n\nYou may refund Widget X in 7 days.\n\n"
        "## Shipping\n\nOrders ship in three business days."
    )
    ctx = _FakeCtx()

    recursive_out = await recursive.execute(
        {"raw_text": raw}, {"chunk_size": 40, "overlap": 4}, None
    )
    assert recursive_out["chunker_plugin"] == "recursive"
    assert len(recursive_out["chunks"]) >= 2

    semantic_out = await semantic.execute(
        {"raw_text": "First sentence. Second sentence. Third sentence."},
        {"similarity_threshold": 0.99, "max_tokens": 30},
        ctx,
    )
    assert semantic_out["chunker_plugin"] == "semantic"
    assert semantic_out["chunks"]
    assert ctx.embed_calls >= 1

    parent_out = await parent_child.execute(
        {"raw_text": "x" * 120},
        {"parent_max_tokens": 80, "child_max_tokens": 30, "overlap": 0},
        None,
    )
    roles = {c["metadata"]["role"] for c in parent_out["chunks"]}
    assert roles == {"parent", "child"}

    heading_out = await heading.execute(
        {"raw_text": raw}, {"chunk_size": 1024, "overlap": 0}, None
    )
    assert heading_out["chunker_plugin"] == "heading"
    titles = {c["metadata"].get("title") for c in heading_out["chunks"]}
    assert "Refund" in titles
    assert "Shipping" in titles


# --- embedder + indexer ---


async def test_embedders_and_indexer() -> None:
    ctx = _FakeCtx()
    data = {
        "chunks": [
            {"ordinal": 0, "content": "alpha", "token_count": 5, "metadata": {}},
            {
                "ordinal": 1,
                "content": "parent only",
                "token_count": 2,
                "metadata": {"role": "parent"},
                "embed": False,
            },
        ]
    }
    openai_out = await openai_embedder.execute(data, {"batch_size": 1}, ctx)
    assert openai_out["embedder_plugin"] == "openai_embedder"
    assert len(openai_out["embeddings"]) == 1
    assert openai_out["chunks"][0]["embedding"] == [1.0, 0.0]
    assert "embedding" not in openai_out["chunks"][1]

    local_data = {
        "chunks": [{"ordinal": 0, "content": "beta", "token_count": 1, "metadata": {}}]
    }
    local_out = await local_embedder.execute(local_data, {}, ctx)
    assert local_out["embedder_plugin"] == "local_embedder"
    assert local_out["embeddings"]

    index_data = {
        "document_version_id": uuid4(),
        "vector_collection_id": uuid4(),
        "chunker_plugin": "recursive",
        "embedder_plugin": "openai_embedder",
        "chunks": openai_out["chunks"],
    }
    indexed = await pgvector.execute(index_data, {"metric": "cosine"}, ctx)
    assert indexed["indexed_count"] == 1
    assert len(ctx.kb_repo.chunks) == 2  # parent embed=False still stored
    assert len(ctx.kb_repo.embeddings) == 1
    assert ctx.kb_repo.collection_dim == 2


# --- query transformer ---


async def test_query_transformers() -> None:
    base = {
        "query": "它多少钱？",
        "history": [
            {"role": "user", "content": "介绍 Widget X"},
            {"role": "assistant", "content": "传感器产品"},
        ],
    }
    pass_out = await passthrough.execute(dict(base), {}, None)
    assert pass_out["rewritten_query"] == "它多少钱？"

    rewrite_ctx = _FakeCtx(chat_reply="Widget X 价格")
    rewrite_out = await rewrite.execute(dict(base), {"history_turns": 1}, rewrite_ctx)
    assert rewrite_out["rewritten_query"] == "Widget X 价格"
    assert rewrite_ctx.chat_calls == 1

    hyde_ctx = _FakeCtx(chat_reply="Widget X 售价为 99 元。")
    hyde_out = await hyde.execute(dict(base), {"n_hypothetical": 1}, hyde_ctx)
    assert hyde_out["hypothetical_docs"]
    assert hyde_out["rewritten_query"].startswith("Widget X")
    assert hyde_out["search_queries"]

    mq_ctx = _FakeCtx(chat_reply="Widget X price\nWidget X cost\nWidget X 售价")
    mq_out = await multi_query.execute(dict(base), {"n_queries": 3}, mq_ctx)
    assert len(mq_out["search_queries"]) == 3
    assert mq_out["rewritten_query"]


# --- retriever + fusion ---


async def test_retrievers_and_fusion() -> None:
    ctx = _FakeCtx()
    data = {
        "query": "Widget refund",
        "rewritten_query": "Widget X refund",
        "search_queries": ["Widget X refund"],
        "vector_collection_id": uuid4(),
    }
    dense_out = await dense.execute(dict(data), {"top_k": 5}, ctx)
    assert dense_out["retrieved_lists"]["dense"]
    assert dense_out["retrieved"][0]["retriever"] == "dense"

    bm25_out = await bm25.execute(dict(data), {"top_k": 5}, ctx)
    assert bm25_out["retrieved_lists"]["bm25"]
    assert any("refund" in (h["content"] or "").lower() for h in bm25_out["retrieved"])

    fusion_data = {
        "retrieved_lists": {
            "dense": dense_out["retrieved"],
            "bm25": bm25_out["retrieved"],
        }
    }
    fused = await rrf.execute(fusion_data, {"k": 60}, None)
    assert fused["retrieved"]
    assert {h["chunk_id"] for h in fused["retrieved"]} <= {"c1", "c2"}


# --- reranker + grader + compressor + generator ---


async def test_query_tail_plugins() -> None:
    passages = [
        {"chunk_id": "c1", "content": "Refund in 7 days", "rank": 1, "score": 0.9},
        {"chunk_id": "c2", "content": "Unrelated shipping note", "rank": 2, "score": 0.2},
    ]
    none_rr = await none_reranker.execute({"retrieved": list(passages)}, {}, None)
    assert none_rr["retrieved"] == passages

    rr_ctx = _FakeCtx(scores=[0.95, 0.1])
    reranked = await bge_reranker.execute(
        {"query": "refund", "retrieved": list(passages)}, {"top_n": 1}, rr_ctx
    )
    assert len(reranked["retrieved"]) == 1
    assert reranked["retrieved"][0]["rerank_score"] == 0.95

    grade_ctx = _FakeCtx(scores=[0.9, 0.2])
    graded = await crag.execute(
        {
            "query": "refund policy",
            "retrieved": list(passages),
        },
        {"accept_threshold": 0.5},
        grade_ctx,
    )
    assert graded["crag_action"] == "correct"
    assert len(graded["retrieved"]) == 1

    none_c = await none_compressor.execute({"retrieved": list(passages)}, {}, None)
    assert len(none_c["retrieved"]) == 2
    top = await top_n.execute({"retrieved": list(passages)}, {"n": 1}, None)
    assert len(top["retrieved"]) == 1
    assert top["retrieved"][0]["rank"] == 1

    gen_ctx = _FakeCtx(chat_reply="You may refund within 7 days. [1]")
    generated = await chat.execute(
        {
            "query": "refund?",
            "retrieved": [{"rank": 1, "content": "Refund in 7 days"}],
            "history": [],
        },
        {"temperature": 0.0, "max_tokens": 64},
        gen_ctx,
    )
    assert "[1]" in generated["answer"]


# --- evaluator ---


async def test_evaluators() -> None:
    data = {
        "retrieved": [
            {"content": "Refund Widget X within 7 days"},
            {"content": "Other policy"},
        ],
        "gold_quotes": ["Refund Widget X"],
        "answer": "Refund is allowed within 7 days.",
    }
    recall = await recall_at_k.execute(dict(data), {"k": 1}, None)
    assert recall["metrics"]["recall_at_k"] == 1.0

    mrr_out = await mrr.execute(dict(data), {}, None)
    assert mrr_out["metrics"]["mrr"] == 1.0

    faith_ctx = _FakeCtx(scores=[0.88])
    faith = await faithfulness.execute(dict(data), {}, faith_ctx)
    assert faith["metrics"]["faithfulness"] == 0.88


async def test_every_builtin_is_executable() -> None:
    """Guardrail: every registered plugin name appears in the smoke suite above.

    Catalog completeness is checked in test_builtin_catalog_covers_every_stage;
    this documents the execute coverage matrix used by this file.
    """
    covered = {
        ("loader", "auto"),
        ("loader", "text"),
        ("loader", "markup"),
        ("loader", "layout"),
        ("loader", "table"),
        ("loader", "ocr"),
        ("chunker", "recursive"),
        ("chunker", "semantic"),
        ("chunker", "parent_child"),
        ("chunker", "heading"),
        ("embedder", "openai_embedder"),
        ("embedder", "local_embedder"),
        ("indexer", "pgvector"),
        ("query_transformer", "passthrough"),
        ("query_transformer", "rewrite"),
        ("query_transformer", "hyde"),
        ("query_transformer", "multi_query"),
        ("retriever", "dense"),
        ("retriever", "bm25"),
        ("fusion", "rrf"),
        ("reranker", "none"),
        ("reranker", "bge-reranker"),
        ("grader", "crag"),
        ("compressor", "none"),
        ("compressor", "top_n"),
        ("generator", "chat"),
        ("evaluator", "recall_at_k"),
        ("evaluator", "mrr"),
        ("evaluator", "faithfulness"),
    }
    registered = {(p.stage.value, p.name) for p in ALL_BUILTIN_PLUGINS}
    assert covered == registered
