"""conversations, messages, rag_runs, stage_traces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.entities import Citation, Conversation, Message, RagRun, RetrievedChunk, StageTrace
from db.serialize import as_dict
from models.enums import PipelineStage, RunStatus
from repositories.base import persist, remove_by_pk


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_conversation(
        self,
        *,
        knowledge_base_id: UUID,
        pipeline_config_id: UUID | None,
        title: str | None,
        history_window: int,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            Conversation(
                knowledge_base_id=knowledge_base_id,
                pipeline_config_id=pipeline_config_id,
                title=title,
                history_window=history_window,
            ),
        )

    async def get_conversation(self, conversation_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(Conversation, conversation_id)
        return as_dict(row) if row else None

    async def get_rag_run(self, rag_run_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(RagRun, rag_run_id)
        return as_dict(row, include={"id", "conversation_id", "status"}) if row else None

    async def list_conversations(self) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(Conversation).order_by(Conversation.updated_at.desc())
        )
        return [as_dict(row) for row in result]

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        return await remove_by_pk(self._session, Conversation, conversation_id)

    async def next_turn_index(self, conversation_id: UUID) -> int:
        value = await self._session.scalar(
            select(func.coalesce(func.max(Message.turn_index), -1) + 1).where(
                Message.conversation_id == conversation_id
            )
        )
        return int(value or 0)

    async def insert_message(
        self,
        *,
        conversation_id: UUID,
        turn_index: int,
        role: str,
        content: str,
        rag_run_id: UUID | None = None,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            Message(
                conversation_id=conversation_id,
                turn_index=turn_index,
                role=role,
                content=content,
                rag_run_id=rag_run_id,
            ),
        )

    async def list_messages(self, conversation_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.turn_index, Message.created_at)
        )
        return [as_dict(row) for row in result]

    async def insert_rag_run(
        self,
        *,
        conversation_id: UUID,
        trigger_message_id: UUID,
        pipeline_config_id: UUID,
        knowledge_base_id: UUID,
        vector_collection_id: UUID | None,
        resolved_params: dict[str, Any],
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            RagRun(
                conversation_id=conversation_id,
                trigger_message_id=trigger_message_id,
                pipeline_config_id=pipeline_config_id,
                knowledge_base_id=knowledge_base_id,
                vector_collection_id=vector_collection_id,
                variant_label="default",
                resolved_params=resolved_params,
                status=RunStatus.RUNNING,
            ),
            include={"id"},
        )

    async def insert_eval_rag_run(
        self,
        *,
        eval_run_id: UUID,
        eval_item_id: UUID,
        compare_variant_id: UUID | None,
        pipeline_config_id: UUID,
        knowledge_base_id: UUID,
        vector_collection_id: UUID | None,
        variant_label: str,
        slot_overrides: dict[str, Any],
        resolved_params: dict[str, Any],
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            RagRun(
                eval_run_id=eval_run_id,
                eval_item_id=eval_item_id,
                compare_variant_id=compare_variant_id,
                pipeline_config_id=pipeline_config_id,
                knowledge_base_id=knowledge_base_id,
                vector_collection_id=vector_collection_id,
                variant_label=variant_label,
                slot_overrides=slot_overrides,
                resolved_params=resolved_params,
                status=RunStatus.RUNNING,
            ),
            include={"id"},
        )

    async def finish_rag_run(
        self,
        run_id: UUID,
        *,
        status: str,
        answer_text: str | None,
        rewritten_query: str | None,
        error_message: str | None,
        latency_ms: int | None,
        token_in: int | None = None,
        token_out: int | None = None,
        token_cached: int | None = None,
        cost_micros: int | None = None,
    ) -> None:
        run = await self._session.get(RagRun, run_id)
        if run is None:
            return
        run.status = RunStatus(status)
        run.answer_text = answer_text
        run.rewritten_query = rewritten_query
        run.error_message = error_message
        run.latency_ms = latency_ms
        run.token_in = token_in
        run.token_out = token_out
        run.token_cached = token_cached
        run.cost_micros = cost_micros
        run.finished_at = datetime.now(UTC)
        await self._session.flush()

    async def insert_stage_trace(
        self,
        *,
        rag_run_id: UUID,
        stage: str,
        plugin_name: str,
        ordinal: int,
        output_json: dict[str, Any] | None,
        latency_ms: int | None,
        error_message: str | None,
    ) -> None:
        self._session.add(
            StageTrace(
                rag_run_id=rag_run_id,
                stage=PipelineStage(stage),
                plugin_name=plugin_name,
                ordinal=ordinal,
                output_json=output_json,
                latency_ms=latency_ms,
                error_message=error_message,
            )
        )
        await self._session.flush()

    async def insert_retrieved_chunk(
        self,
        *,
        rag_run_id: UUID,
        chunk_id: UUID | None,
        retriever: str,
        rank: int,
        score: float | None,
        content_snapshot: str,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            RetrievedChunk(
                rag_run_id=rag_run_id,
                chunk_id=chunk_id,
                retriever=retriever,
                rank=rank,
                score=score,
                content_snapshot=content_snapshot,
            ),
            include={"id", "rank", "chunk_id", "retriever", "score", "content_snapshot"},
        )

    async def insert_citation(
        self,
        *,
        rag_run_id: UUID,
        retrieved_id: UUID | None,
        char_start: int | None,
        char_end: int | None,
        quote: str | None,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            Citation(
                rag_run_id=rag_run_id,
                retrieved_id=retrieved_id,
                char_start=char_start,
                char_end=char_end,
                quote=quote,
            ),
            include={"id", "retrieved_id", "char_start", "char_end", "quote"},
        )

    async def list_retrieved(self, rag_run_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(RetrievedChunk)
            .where(RetrievedChunk.rag_run_id == rag_run_id)
            .order_by(RetrievedChunk.rank)
        )
        return [
            as_dict(
                row,
                include={"id", "chunk_id", "retriever", "rank", "score", "content_snapshot"},
            )
            for row in result
        ]

    async def list_citations(self, rag_run_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(Citation).where(Citation.rag_run_id == rag_run_id).order_by(Citation.char_start)
        )
        return [
            as_dict(
                row,
                include={"id", "retrieved_id", "char_start", "char_end", "quote"},
            )
            for row in result
        ]

    async def list_traces(self, rag_run_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(StageTrace)
            .where(StageTrace.rag_run_id == rag_run_id)
            .order_by(StageTrace.created_at, StageTrace.ordinal)
        )
        traces = []
        for row in result:
            traces.append(
                as_dict(
                    row,
                    include={
                        "stage",
                        "plugin_name",
                        "ordinal",
                        "output_json",
                        "latency_ms",
                        "error_message",
                    },
                )
            )
        return traces

    async def touch_conversation(self, conversation_id: UUID) -> None:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            return
        conversation.updated_at = datetime.now(UTC)
        await self._session.flush()
