from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import settings_service_dep
from models.schemas import CredentialCreate, CredentialOut
from services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

SettingsSvc = Annotated[SettingsService, Depends(settings_service_dep)]


@router.get("/credentials", response_model=list[CredentialOut])
async def list_credentials(svc: SettingsSvc) -> list[CredentialOut]:
    return await svc.list_credentials()


@router.post("/credentials", response_model=CredentialOut)
async def create_credential(payload: CredentialCreate, svc: SettingsSvc) -> CredentialOut:
    return await svc.create_credential(payload)


@router.delete("/credentials/{credential_id}", status_code=204)
async def delete_credential(credential_id: UUID, svc: SettingsSvc) -> None:
    await svc.delete_credential(credential_id)
