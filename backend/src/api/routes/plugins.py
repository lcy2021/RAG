from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import OptionalSessionDep, plugin_catalog_dep
from models.schemas import PluginSummary
from services.plugins import PluginCatalogService

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("", response_model=list[PluginSummary])
async def list_plugins(
    session: OptionalSessionDep,
    catalog: Annotated[PluginCatalogService, Depends(plugin_catalog_dep)],
) -> list[PluginSummary]:
    return await catalog.list_plugins(session)
