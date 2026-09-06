from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from sqlalchemy import select

from configs.settings import get_settings
from db.session import get_sessionmaker
from models.schemas import HealthResponse

router = APIRouter(tags=["health"])

try:
    __version__ = version("raglab")
except PackageNotFoundError:
    __version__ = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    db_status = "skipped"
    if settings.database_enabled:
        try:
            async with get_sessionmaker()() as session:
                await session.scalar(select(1))
            db_status = "ok"
        except Exception:
            db_status = "error"
    return HealthResponse(status="ok", version=__version__, database=db_status)
