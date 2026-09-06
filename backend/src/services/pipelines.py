"""Pipeline recipe CRUD and slot validation against the in-process registry."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import PipelineKind
from models.schemas import PipelineCreate, PipelineOut, PipelineSlotIn, PipelineUpdate
from plugins.registry import PluginRegistry, get_registry
from repositories.pipelines import PipelineRepository


class PipelineService:
    def __init__(self, session: AsyncSession, registry: PluginRegistry | None = None) -> None:
        self._repo = PipelineRepository(session)
        self._registry = registry or get_registry()

    async def list_pipelines(self) -> list[PipelineOut]:
        return [PipelineOut.model_validate(row) for row in await self._repo.list_all()]

    async def get_pipeline(self, pipeline_id: UUID) -> PipelineOut:
        row = await self._repo.get(pipeline_id)
        if not row:
            raise HTTPException(status_code=404, detail="pipeline not found")
        return PipelineOut.model_validate(row)

    @staticmethod
    def _slot_rows(slots: list[PipelineSlotIn]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, slot in enumerate(slots):
            rows.append(
                {
                    "stage": slot.stage.value,
                    "mode": slot.mode.value,
                    "ordinal": slot.ordinal if slot.ordinal is not None else index,
                    "bindings": [item.model_dump() for item in slot.bindings],
                }
            )
        return rows

    async def create_pipeline(self, payload: PipelineCreate) -> PipelineOut:
        self._validate_slots(payload.kind, payload.slots)
        try:
            row = await self._repo.insert(
                name=payload.name,
                kind=payload.kind.value,
                description=payload.description,
                definition=payload.definition,
                slots=self._slot_rows(payload.slots),
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="pipeline name already exists") from exc
        return PipelineOut.model_validate(row)

    async def update_pipeline(self, pipeline_id: UUID, payload: PipelineUpdate) -> PipelineOut:
        existing = await self._repo.get(pipeline_id)
        if not existing:
            raise HTTPException(status_code=404, detail="pipeline not found")
        kind = PipelineKind(existing["kind"])
        self._validate_slots(kind, payload.slots)
        try:
            row = await self._repo.update(
                pipeline_id,
                name=payload.name,
                description=payload.description,
                definition=payload.definition,
                slots=self._slot_rows(payload.slots),
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="pipeline name already exists") from exc
        assert row is not None
        return PipelineOut.model_validate(row)

    async def delete_pipeline(self, pipeline_id: UUID) -> None:
        try:
            deleted = await self._repo.delete(pipeline_id)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="pipeline is still referenced") from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="pipeline not found")

    def _validate_slots(self, kind: PipelineKind, slots: list[PipelineSlotIn]) -> None:
        ingest_stages = {"loader", "chunker", "embedder", "indexer"}
        query_stages = {
            "query_transformer",
            "retriever",
            "fusion",
            "reranker",
            "grader",
            "compressor",
            "generator",
        }
        allowed = ingest_stages if kind == PipelineKind.INGEST else query_stages
        for slot in slots:
            if slot.stage.value not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"stage {slot.stage} is not valid on a {kind} pipeline",
                )
            for binding in slot.bindings:
                plugin = self._registry.get(slot.stage, binding.name)
                if plugin is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"unknown plugin {slot.stage}/{binding.name}",
                    )
