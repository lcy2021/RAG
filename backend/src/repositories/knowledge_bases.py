"""knowledge_bases, documents, stored_files, vector_collections, ingest_jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from db.entities import (
    Chunk,
    ChunkEmbedding,
    Document,
    DocumentVersion,
    IngestJob,
    IngestStageTrace,
    KnowledgeBase,
    PipelinePromotion,
    Scenario,
    StoredFile,
    VectorCollection,
)
from db.serialize import as_dict
from models.enums import DocumentStatus, PipelineStage, RunStatus, StorageBackend
from repositories.base import persist, row_dict


def _kb_payload(kb: KnowledgeBase, collections: list[VectorCollection]) -> dict[str, Any]:
    data = as_dict(kb)
    data["collections"] = [as_dict(item) for item in collections]
    return data


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.deleted_at.is_(None))
            .order_by(KnowledgeBase.name)
        )
        items = []
        for kb in result:
            collections = await self._collections(kb.id)
            items.append(_kb_payload(kb, collections))
        return items

    async def get(self, kb_id: UUID) -> dict[str, Any] | None:
        kb = await self._session.get(KnowledgeBase, kb_id)
        if kb is None or kb.deleted_at is not None:
            return None
        return _kb_payload(kb, await self._collections(kb_id))

    async def mark_deleted(self, kb_id: UUID) -> bool:
        """Soft-delete a knowledge base so it disappears from list/get immediately."""
        kb = await self._session.get(KnowledgeBase, kb_id)
        if kb is None or kb.deleted_at is not None:
            return False
        kb.deleted_at = datetime.now(UTC)
        kb.updated_at = datetime.now(UTC)
        await self._session.flush()
        return True

    async def blocking_reference_count(self, kb_id: UUID) -> int:
        """Count FK rows that block hard delete (scenarios / promotions)."""
        scenarios = await self._session.scalar(
            select(func.count()).select_from(Scenario).where(Scenario.knowledge_base_id == kb_id)
        )
        promotions = await self._session.scalar(
            select(func.count())
            .select_from(PipelinePromotion)
            .where(PipelinePromotion.knowledge_base_id == kb_id)
        )
        return int(scenarios or 0) + int(promotions or 0)

    async def delete(self, kb_id: UUID) -> list[str] | None:
        """Hard-delete a knowledge base and dependent chat/runs. Returns storage keys to unlink."""
        kb = await self._session.get(KnowledgeBase, kb_id)
        if kb is None:
            return None

        docs = await self._session.scalars(
            select(Document).where(Document.knowledge_base_id == kb_id)
        )
        file_ids = [row.stored_file_id for row in docs if row.stored_file_id]
        storage_keys: list[str] = []
        if file_ids:
            files = await self._session.scalars(
                select(StoredFile).where(StoredFile.id.in_(file_ids))
            )
            storage_keys = [row.storage_key for row in files if row.storage_key]

        collection_ids = list(
            await self._session.scalars(
                select(VectorCollection.id).where(VectorCollection.knowledge_base_id == kb_id)
            )
        )
        # Drop dense vectors first — ORM cascade on large embedding tables is very slow.
        if collection_ids:
            await self._session.execute(
                delete(ChunkEmbedding).where(
                    ChunkEmbedding.vector_collection_id.in_(collection_ids)
                )
            )
            await self._session.flush()

        await self._session.delete(kb)
        await self._session.flush()

        if file_ids:
            await self._session.execute(delete(StoredFile).where(StoredFile.id.in_(file_ids)))
            await self._session.flush()
        return storage_keys

    async def insert(
        self,
        *,
        name: str,
        description: str | None,
        ingest_pipeline_id: UUID | None,
        query_pipeline_id: UUID | None,
        default_embedder_binding_id: UUID | None,
        default_generator_binding_id: UUID | None,
    ) -> dict[str, Any]:
        kb = KnowledgeBase(
            name=name,
            description=description,
            ingest_pipeline_id=ingest_pipeline_id,
            query_pipeline_id=query_pipeline_id,
            default_embedder_binding_id=default_embedder_binding_id,
            default_generator_binding_id=default_generator_binding_id,
        )
        await persist(self._session, kb)
        return _kb_payload(kb, [])

    async def _collections(self, kb_id: UUID) -> list[VectorCollection]:
        result = await self._session.scalars(
            select(VectorCollection)
            .where(VectorCollection.knowledge_base_id == kb_id)
            .order_by(VectorCollection.created_at)
        )
        return list(result)

    async def list_collections(self, kb_id: UUID) -> list[dict[str, Any]]:
        return [as_dict(item) for item in await self._collections(kb_id)]

    async def get_collection(self, collection_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(VectorCollection, collection_id)
        return as_dict(row) if row else None

    async def insert_collection(
        self,
        *,
        knowledge_base_id: UUID,
        name: str,
        embedder_binding_id: UUID,
        metric: str = "cosine",
        dim: int | None = None,
        is_default: bool = True,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            VectorCollection(
                knowledge_base_id=knowledge_base_id,
                name=name,
                embedder_binding_id=embedder_binding_id,
                metric=metric,
                dim=dim,
                is_default=is_default,
            ),
        )

    async def update_collection_dim(self, collection_id: UUID, dim: int) -> None:
        await self._session.execute(
            update(VectorCollection)
            .where(VectorCollection.id == collection_id, VectorCollection.dim.is_(None))
            .values(dim=dim)
        )

    async def set_default_collection(self, kb_id: UUID, collection_id: UUID) -> None:
        collections = await self._collections(kb_id)
        found = False
        for item in collections:
            if item.id == collection_id:
                item.is_default = True
                found = True
            else:
                item.is_default = False
        if not found:
            raise ValueError("collection not found in knowledge base")
        await self._session.flush()

    async def apply_promotion(
        self,
        kb_id: UUID,
        *,
        ingest_pipeline_id: UUID | None,
        query_pipeline_id: UUID | None,
        promoted_from_eval_run_id: UUID,
    ) -> dict[str, Any] | None:
        kb = await self._session.get(KnowledgeBase, kb_id)
        if kb is None:
            return None
        if ingest_pipeline_id is not None:
            kb.ingest_pipeline_id = ingest_pipeline_id
        if query_pipeline_id is not None:
            kb.query_pipeline_id = query_pipeline_id
        kb.promoted_from_eval_run_id = promoted_from_eval_run_id
        kb.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(kb)
        return _kb_payload(kb, await self._collections(kb_id))

    async def insert_stored_file(
        self,
        *,
        original_filename: str,
        content_type: str | None,
        byte_size: int,
        content_hash: str,
        storage_key: str,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            StoredFile(
                original_filename=original_filename,
                content_type=content_type,
                byte_size=byte_size,
                content_hash=content_hash,
                storage_backend=StorageBackend.LOCAL,
                storage_key=storage_key,
            ),
        )

    async def insert_document(
        self,
        *,
        knowledge_base_id: UUID,
        stored_file_id: UUID,
        source_uri: str,
        mime_type: str | None,
        title: str | None,
        content_hash: str,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            Document(
                knowledge_base_id=knowledge_base_id,
                stored_file_id=stored_file_id,
                source_uri=source_uri,
                mime_type=mime_type,
                title=title,
                content_hash=content_hash,
            ),
            include={
                "id",
                "knowledge_base_id",
                "source_uri",
                "title",
                "status",
                "content_hash",
                "created_at",
            },
        )

    async def insert_document_version(
        self,
        *,
        document_id: UUID,
        version_no: int,
        content_hash: str,
        raw_text: str | None,
        byte_size: int,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            DocumentVersion(
                document_id=document_id,
                version_no=version_no,
                content_hash=content_hash,
                raw_text=raw_text,
                byte_size=byte_size,
            ),
            include={"id", "document_id", "version_no", "content_hash"},
        )

    async def get_stored_file(self, stored_file_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(StoredFile, stored_file_id)
        if row is None:
            return None
        return as_dict(
            row,
            include={
                "id",
                "original_filename",
                "content_type",
                "storage_key",
                "byte_size",
                "content_hash",
            },
        )

    async def get_document(self, document_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(Document, document_id)
        if row is None:
            return None
        return as_dict(
            row,
            include={
                "id",
                "knowledge_base_id",
                "stored_file_id",
                "source_uri",
                "mime_type",
                "title",
                "status",
                "content_hash",
                "created_at",
            },
        )

    async def list_documents(self, kb_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(Document)
            .where(Document.knowledge_base_id == kb_id)
            .order_by(Document.created_at.desc())
        )
        return [
            as_dict(
                row,
                include={
                    "id",
                    "knowledge_base_id",
                    "source_uri",
                    "title",
                    "status",
                    "content_hash",
                    "created_at",
                },
            )
            for row in result
        ]

    async def delete_document(self, kb_id: UUID, document_id: UUID) -> list[str] | None:
        """Delete a document and its stored file. Returns storage keys to unlink, or None if missing."""
        document = await self._session.get(Document, document_id)
        if document is None or document.knowledge_base_id != kb_id:
            return None

        storage_keys: list[str] = []
        stored_file_id = document.stored_file_id
        if stored_file_id:
            stored = await self._session.get(StoredFile, stored_file_id)
            if stored is not None and stored.storage_key:
                storage_keys.append(stored.storage_key)

        await self._session.delete(document)
        await self._session.flush()

        if stored_file_id:
            await self._session.execute(delete(StoredFile).where(StoredFile.id == stored_file_id))
            await self._session.flush()
        return storage_keys

    async def latest_version(self, document_id: UUID) -> dict[str, Any] | None:
        result = await self._session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_no.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        return as_dict(
            row,
            include={"id", "document_id", "version_no", "content_hash", "raw_text", "byte_size"},
        )

    async def update_version_raw_text(self, version_id: UUID, raw_text: str) -> None:
        row = await self._session.get(DocumentVersion, version_id)
        if row is None:
            return
        row.raw_text = raw_text
        await self._session.flush()

    async def set_document_status(self, document_id: UUID, status: str) -> None:
        document = await self._session.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus(status)
        await self._session.flush()

    async def insert_chunk(
        self,
        *,
        document_version_id: UUID,
        chunker_plugin: str,
        ordinal: int,
        content: str,
        token_count: int | None,
        metadata: dict[str, Any],
        parent_chunk_id: UUID | None = None,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            Chunk(
                document_version_id=document_version_id,
                parent_chunk_id=parent_chunk_id,
                chunker_plugin=chunker_plugin,
                ordinal=ordinal,
                content=content,
                token_count=token_count,
                extra_metadata=metadata,
            ),
            include={"id", "ordinal", "content", "parent_chunk_id"},
        )

    async def insert_embedding(
        self,
        *,
        chunk_id: UUID,
        vector_collection_id: UUID,
        embedder_plugin: str,
        embedding: list[float],
        dim: int,
    ) -> None:
        self._session.add(
            ChunkEmbedding(
                chunk_id=chunk_id,
                vector_collection_id=vector_collection_id,
                embedder_plugin=embedder_plugin,
                embedding=embedding,
                dim=dim,
            )
        )
        await self._session.flush()

    async def dense_search(
        self,
        *,
        vector_collection_id: UUID,
        query_embedding: list[float],
        top_k: int,
        score_threshold: float | None,
    ) -> list[dict[str, Any]]:
        parent = aliased(Chunk)
        distance = ChunkEmbedding.embedding.cosine_distance(query_embedding)
        score = (literal(1.0) - distance).label("score")
        stmt = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.content,
                Chunk.extra_metadata.label("metadata"),
                Chunk.parent_chunk_id,
                func.coalesce(parent.content, Chunk.content).label("expanded_content"),
                score,
            )
            .select_from(ChunkEmbedding)
            .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
            .outerjoin(parent, parent.id == Chunk.parent_chunk_id)
            .where(
                ChunkEmbedding.vector_collection_id == vector_collection_id,
                Chunk.superseded_at.is_(None),
            )
        )
        if score_threshold is not None:
            stmt = stmt.where(score >= score_threshold)
        stmt = stmt.order_by(distance).limit(top_k)
        result = await self._session.execute(stmt)
        return [row_dict(row) for row in result]

    async def list_collection_chunks(self, vector_collection_id: UUID) -> list[dict[str, Any]]:
        parent = aliased(Chunk)
        stmt = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.content,
                Chunk.extra_metadata.label("metadata"),
                Chunk.parent_chunk_id,
                func.coalesce(parent.content, Chunk.content).label("expanded_content"),
            )
            .select_from(ChunkEmbedding)
            .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
            .outerjoin(parent, parent.id == Chunk.parent_chunk_id)
            .where(
                ChunkEmbedding.vector_collection_id == vector_collection_id,
                Chunk.superseded_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return [row_dict(row) for row in result]

    async def insert_ingest_job(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        vector_collection_id: UUID,
        ingest_pipeline_id: UUID,
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            IngestJob(
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                document_version_id=document_version_id,
                vector_collection_id=vector_collection_id,
                ingest_pipeline_id=ingest_pipeline_id,
                status=RunStatus.QUEUED,
            ),
            include={
                "id",
                "knowledge_base_id",
                "document_id",
                "status",
                "error_message",
                "stats",
                "created_at",
                "started_at",
                "finished_at",
            },
        )

    async def finish_ingest_job(
        self,
        job_id: UUID,
        *,
        status: str,
        error_message: str | None,
        stats: dict[str, Any],
    ) -> dict[str, Any]:
        job = await self._session.get(IngestJob, job_id)
        if job is None:
            raise LookupError(f"ingest job {job_id} not found")
        job.status = RunStatus(status)
        job.error_message = error_message
        job.stats = stats
        if job.started_at is None:
            job.started_at = datetime.now(UTC)
        job.finished_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(job)
        return as_dict(
            job,
            include={
                "id",
                "knowledge_base_id",
                "document_id",
                "status",
                "error_message",
                "stats",
                "created_at",
                "started_at",
                "finished_at",
            },
        )

    async def insert_ingest_trace(
        self,
        *,
        ingest_job_id: UUID,
        stage: str,
        plugin_name: str,
        ordinal: int,
        output_json: dict[str, Any] | None,
        error_message: str | None,
        latency_ms: int | None,
    ) -> None:
        self._session.add(
            IngestStageTrace(
                ingest_job_id=ingest_job_id,
                stage=PipelineStage(stage),
                plugin_name=plugin_name,
                ordinal=ordinal,
                output_json=output_json,
                error_message=error_message,
                latency_ms=latency_ms,
            )
        )
        await self._session.flush()
