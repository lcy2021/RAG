"""Usage reporting for chat and experiment RAG runs."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import (
    ConversationUsageOut,
    ExperimentUsageOut,
    UsageBucketOut,
    UsageSummaryOut,
)
from repositories.usage import UsageRepository


class UsageService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UsageRepository(session)

    async def summary(self) -> UsageSummaryOut:
        data = await self._repo.summary()
        return UsageSummaryOut(
            total=UsageBucketOut.model_validate(data["total"]),
            chat=UsageBucketOut.model_validate(data["chat"]),
            experiment=UsageBucketOut.model_validate(data["experiment"]),
        )

    async def list_conversations(self) -> list[ConversationUsageOut]:
        rows = await self._repo.list_conversations()
        return [ConversationUsageOut.model_validate(row) for row in rows]

    async def list_experiments(self) -> list[ExperimentUsageOut]:
        rows = await self._repo.list_experiments()
        return [ExperimentUsageOut.model_validate(row) for row in rows]
