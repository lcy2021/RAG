"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings, get_settings
from db.session import get_optional_session, get_session
from plugins.registry import PluginRegistry, get_registry
from services.chat import ChatService
from services.experiments import ExperimentService
from services.knowledge_bases import KnowledgeBaseService
from services.pipelines import PipelineService
from services.plugins import PluginCatalogService
from services.scenarios import ScenarioService
from services.settings import SettingsService
from services.usage import UsageService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
OptionalSessionDep = Annotated[AsyncSession | None, Depends(get_optional_session)]


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def registry_dep() -> PluginRegistry:
    return get_registry()


def plugin_catalog_dep() -> PluginCatalogService:
    return PluginCatalogService()


def settings_service_dep(session: SessionDep) -> SettingsService:
    return SettingsService(session)


def pipeline_service_dep(session: SessionDep) -> PipelineService:
    return PipelineService(session)


def kb_service_dep(session: SessionDep, settings: SettingsDep) -> KnowledgeBaseService:
    return KnowledgeBaseService(session, settings)


def chat_service_dep(session: SessionDep, settings: SettingsDep) -> ChatService:
    return ChatService(session, settings)


def scenario_service_dep(session: SessionDep) -> ScenarioService:
    return ScenarioService(session)


def experiment_service_dep(session: SessionDep, settings: SettingsDep) -> ExperimentService:
    return ExperimentService(session, settings)


def usage_service_dep(session: SessionDep) -> UsageService:
    return UsageService(session)
