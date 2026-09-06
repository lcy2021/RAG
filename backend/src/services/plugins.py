"""Plugin catalog: process registry plus optional database rows after startup sync."""

from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import PipelineStage
from models.schemas import PluginSummary
from plugins.registry import PluginRegistry, get_registry
from repositories.plugins import PluginRepository


class PluginCatalogService:
    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    def list_from_registry(self) -> list[PluginSummary]:
        return [
            PluginSummary(
                stage=plugin.stage,
                name=plugin.name,
                version=plugin.version,
                description=plugin.description,
                source=plugin.source,
                config_schema=plugin.config_schema,
                default_params=plugin.default_params,
            )
            for plugin in self._registry.list_all()
        ]

    async def list_plugins(self, session: AsyncSession | None = None) -> list[PluginSummary]:
        if session is None:
            return self.list_from_registry()
        rows = await PluginRepository(session).list_enabled()
        if not rows:
            return self.list_from_registry()
        return [
            PluginSummary(
                stage=PipelineStage(row["stage"]),
                name=row["name"],
                version=row["version"],
                description=row.get("description") or "",
                source=row["source"],
                config_schema=row["config_schema"] or {},
                default_params=row["default_params"] or {},
                is_enabled=bool(row["is_enabled"]),
            )
            for row in rows
        ]

    async def sync_to_database(self, session: AsyncSession) -> int:
        plugins = self._registry.list_all()
        await PluginRepository(session).upsert_all(plugins)
        return len(plugins)
