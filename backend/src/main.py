"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from configs.settings import get_settings
from db.migrate import upgrade_head
from db.session import get_sessionmaker
from plugins.builtin import register_builtin
from plugins.loader import load_plugin_file
from plugins.registry import get_registry
from services.plugins import PluginCatalogService


def _ensure_builtin_plugins() -> None:
    registry = get_registry()
    if not registry.list_all():
        register_builtin(registry)


def _load_custom_plugins() -> None:
    directory = Path(get_settings().custom_plugin_dir)
    if not directory.is_dir():
        return
    registry = get_registry()
    for path in sorted(directory.glob("*.py")):
        load_plugin_file(path, registry)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _ensure_builtin_plugins()
    _load_custom_plugins()
    settings = get_settings()
    if settings.database_enabled:
        await asyncio.to_thread(upgrade_head)
        async with get_sessionmaker()() as session:
            await PluginCatalogService().sync_to_database(session)
            await session.commit()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    _ensure_builtin_plugins()
    app = FastAPI(
        title="RAG Lab API",
        version="0.1.0",
        description="Plugin-based RAG laboratory. UI is the primary config surface.",
        lifespan=lifespan,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("main:app", host="0.0.0.0", port=6660, reload=True)
