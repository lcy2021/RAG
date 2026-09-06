"""Execute pipeline slots in documented stage order."""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from engine.param_merge import merge_params
from models.enums import PipelineKind, PipelineStage
from plugins.context import PluginContext, SpanRecord
from plugins.registry import PluginRegistry

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]

INGEST_ORDER = [
    PipelineStage.LOADER,
    PipelineStage.CHUNKER,
    PipelineStage.EMBEDDER,
    PipelineStage.INDEXER,
]

QUERY_ORDER = [
    PipelineStage.QUERY_TRANSFORMER,
    PipelineStage.RETRIEVER,
    PipelineStage.FUSION,
    PipelineStage.RERANKER,
    PipelineStage.GRADER,
    PipelineStage.COMPRESSOR,
    PipelineStage.GENERATOR,
]


def ordered_calls(
    slots: list[dict[str, Any]],
    kind: PipelineKind,
    slot_overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Turn stored slots into first-binding calls, applying variant overrides."""
    order = INGEST_ORDER if kind == PipelineKind.INGEST else QUERY_ORDER
    by_stage = {str(slot["stage"]): slot for slot in slots}
    overrides = slot_overrides or {}
    calls: list[dict[str, Any]] = []
    for ordinal, stage in enumerate(order):
        override = overrides.get(stage.value)
        if override:
            calls.append(
                {
                    "stage": stage.value,
                    "plugin": override["plugin"],
                    "params": override.get("params") or {},
                    "ordinal": ordinal,
                }
            )
            continue
        slot = by_stage.get(stage.value)
        if not slot:
            continue
        bindings = slot["bindings"]
        if isinstance(bindings, str):
            continue
        mode = str(slot.get("mode") or "first")
        if mode == "ensemble" and len(bindings) > 1:
            calls.append(
                {
                    "stage": stage.value,
                    "ordinal": ordinal,
                    "parallel": [
                        {"plugin": item["name"], "params": item.get("params") or {}}
                        for item in bindings
                    ],
                }
            )
            continue
        binding = bindings[0]
        calls.append(
            {
                "stage": stage.value,
                "plugin": binding["name"],
                "params": binding.get("params") or {},
                "ordinal": ordinal,
            }
        )
    return calls


async def run_pipeline(
    *,
    calls: list[dict[str, Any]],
    data: dict[str, Any],
    ctx: PluginContext,
    registry: PluginRegistry,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    current = data
    for call in calls:
        plugin_label = (
            "+".join(item["plugin"] for item in call["parallel"])
            if call.get("parallel")
            else call["plugin"]
        )
        base = {
            "stage": call["stage"],
            "plugin_name": plugin_label,
            "ordinal": call["ordinal"],
        }
        if on_progress is not None:
            await on_progress({**base, "status": "running"})
        started = time.perf_counter()
        error: str | None = None
        output_meta: dict[str, Any] | None = None
        try:
            if call.get("parallel"):
                current = await _run_parallel(call, current, ctx, registry, resolved)
            else:
                current = await _run_one(call, current, ctx, registry, resolved)
            output_meta = _safe_meta(current, call["stage"])
        except Exception as exc:
            error = str(exc)
            latency = int((time.perf_counter() - started) * 1000)
            ctx.trace.record(
                SpanRecord(
                    stage=call["stage"],
                    plugin_name=plugin_label,
                    ordinal=call["ordinal"],
                    latency_ms=latency,
                    output=None,
                    error_message=error,
                )
            )
            if on_progress is not None:
                await on_progress(
                    {
                        **base,
                        "status": "error",
                        "latency_ms": latency,
                        "error_message": error,
                    }
                )
            raise
        latency = int((time.perf_counter() - started) * 1000)
        ctx.trace.record(
            SpanRecord(
                stage=call["stage"],
                plugin_name=plugin_label,
                ordinal=call["ordinal"],
                latency_ms=latency,
                output=output_meta,
            )
        )
        if on_progress is not None:
            await on_progress(
                {
                    **base,
                    "status": "done",
                    "latency_ms": latency,
                    "output": output_meta,
                }
            )
    current["resolved_params"] = resolved
    return current


async def _run_one(
    call: dict[str, Any],
    data: dict[str, Any],
    ctx: PluginContext,
    registry: PluginRegistry,
    resolved: dict[str, Any],
) -> dict[str, Any]:
    plugin = registry.get(call["stage"], call["plugin"])
    if plugin is None:
        raise ValueError(f"plugin not registered: {call['stage']}/{call['plugin']}")
    resolved[f"{call['stage']}:{call['plugin']}"] = merge_params(
        plugin.default_params, call["params"]
    )
    return await plugin.execute(data, call["params"], ctx)


async def _run_parallel(
    call: dict[str, Any],
    data: dict[str, Any],
    ctx: PluginContext,
    registry: PluginRegistry,
    resolved: dict[str, Any],
) -> dict[str, Any]:
    current = data
    for item in call["parallel"]:
        nested = {
            "stage": call["stage"],
            "plugin": item["plugin"],
            "params": item.get("params") or {},
            "ordinal": call["ordinal"],
        }
        current = await _run_one(nested, current, ctx, registry, resolved)
    # Each retriever overwrites `retrieved`; keep a non-empty list for traces.
    # Fusion still merges from `retrieved_lists`.
    lists = current.get("retrieved_lists") or {}
    if lists:
        current["retrieved"] = next(
            (items for items in lists.values() if items),
            [],
        )
    return current


# Keys each stage may emit into progress/traces (pipeline state still carries everything).
_PASSAGE_STAGES = frozenset({"retriever", "fusion", "reranker", "grader", "compressor"})
_PASSAGE_CONTENT_LIMIT = 4000
_TEXT_LIMIT = 4000

_STAGE_META_KEYS: dict[str, tuple[str, ...]] = {
    "loader": (
        "loader_kind",
        "loader_strategy",
        "raw_text_len",
        "tables_merged",
        "loader_warnings",
    ),
    "chunker": ("chunk_count",),
    "embedder": ("embedding_count", "chunk_count"),
    "indexer": ("indexed_count",),
    "query_transformer": (
        "query",
        "rewritten_query",
        "search_query_count",
        "hypothetical_count",
        "hypothetical_docs",
        "search_queries",
    ),
    "retriever": ("retrieved_count", "retrieved_by_plugin", "passages", "passages_by_plugin"),
    "fusion": ("retrieved_count", "fused_list_count", "passages"),
    "reranker": ("retrieved_count", "passages"),
    "grader": ("crag_action", "crag_max_score", "retrieved_count", "passages"),
    "compressor": ("retrieved_count", "passages"),
    "generator": ("answer_preview", "citation_marks"),
    "evaluator": ("metric_name", "metric_value"),
}


def _clip_text(value: Any, limit: int = _TEXT_LIMIT) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _passage_row(item: dict[str, Any], rank: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "rank": int(item.get("rank") or rank),
        "content": _clip_text(
            item.get("content") or item.get("expanded_content") or "",
            _PASSAGE_CONTENT_LIMIT,
        ),
    }
    chunk_id = item.get("chunk_id")
    if chunk_id is not None:
        row["chunk_id"] = str(chunk_id)
    for key in ("score", "rerank_score", "grade"):
        value = item.get(key)
        if value is None:
            continue
        try:
            row[key] = float(value)
        except (TypeError, ValueError):
            continue
    return row


def _passages_from_items(items: list[Any] | None) -> list[dict[str, Any]]:
    passages: list[dict[str, Any]] = []
    for index, item in enumerate(items or [], start=1):
        if isinstance(item, dict):
            passages.append(_passage_row(item, index))
    return passages


def _citation_marks(answer: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\[\d+\]", answer or "")))


def _safe_meta(data: dict[str, Any], stage: str | None = None) -> dict[str, Any]:
    """Stage-scoped trace payload without embeddings or raw secrets."""
    available: dict[str, Any] = {}
    if "query" in data:
        available["query"] = _clip_text(data["query"], 2000)
    if "rewritten_query" in data:
        available["rewritten_query"] = _clip_text(data["rewritten_query"], 2000)
    if "chunks" in data:
        available["chunk_count"] = len(data["chunks"] or [])
    embeddings = data.get("embeddings")
    if embeddings is not None:
        available["embedding_count"] = len(embeddings)
    if data.get("raw_text"):
        available["raw_text_len"] = len(str(data["raw_text"]))
    if data.get("loader_kind"):
        available["loader_kind"] = data["loader_kind"]
    if data.get("loader_strategy"):
        available["loader_strategy"] = data["loader_strategy"]
    if data.get("tables_merged"):
        available["tables_merged"] = data["tables_merged"]
    if data.get("loader_warnings"):
        available["loader_warnings"] = data["loader_warnings"]
    if "indexed_count" in data:
        available["indexed_count"] = data["indexed_count"]
    lists = data.get("retrieved_lists")
    if isinstance(lists, dict) and lists:
        available["retrieved_by_plugin"] = {
            name: len(items or []) for name, items in lists.items()
        }
        available["fused_list_count"] = sum(1 for items in lists.values() if items)
        if stage == "retriever":
            available["passages_by_plugin"] = {
                name: _passages_from_items(items if isinstance(items, list) else [])
                for name, items in lists.items()
            }
    if "retrieved" in data:
        retrieved = list(data["retrieved"] or [])
        available["retrieved_count"] = len(retrieved)
        if stage in _PASSAGE_STAGES:
            available["passages"] = _passages_from_items(retrieved)
    if "search_queries" in data:
        queries = [str(item) for item in (data["search_queries"] or []) if item]
        available["search_query_count"] = len(queries)
        available["search_queries"] = [_clip_text(item, 2000) for item in queries]
    hypos = data.get("hypothetical_docs")
    if hypos is not None:
        docs = [str(item) for item in (hypos or []) if item]
        available["hypothetical_count"] = len(docs)
        available["hypothetical_docs"] = [_clip_text(item) for item in docs]
    if "crag_action" in data:
        available["crag_action"] = data["crag_action"]
    if "crag_max_score" in data:
        available["crag_max_score"] = data["crag_max_score"]
    if "answer" in data:
        answer = str(data["answer"])
        available["answer_preview"] = answer[:500]
        marks = _citation_marks(answer)
        if marks:
            available["citation_marks"] = marks
    if data.get("metric_name") is not None:
        available["metric_name"] = data["metric_name"]
    if "metric_value" in data:
        available["metric_value"] = data["metric_value"]

    allowed = _STAGE_META_KEYS.get(stage or "")
    if allowed is None:
        return available
    return {key: available[key] for key in allowed if key in available}

def default_collection_id(kb: dict[str, Any]) -> UUID | None:
    collections = kb.get("collections") or []
    for collection in collections:
        if collection.get("is_default"):
            return collection["id"]
    if collections:
        return collections[0]["id"]
    return None
