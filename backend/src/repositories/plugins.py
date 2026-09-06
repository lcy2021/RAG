"""plugins catalog persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.entities import PluginRow
from db.serialize import as_dict
from plugins.define import StagePlugin


class PluginRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_all(self, plugins: list[StagePlugin]) -> None:
        for plugin in plugins:
            stmt = insert(PluginRow).values(
                stage=plugin.stage,
                name=plugin.name,
                version=plugin.version,
                description=plugin.description,
                config_schema=plugin.config_schema,
                default_params=plugin.default_params,
                source=plugin.source,
                origin_path=plugin.origin_path,
                is_enabled=True,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_plugins_stage_name_version",
                set_={
                    "description": stmt.excluded.description,
                    "config_schema": stmt.excluded.config_schema,
                    "default_params": stmt.excluded.default_params,
                    "source": stmt.excluded.source,
                    "origin_path": stmt.excluded.origin_path,
                    "is_enabled": True,
                },
            )
            await self._session.execute(stmt)

    async def disable_absent(self, present: set[tuple[str, str]]) -> None:
        """Disable catalog rows whose (stage, name) are no longer registered."""
        if not present:
            await self._session.execute(update(PluginRow).values(is_enabled=False))
            return
        pairs = list(present)
        await self._session.execute(
            update(PluginRow)
            .where(tuple_(PluginRow.stage, PluginRow.name).notin_(pairs))
            .values(is_enabled=False)
        )

    async def list_enabled(self) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(PluginRow)
            .where(PluginRow.is_enabled.is_(True))
            .order_by(PluginRow.stage, PluginRow.name, PluginRow.version)
        )
        return [as_dict(row) for row in result]
