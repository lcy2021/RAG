from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile

from api.deps import SessionDep, kb_service_dep
from jobs.kb_delete import execute_kb_delete_job
from models.schemas import DocumentOut, IngestJobOut, KnowledgeBaseCreate, KnowledgeBaseOut
from services.knowledge_bases import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

KbSvc = Annotated[KnowledgeBaseService, Depends(kb_service_dep)]


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(svc: KbSvc) -> list[KnowledgeBaseOut]:
    return await svc.list_kbs()


@router.post("", response_model=KnowledgeBaseOut)
async def create_knowledge_base(payload: KnowledgeBaseCreate, svc: KbSvc) -> KnowledgeBaseOut:
    return await svc.create_kb(payload)


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: UUID,
    svc: KbSvc,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> None:
    await svc.delete_kb(kb_id)
    await session.commit()
    background_tasks.add_task(execute_kb_delete_job, kb_id)


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(kb_id: UUID, svc: KbSvc) -> KnowledgeBaseOut:
    return await svc.get_kb(kb_id)


@router.get("/{kb_id}/documents", response_model=list[DocumentOut])
async def list_documents(kb_id: UUID, svc: KbSvc) -> list[DocumentOut]:
    return await svc.list_documents(kb_id)


@router.post("/{kb_id}/documents", response_model=DocumentOut)
async def upload_document(kb_id: UUID, file: UploadFile, svc: KbSvc) -> DocumentOut:
    return await svc.upload_document(kb_id, file)


@router.delete("/{kb_id}/documents/{document_id}", status_code=204)
async def delete_document(kb_id: UUID, document_id: UUID, svc: KbSvc) -> None:
    await svc.delete_document(kb_id, document_id)


@router.post("/{kb_id}/documents/{document_id}/ingest", response_model=IngestJobOut)
async def ingest_document(kb_id: UUID, document_id: UUID, svc: KbSvc) -> IngestJobOut:
    return await svc.ingest_document(kb_id, document_id)
