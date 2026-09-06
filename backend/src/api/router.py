from fastapi import APIRouter

from api.routes.chat import router as chat_router
from api.routes.experiments import router as experiments_router
from api.routes.health import router as health_router
from api.routes.import_export import router as import_export_router
from api.routes.knowledge_bases import router as knowledge_bases_router
from api.routes.pipelines import router as pipelines_router
from api.routes.plugins import router as plugins_router
from api.routes.scenarios import router as scenarios_router
from api.routes.settings import router as settings_router
from api.routes.usage import router as usage_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(settings_router)
api_router.include_router(plugins_router)
api_router.include_router(pipelines_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(scenarios_router)
api_router.include_router(experiments_router)
api_router.include_router(chat_router)
api_router.include_router(usage_router)
api_router.include_router(import_export_router)
