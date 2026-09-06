"""Knowledge base, document upload, and inline ingest jobs."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from engine.runner import default_collection_id, ordered_calls, run_pipeline
from infra.models import LiteLLMClient
from models.enums import PipelineKind, PipelineStage
from models.schemas import DocumentOut, IngestJobOut, KnowledgeBaseCreate, KnowledgeBaseOut
from plugins.context import MemoryTrace, PluginContext
from plugins.registry import get_registry
from repositories.knowledge_bases import KnowledgeBaseRepository
from repositories.pipelines import PipelineRepository
from repositories.settings import SettingsRepository
from services.bindings import BindingResolver

logger = logging.getLogger(__name__)


def first_slot_binding_id(pipeline: dict, stage: PipelineStage) -> UUID | None:
    """Read binding_id from the first binding of a pipeline stage slot."""
    for slot in pipeline.get("slots") or []:
        slot_stage = slot.get("stage")
        if str(slot_stage) != stage.value:
            continue
        bindings = slot.get("bindings") or []
        if not bindings:
            continue
        params = bindings[0].get("params") or {}
        raw = params.get("binding_id")
        if raw:
            return UUID(str(raw))
    return None


# Backward-compatible alias for older call sites / tests.
_first_slot_binding_id = first_slot_binding_id


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = KnowledgeBaseRepository(session)
        self._pipelines = PipelineRepository(session)
        self._resolver = BindingResolver(SettingsRepository(session))

    async def list_kbs(self) -> list[KnowledgeBaseOut]:
        return [KnowledgeBaseOut.model_validate(row) for row in await self._repo.list_all()]

    async def get_kb(self, kb_id: UUID) -> KnowledgeBaseOut:
        row = await self._require_kb(kb_id)
        return KnowledgeBaseOut.model_validate(row)

    async def delete_kb(self, kb_id: UUID) -> None:
        """Soft-delete immediately; caller should schedule execute_delete_kb in background."""
        if await self._repo.blocking_reference_count(kb_id) > 0:
            raise HTTPException(
                status_code=409, detail="knowledge base is still referenced"
            )
        if not await self._repo.mark_deleted(kb_id):
            raise HTTPException(status_code=404, detail="knowledge base not found")

    async def execute_delete_kb(self, kb_id: UUID) -> None:
        """Hard-delete rows and unlink uploaded files (background job)."""
        try:
            storage_keys = await self._repo.delete(kb_id)
        except IntegrityError:
            logger.exception("hard delete blocked for knowledge base %s", kb_id)
            return
        if storage_keys is None:
            return
        upload_root = Path(self._settings.upload_dir)
        for key in storage_keys:
            candidate = upload_root / key
            if candidate.is_file():
                candidate.unlink(missing_ok=True)

    async def create_kb(self, payload: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        settings_repo = SettingsRepository(self._session)
        ingest = await self._pipelines.get(payload.ingest_pipeline_id)
        if not ingest or ingest.get("kind") != PipelineKind.INGEST:
            raise HTTPException(status_code=400, detail="ingest pipeline not found")

        embedder_id = _first_slot_binding_id(ingest, PipelineStage.EMBEDDER)
        if embedder_id is None:
            credentials = await settings_repo.list_credentials()
            vectors = [row for row in credentials if row.get("kind") == "vector"]
            if not vectors:
                raise HTTPException(
                    status_code=400,
                    detail="no vector credential; create one in Settings or set "
                    "binding_id on the ingest embedder slot",
                )
            embedder_id = vectors[0]["id"]

        embedder = await settings_repo.get_credential(embedder_id)
        if not embedder or embedder.get("kind") != "vector":
            raise HTTPException(
                status_code=400, detail="embedder credential must be kind=vector"
            )

        row = await self._repo.insert(
            name=payload.name,
            description=payload.description,
            ingest_pipeline_id=payload.ingest_pipeline_id,
            query_pipeline_id=None,
            default_embedder_binding_id=embedder_id,
            default_generator_binding_id=None,
        )
        extra = embedder.get("extra") or {}
        dim = extra.get("dim") if isinstance(extra, dict) else None
        collection = await self._repo.insert_collection(
            knowledge_base_id=row["id"],
            name="default",
            embedder_binding_id=embedder_id,
            dim=int(dim) if dim is not None else None,
        )
        row["collections"] = [collection]
        return KnowledgeBaseOut.model_validate(row)

    async def list_documents(self, kb_id: UUID) -> list[DocumentOut]:
        await self._require_kb(kb_id)
        return [DocumentOut.model_validate(row) for row in await self._repo.list_documents(kb_id)]

    async def delete_document(self, kb_id: UUID, document_id: UUID) -> None:
        await self._require_kb(kb_id)
        try:
            storage_keys = await self._repo.delete_document(kb_id, document_id)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="document is still referenced"
            ) from exc
        if storage_keys is None:
            raise HTTPException(status_code=404, detail="document not found")
        upload_root = Path(self._settings.upload_dir)
        for key in storage_keys:
            candidate = upload_root / key
            if candidate.is_file():
                candidate.unlink(missing_ok=True)

    async def upload_document(self, kb_id: UUID, file: UploadFile) -> DocumentOut:
        await self._require_kb(kb_id)
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="empty file")
        digest = hashlib.sha256(raw).hexdigest()
        filename = file.filename or "upload.bin"
        upload_root = Path(self._settings.upload_dir)
        upload_root.mkdir(parents=True, exist_ok=True)
        storage_key = f"{uuid4()}-{filename}"
        (upload_root / storage_key).write_bytes(raw)
        stored = await self._repo.insert_stored_file(
            original_filename=filename,
            content_type=file.content_type,
            byte_size=len(raw),
            content_hash=digest,
            storage_key=storage_key,
        )
        try:
            document = await self._repo.insert_document(
                knowledge_base_id=kb_id,
                stored_file_id=stored["id"],
                source_uri=filename,
                mime_type=file.content_type,
                title=filename,
                content_hash=digest,
            )
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="a document with this filename already exists"
            ) from exc
        await self._repo.insert_document_version(
            document_id=document["id"],
            version_no=1,
            content_hash=digest,
            raw_text=None,
            byte_size=len(raw),
        )
        await self.ingest_document(kb_id, document["id"])
        refreshed = await self._repo.get_document(document["id"])
        return DocumentOut.model_validate(refreshed or document)

    async def ingest_document(self, kb_id: UUID, document_id: UUID) -> IngestJobOut:
        kb = await self._require_kb(kb_id)
        if not kb.get("ingest_pipeline_id"):
            raise HTTPException(status_code=400, detail="knowledge base has no ingest pipeline")
        if not kb.get("default_embedder_binding_id"):
            raise HTTPException(status_code=400, detail="knowledge base has no vector credential")
        document = await self._repo.get_document(document_id)
        if not document or document["knowledge_base_id"] != kb_id:
            raise HTTPException(status_code=404, detail="document not found")
        version = await self._repo.latest_version(document_id)
        if not version:
            raise HTTPException(status_code=400, detail="document has no version")
        collection_id = default_collection_id(kb)
        if collection_id is None:
            raise HTTPException(status_code=400, detail="knowledge base has no vector collection")
        pipeline = await self._pipelines.get(kb["ingest_pipeline_id"])
        if not pipeline:
            raise HTTPException(status_code=400, detail="ingest pipeline not found")
        job = await self._repo.insert_ingest_job(
            knowledge_base_id=kb_id,
            document_id=document_id,
            document_version_id=version["id"],
            vector_collection_id=collection_id,
            ingest_pipeline_id=pipeline["id"],
        )
        ctx = PluginContext(
            resolver=self._resolver,
            kb_repo=self._repo,
            models=LiteLLMClient(),
            trace=MemoryTrace(),
            default_embedder_binding_id=kb.get("default_embedder_binding_id"),
            default_generator_binding_id=kb.get("default_generator_binding_id"),
        )
        calls = ordered_calls(pipeline["slots"], PipelineKind.INGEST)
        filename = document.get("source_uri") or "document"
        mime_type = document.get("mime_type")
        file_path = None
        stored_file_id = document.get("stored_file_id")
        if stored_file_id:
            stored = await self._repo.get_stored_file(stored_file_id)
            if stored:
                filename = stored.get("original_filename") or filename
                mime_type = mime_type or stored.get("content_type")
                candidate = Path(self._settings.upload_dir) / stored["storage_key"]
                if candidate.is_file():
                    file_path = str(candidate)
        data = {
            "raw_text": version["raw_text"] or "",
            "file_path": file_path,
            "filename": filename,
            "mime_type": mime_type,
            "document_version_id": version["id"],
            "document_id": document_id,
            "knowledge_base_id": kb_id,
            "vector_collection_id": collection_id,
        }
        try:
            result = await run_pipeline(
                calls=calls,
                data=data,
                ctx=ctx,
                registry=get_registry(),
            )
            for span in ctx.trace.spans:
                await self._repo.insert_ingest_trace(
                    ingest_job_id=job["id"],
                    stage=span.stage,
                    plugin_name=span.plugin_name,
                    ordinal=span.ordinal,
                    output_json=span.output,
                    error_message=span.error_message,
                    latency_ms=span.latency_ms,
                )
            extracted = result.get("raw_text")
            if extracted:
                await self._repo.update_version_raw_text(version["id"], extracted)
            await self._repo.set_document_status(document_id, "indexed")
            finished = await self._repo.finish_ingest_job(
                job["id"],
                status="succeeded",
                error_message=None,
                stats={"indexed_count": result.get("indexed_count", 0)},
            )
        except Exception as exc:
            await self._repo.set_document_status(document_id, "failed")
            for span in ctx.trace.spans:
                await self._repo.insert_ingest_trace(
                    ingest_job_id=job["id"],
                    stage=span.stage,
                    plugin_name=span.plugin_name,
                    ordinal=span.ordinal,
                    output_json=span.output,
                    error_message=span.error_message,
                    latency_ms=span.latency_ms,
                )
            finished = await self._repo.finish_ingest_job(
                job["id"],
                status="failed",
                error_message=str(exc),
                stats={},
            )
        return IngestJobOut.model_validate(finished)

    async def _require_kb(self, kb_id: UUID) -> dict:
        row = await self._repo.get(kb_id)
        if not row:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        return row
