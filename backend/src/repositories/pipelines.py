"""pipeline_configs and pipeline_slots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.entities import PipelineConfig, PipelineSlot
from db.serialize import as_dict
from models.enums import PipelineKind, PipelineStage, SlotMode
from repositories.base import persist, remove_by_pk


def _with_slots(config: PipelineConfig) -> dict[str, Any]:
    data = as_dict(config)
    data["slots"] = [as_dict(slot) for slot in config.slots]
    return data


class PipelineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(PipelineConfig)
            .options(selectinload(PipelineConfig.slots))
            .order_by(PipelineConfig.name)
        )
        return [_with_slots(row) for row in result]

    async def get(self, pipeline_id: UUID) -> dict[str, Any] | None:
        result = await self._session.scalars(
            select(PipelineConfig)
            .options(selectinload(PipelineConfig.slots))
            .where(PipelineConfig.id == pipeline_id)
        )
        row = result.first()
        return _with_slots(row) if row else None

    async def list_slots(self, pipeline_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(PipelineSlot)
            .where(PipelineSlot.pipeline_config_id == pipeline_id)
            .order_by(PipelineSlot.ordinal, PipelineSlot.stage)
        )
        return [as_dict(row) for row in result]

    async def insert(
        self,
        *,
        name: str,
        kind: str,
        description: str | None,
        definition: dict[str, Any],
        slots: list[dict[str, Any]],
    ) -> dict[str, Any]:
        config = PipelineConfig(
            name=name,
            kind=PipelineKind(kind),
            description=description,
            definition=definition,
        )
        await persist(self._session, config)
        await self.replace_slots(config.id, slots)
        loaded = await self.get(config.id)
        assert loaded is not None
        return loaded

    async def replace_slots(self, pipeline_id: UUID, slots: list[dict[str, Any]]) -> None:
        existing = await self._session.scalars(
            select(PipelineSlot).where(PipelineSlot.pipeline_config_id == pipeline_id)
        )
        for slot in existing:
            await self._session.delete(slot)
        await self._session.flush()
        for slot in slots:
            self._session.add(
                PipelineSlot(
                    pipeline_config_id=pipeline_id,
                    stage=PipelineStage(slot["stage"]),
                    mode=SlotMode(slot["mode"]),
                    ordinal=slot["ordinal"],
                    bindings=slot["bindings"],
                )
            )
        await self._session.flush()

    async def update(
        self,
        pipeline_id: UUID,
        *,
        name: str,
        description: str | None,
        definition: dict[str, Any],
        slots: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        result = await self._session.scalars(
            select(PipelineConfig).where(PipelineConfig.id == pipeline_id)
        )
        config = result.first()
        if config is None:
            return None
        config.name = name
        config.description = description
        config.definition = definition
        config.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self.replace_slots(pipeline_id, slots)
        loaded = await self.get(pipeline_id)
        assert loaded is not None
        return loaded

    async def delete(self, pipeline_id: UUID) -> bool:
        return await remove_by_pk(self._session, PipelineConfig, pipeline_id)
