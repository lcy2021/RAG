from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import usage_service_dep
from models.schemas import ConversationUsageOut, ExperimentUsageOut, UsageSummaryOut
from services.usage import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])

UsageSvc = Annotated[UsageService, Depends(usage_service_dep)]


@router.get("/summary", response_model=UsageSummaryOut)
async def usage_summary(svc: UsageSvc) -> UsageSummaryOut:
    return await svc.summary()


@router.get("/conversations", response_model=list[ConversationUsageOut])
async def usage_conversations(svc: UsageSvc) -> list[ConversationUsageOut]:
    return await svc.list_conversations()


@router.get("/experiments", response_model=list[ExperimentUsageOut])
async def usage_experiments(svc: UsageSvc) -> list[ExperimentUsageOut]:
    return await svc.list_experiments()
