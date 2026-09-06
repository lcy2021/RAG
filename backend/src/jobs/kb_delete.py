"""Background jobs for knowledge-base hard deletion."""

from __future__ import annotations

import logging
from uuid import UUID

from configs.settings import get_settings
from db.session import get_sessionmaker
from services.knowledge_bases import KnowledgeBaseService

logger = logging.getLogger(__name__)


async def execute_kb_delete_job(kb_id: UUID) -> None:
    """Hard-delete a soft-deleted knowledge base in its own DB session."""
    settings = get_settings()
    factory = get_sessionmaker()
    async with factory() as session:
        service = KnowledgeBaseService(session, settings)
        try:
            await service.execute_delete_kb(kb_id)
            await session.commit()
        except Exception:
            logger.exception("knowledge base delete %s crashed", kb_id)
            await session.rollback()
            raise
