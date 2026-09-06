"""Regression tests for builtin plugin param / length / query fixes."""

from __future__ import annotations

from typing import Any

from plugins.builtin.chunker import parent_child, semantic
from plugins.builtin.compressor import top_n
from plugins.builtin.grader import crag
from plugins.builtin.generator import chat
from plugins.builtin.query_transformer import rewrite
from plugins.params import param_float, param_int, retrieval_query


def test_param_helpers_keep_zero() -> None:
    assert param_int({"overlap": 0}, "overlap", 32) == 0
    assert param_float({"temperature": 0.0}, "temperature", 0.2) == 0.0
    assert param_float({"accept_threshold": 0}, "accept_threshold", 0.5) == 0.0
    assert param_int({}, "overlap", 32) == 32
    assert param_float({"temperature": None}, "temperature", 0.2) == 0.2


def test_retrieval_query_prefers_rewritten() -> None:
    assert retrieval_query({"query": "raw", "rewritten_query": "fixed"}) == "fixed"
    assert retrieval_query({"query": "raw"}) == "raw"


class _FakeCtx:
    def __init__(self, scores: list[float] | None = None, vectors: list[list[float]] | None = None):
        self._scores = list(scores or [])
        self._vectors = vectors or []
        self.chat_calls: list[str] = []
        self.chat_message_lists: list[list[dict[str, str]]] = []
        self.last_temperature: float | None = None

    async def embed_texts(self, texts: list[str], binding_id: Any) -> list[list[float]]:
        if self._vectors:
            return self._vectors
        # Identical adjacent vectors → always "similar" for size-limit tests.
        return [[1.0, 0.0] for _ in texts]

    async def chat_complete(
        self,
        messages: list[dict[str, str]],
        binding_id: Any,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.last_temperature = temperature
        self.chat_message_lists.append(messages)
        self.chat_calls.append(messages[-1]["content"])
        if self._scores:
            score = self._scores.pop(0)
            return f'{{"score": {score}}}'
        return "ok"

    def token_callback(self):
        return None


async def test_rewrite_includes_chat_history() -> None:
    ctx = _FakeCtx()
    await rewrite.execute(
        {
            "query": "它多少钱？",
            "history": [
                {"role": "user", "content": "介绍一下 Widget X"},
                {"role": "assistant", "content": "Widget X 是一款传感器。"},
            ],
        },
        {"temperature": 0.0, "history_turns": 3},
        ctx,
    )
    messages = ctx.chat_message_lists[0]
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "介绍一下 Widget X"}
    assert messages[2] == {"role": "assistant", "content": "Widget X 是一款传感器。"}
    assert messages[3] == {"role": "user", "content": "它多少钱？"}
    assert ctx.chat_calls[0] == "它多少钱？"


async def test_rewrite_history_turns_limits_prior_rounds() -> None:
    ctx = _FakeCtx()
    history = [
        {"role": "user", "content": "turn1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "turn2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "turn3"},
        {"role": "assistant", "content": "a3"},
    ]
    await rewrite.execute(
        {"query": "follow-up", "history": history},
        {"history_turns": 1},
        ctx,
    )
    assert [m["content"] for m in ctx.chat_message_lists[0][1:]] == ["turn3", "a3", "follow-up"]

    ctx2 = _FakeCtx()
    await rewrite.execute(
        {"query": "follow-up", "history": history},
        {"history_turns": 0},
        ctx2,
    )
    assert [m["role"] for m in ctx2.chat_message_lists[0]] == ["system", "user"]
    assert ctx2.chat_message_lists[0][1]["content"] == "follow-up"


async def test_generator_keeps_temperature_zero() -> None:
    ctx = _FakeCtx()
    await chat.execute(
        {"query": "q", "retrieved": [], "history": []},
        {"temperature": 0.0, "max_tokens": 64},
        ctx,
    )
    assert ctx.last_temperature == 0.0


async def test_grader_accept_threshold_zero_keeps_all() -> None:
    ctx = _FakeCtx(scores=[0.0, 0.0])
    data = {
        "query": "raw question",
        "rewritten_query": "rewritten question",
        "retrieved": [
            {"content": "a", "rank": 1},
            {"content": "b", "rank": 2},
        ],
    }
    result = await crag.execute(data, {"accept_threshold": 0.0}, ctx)
    assert result["crag_action"] == "correct"
    assert len(result["retrieved"]) == 2
    assert "rewritten question" in ctx.chat_calls[0]
    assert "raw question" not in ctx.chat_calls[0]


async def test_compressor_n_zero_clears_passages() -> None:
    data = {"retrieved": [{"content": "a", "rank": 1}, {"content": "b", "rank": 2}]}
    result = await top_n.execute(data, {"n": 0}, None)
    assert result["retrieved"] == []


async def test_parent_child_overlap_zero() -> None:
    text = "x" * 100
    result = await parent_child.execute(
        {"raw_text": text},
        {"parent_max_tokens": 100, "child_max_tokens": 40, "overlap": 0},
        None,
    )
    children = [c for c in result["chunks"] if c["metadata"]["role"] == "child"]
    assert [len(c["content"]) for c in children] == [40, 40, 20]
    assert sum(len(c["content"]) for c in children) == 100


async def test_semantic_respects_char_limit_for_chinese() -> None:
    # Identical embeddings force merges; char limit must split Chinese text.
    text = "这是第一句话。这是第二句话内容稍长一些。这是第三句。"
    ctx = _FakeCtx()
    result = await semantic.execute(
        {"raw_text": text},
        {"similarity_threshold": 0.0, "max_tokens": 20},
        ctx,
    )
    chunks = result["chunks"]
    assert len(chunks) >= 2
    assert all(len(c["content"]) <= 20 for c in chunks)
    assert all(c["token_count"] == len(c["content"]) for c in chunks)
