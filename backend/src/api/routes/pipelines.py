from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import pipeline_service_dep
from models.schemas import PipelineCreate, PipelineOut, PipelineUpdate
from services.pipelines import PipelineService

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

PipelineSvc = Annotated[PipelineService, Depends(pipeline_service_dep)]


@router.get("", response_model=list[PipelineOut])
async def list_pipelines(svc: PipelineSvc) -> list[PipelineOut]:
    return await svc.list_pipelines()


@router.post("", response_model=PipelineOut)
async def create_pipeline(payload: PipelineCreate, svc: PipelineSvc) -> PipelineOut:
    return await svc.create_pipeline(payload)


@router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline(pipeline_id: UUID, svc: PipelineSvc) -> PipelineOut:
    return await svc.get_pipeline(pipeline_id)


@router.put("/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline(
    pipeline_id: UUID, payload: PipelineUpdate, svc: PipelineSvc
) -> PipelineOut:
    return await svc.update_pipeline(pipeline_id, payload)


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: UUID, svc: PipelineSvc) -> None:
    await svc.delete_pipeline(pipeline_id)
