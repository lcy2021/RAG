"""Multi-turn naive chat: one query pipeline run per user message."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from engine.citations import citation_spans, normalize_sources
from engine.runner import default_collection_id, ordered_calls, run_pipeline
from infra.models import LiteLLMClient
from models.enums import PipelineKind, PipelineStage
from models.schemas import (
    ChatMessageIn,
    ChatMessageOut,
    ChatTurnOut,
    CitationOut,
    ConversationCreate,
    ConversationOut,
    RagRunSourcesOut,
    RetrievedSourceOut,
    StageTraceOut,
)
from plugins.context import MemoryTrace, PluginContext
from plugins.registry import get_registry
from repositories.chat import ChatRepository
from repositories.knowledge_bases import KnowledgeBaseRepository
from repositories.pipelines import PipelineRepository
from repositories.settings import SettingsRepository
from services.bindings import BindingResolver
from services.knowledge_bases import first_slot_binding_id

_STREAM_SENTINEL = object()


class ChatService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._settings = settings
        self._chat = ChatRepository(session)
        self._kb = KnowledgeBaseRepository(session)
        self._pipelines = PipelineRepository(session)
        self._resolver = BindingResolver(SettingsRepository(session))

    async def list_conversations(self) -> list[ConversationOut]:
        rows = await self._chat.list_conversations()
        return [ConversationOut.model_validate(row) for row in rows]

    async def delete_conversation(self, conversation_id: UUID) -> None:
        deleted = await self._chat.delete_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="conversation not found")

    async def create_conversation(self, payload: ConversationCreate) -> ConversationOut:
        kb = await self._kb.get(payload.knowledge_base_id)
        if not kb:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        pipeline = await self._pipelines.get(payload.pipeline_config_id)
        if not pipeline or pipeline.get("kind") != PipelineKind.QUERY:
            raise HTTPException(status_code=400, detail="query pipeline not found")
        row = await self._chat.insert_conversation(
            knowledge_base_id=payload.knowledge_base_id,
            pipeline_config_id=payload.pipeline_config_id,
            title=payload.title,
            history_window=payload.history_window,
        )
        return ConversationOut.model_validate(row)

    async def list_messages(self, conversation_id: UUID) -> list[ChatMessageOut]:
        await self._require_conversation(conversation_id)
        rows = await self._chat.list_messages(conversation_id)
        return [ChatMessageOut.model_validate(row) for row in rows]

    async def get_run_sources(
        self, conversation_id: UUID, rag_run_id: UUID
    ) -> RagRunSourcesOut:
        await self._require_conversation(conversation_id)
        run = await self._chat.get_rag_run(rag_run_id)
        if not run or run.get("conversation_id") != conversation_id:
            raise HTTPException(status_code=404, detail="rag run not found")
        sources, citations = await self._load_sources(rag_run_id)
        traces = await self._load_traces(rag_run_id)
        return RagRunSourcesOut(
            rag_run_id=rag_run_id,
            sources=sources,
            citations=citations,
            traces=traces,
        )

    async def send_message(self, conversation_id: UUID, payload: ChatMessageIn) -> ChatTurnOut:
        prepared = await self._prepare_turn(conversation_id, payload)
        return await self._run_turn(prepared, on_token=None, on_progress=None)

    async def prepare_stream(
        self, conversation_id: UUID, payload: ChatMessageIn
    ) -> dict[str, Any]:
        """Validate and persist the user turn; raise HTTPException before SSE starts."""
        return await self._prepare_turn(conversation_id, payload)

    async def iter_stream_events(
        self, prepared: dict[str, Any]
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        async for event in self._iter_stream_events(prepared):
            yield event

    async def _iter_stream_events(
        self, prepared: dict[str, Any]
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        yield (
            "meta",
            {
                "conversation_id": str(prepared["conversation_id"]),
                "rag_run_id": str(prepared["run"]["id"]),
                "user": ChatMessageOut.model_validate(prepared["user"]).model_dump(mode="json"),
            },
        )

        queue: asyncio.Queue[tuple[str, Any] | object] = asyncio.Queue()

        async def on_token(delta: str) -> None:
            await queue.put(("delta", delta))

        async def on_progress(event: dict[str, Any]) -> None:
            await queue.put(("progress", event))

        async def run() -> ChatTurnOut:
            try:
                return await self._run_turn(
                    prepared, on_token=on_token, on_progress=on_progress
                )
            finally:
                await queue.put(_STREAM_SENTINEL)

        task = asyncio.create_task(run())
        while True:
            item = await queue.get()
            if item is _STREAM_SENTINEL:
                break
            assert isinstance(item, tuple)
            kind, payload = item
            if kind == "delta":
                yield ("delta", {"text": str(payload)})
            else:
                yield ("progress", dict(payload))

        try:
            turn = await task
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            yield ("error", {"detail": detail})
            return
        except Exception as exc:  # noqa: BLE001 — surface pipeline failures over SSE
            yield ("error", {"detail": str(exc)})
            return

        yield ("done", turn.model_dump(mode="json"))

    async def _prepare_turn(self, conversation_id: UUID, payload: ChatMessageIn) -> dict[str, Any]:
        conversation = await self._require_conversation(conversation_id)
        kb_id = conversation.get("knowledge_base_id")
        if not kb_id:
            raise HTTPException(
                status_code=400,
                detail="knowledge base was deleted; start a new chat with another knowledge base",
            )
        kb = await self._kb.get(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        pipeline_id = conversation.get("pipeline_config_id")
        if not pipeline_id:
            raise HTTPException(status_code=400, detail="no query pipeline configured")
        pipeline = await self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.get("kind") != PipelineKind.QUERY:
            raise HTTPException(status_code=400, detail="query pipeline not found")
        collection_id = default_collection_id(kb)
        if collection_id is None:
            raise HTTPException(
                status_code=400,
                detail="knowledge base has no vector collection; upload a document first",
            )
        turn = await self._chat.next_turn_index(conversation_id)
        user = await self._chat.insert_message(
            conversation_id=conversation_id,
            turn_index=turn,
            role="user",
            content=payload.content,
        )
        run = await self._chat.insert_rag_run(
            conversation_id=conversation_id,
            trigger_message_id=user["id"],
            pipeline_config_id=pipeline_id,
            knowledge_base_id=kb["id"],
            vector_collection_id=collection_id,
            resolved_params={},
        )
        history_rows = await self._chat.list_messages(conversation_id)
        window = int(conversation["history_window"])
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in history_rows
            if row["id"] != user["id"]
        ][-window:]
        calls = ordered_calls(pipeline["slots"], PipelineKind.QUERY)
        data = {
            "query": payload.content,
            "history": history,
            "knowledge_base_id": kb["id"],
            "vector_collection_id": collection_id,
        }
        return {
            "conversation_id": conversation_id,
            "kb": kb,
            "pipeline": pipeline,
            "user": user,
            "run": run,
            "calls": calls,
            "data": data,
            "turn_index": turn,
        }

    async def _run_turn(
        self,
        prepared: dict[str, Any],
        *,
        on_token: Any,
        on_progress: Any = None,
    ) -> ChatTurnOut:
        conversation_id: UUID = prepared["conversation_id"]
        kb = prepared["kb"]
        pipeline = prepared["pipeline"]
        user = prepared["user"]
        run = prepared["run"]
        ctx = PluginContext(
            resolver=self._resolver,
            kb_repo=self._kb,
            models=LiteLLMClient(),
            trace=MemoryTrace(),
            default_embedder_binding_id=kb.get("default_embedder_binding_id"),
            default_generator_binding_id=(
                kb.get("default_generator_binding_id")
                or first_slot_binding_id(pipeline, PipelineStage.GENERATOR)
            ),
        )
        if on_token is not None:
            ctx.extra["on_token"] = on_token
        started = time.perf_counter()
        try:
            result = await run_pipeline(
                calls=prepared["calls"],
                data=prepared["data"],
                ctx=ctx,
                registry=get_registry(),
                on_progress=on_progress,
            )
            answer = result.get("answer") or ""
            latency = int((time.perf_counter() - started) * 1000)
            usage = ctx.usage.persist_fields()
            await self._chat.finish_rag_run(
                run["id"],
                status="succeeded",
                answer_text=answer,
                rewritten_query=result.get("rewritten_query"),
                error_message=None,
                latency_ms=latency,
                **usage,
            )
            retrieved = list(result.get("retrieved") or [])
            sources_payload = normalize_sources(retrieved, answer=answer)
            rank_to_retrieved_id: dict[int, UUID] = {}
            for item in sources_payload:
                chunk_id = item.get("chunk_id")
                row = await self._chat.insert_retrieved_chunk(
                    rag_run_id=run["id"],
                    chunk_id=chunk_id,
                    retriever=str(item.get("retriever") or "dense"),
                    rank=int(item.get("rank") or 0),
                    score=item.get("score"),
                    content_snapshot=str(item.get("content") or ""),
                )
                rank_to_retrieved_id[int(row["rank"])] = row["id"]
            citation_rows: list[CitationOut] = []
            for span in citation_spans(answer):
                rank = int(span["rank"])
                await self._chat.insert_citation(
                    rag_run_id=run["id"],
                    retrieved_id=rank_to_retrieved_id.get(rank),
                    char_start=span.get("char_start"),
                    char_end=span.get("char_end"),
                    quote=span.get("quote"),
                )
                citation_rows.append(
                    CitationOut(
                        rank=rank,
                        char_start=span.get("char_start"),
                        char_end=span.get("char_end"),
                        quote=span.get("quote"),
                    )
                )
            source_rows = [RetrievedSourceOut.model_validate(item) for item in sources_payload]
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            usage = ctx.usage.persist_fields()
            await self._chat.finish_rag_run(
                run["id"],
                status="failed",
                answer_text=None,
                rewritten_query=None,
                error_message=str(exc),
                latency_ms=latency,
                **usage,
            )
            for span in ctx.trace.spans:
                await self._chat.insert_stage_trace(
                    rag_run_id=run["id"],
                    stage=span.stage,
                    plugin_name=span.plugin_name,
                    ordinal=span.ordinal,
                    output_json=span.output,
                    latency_ms=span.latency_ms,
                    error_message=span.error_message,
                )
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        for span in ctx.trace.spans:
            await self._chat.insert_stage_trace(
                rag_run_id=run["id"],
                stage=span.stage,
                plugin_name=span.plugin_name,
                ordinal=span.ordinal,
                output_json=span.output,
                latency_ms=span.latency_ms,
                error_message=span.error_message,
            )
        assistant = await self._chat.insert_message(
            conversation_id=conversation_id,
            turn_index=prepared["turn_index"],
            role="assistant",
            content=result.get("answer") or "",
            rag_run_id=run["id"],
        )
        await self._chat.touch_conversation(conversation_id)
        traces = await self._load_traces(run["id"])
        return ChatTurnOut(
            conversation_id=conversation_id,
            user=ChatMessageOut.model_validate(user),
            assistant=ChatMessageOut.model_validate(assistant),
            rag_run_id=run["id"],
            traces=traces,
            sources=source_rows,
            citations=citation_rows,
        )

    async def _load_traces(self, rag_run_id: UUID) -> list[StageTraceOut]:
        rows = await self._chat.list_traces(rag_run_id)
        return [
            StageTraceOut(
                stage=str(row.get("stage") or ""),
                plugin_name=str(row.get("plugin_name") or ""),
                ordinal=int(row.get("ordinal") or 0),
                latency_ms=row.get("latency_ms"),
                output=row.get("output_json"),
                error_message=row.get("error_message"),
            )
            for row in rows
        ]

    async def _load_sources(
        self, rag_run_id: UUID
    ) -> tuple[list[RetrievedSourceOut], list[CitationOut]]:
        retrieved_rows = await self._chat.list_retrieved(rag_run_id)
        citation_rows = await self._chat.list_citations(rag_run_id)
        cited_ids = {
            row["retrieved_id"] for row in citation_rows if row.get("retrieved_id") is not None
        }
        quoted_ranks: set[int] = set()
        for row in citation_rows:
            quote = row.get("quote") or ""
            if quote.startswith("[") and quote.endswith("]"):
                try:
                    quoted_ranks.add(int(quote[1:-1]))
                except ValueError:
                    pass
        sources: list[RetrievedSourceOut] = []
        id_to_rank: dict[UUID, int] = {}
        for row in retrieved_rows:
            rank = int(row["rank"])
            id_to_rank[row["id"]] = rank
            sources.append(
                RetrievedSourceOut(
                    rank=rank,
                    chunk_id=row.get("chunk_id"),
                    content=row.get("content_snapshot") or "",
                    score=row.get("score"),
                    retriever=row.get("retriever") or "dense",
                    cited=row["id"] in cited_ids or rank in quoted_ranks,
                )
            )
        citations: list[CitationOut] = []
        for row in citation_rows:
            retrieved_id = row.get("retrieved_id")
            rank = id_to_rank.get(retrieved_id) if retrieved_id else None
            if rank is None:
                quote = row.get("quote") or ""
                try:
                    rank = int(quote.strip("[]")) if quote else 0
                except ValueError:
                    rank = 0
            citations.append(
                CitationOut(
                    rank=int(rank or 0),
                    char_start=row.get("char_start"),
                    char_end=row.get("char_end"),
                    quote=row.get("quote"),
                )
            )
        return sources, citations

    async def _require_conversation(self, conversation_id: UUID) -> dict:
        row = await self._chat.get_conversation(conversation_id)
        if not row:
            raise HTTPException(status_code=404, detail="conversation not found")
        return row
