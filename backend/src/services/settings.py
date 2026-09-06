"""Credential use cases. Responses never include raw secrets."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infra.secrets import encode_secret, hint_from_secret
from models.enums import CredentialKind
from models.schemas import CredentialCreate, CredentialOut, CredentialUpdate
from repositories.settings import DEFAULT_PLUGIN, SettingsRepository


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SettingsRepository(session)

    async def list_credentials(self) -> list[CredentialOut]:
        return [CredentialOut.model_validate(row) for row in await self._repo.list_credentials()]

    async def get_credential(self, credential_id: UUID) -> CredentialOut:
        row = await self._repo.get_credential(credential_id)
        if row is None:
            raise HTTPException(status_code=404, detail="credential not found")
        return CredentialOut.model_validate(row)

    async def create_credential(self, payload: CredentialCreate) -> CredentialOut:
        stored = encode_secret(payload.secret)
        extra = dict(payload.extra)
        try:
            row = await self._repo.insert_credential(
                name=payload.name,
                kind=payload.kind.value,
                provider=payload.provider,
                plugin_name=DEFAULT_PLUGIN[payload.kind],
                model_name=payload.model_name,
                base_url=payload.base_url,
                encrypted_payload=stored,
                key_hint=hint_from_secret(payload.secret),
                extra=extra,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="credential name already exists") from exc
        return CredentialOut.model_validate(row)

    async def update_credential(
        self, credential_id: UUID, payload: CredentialUpdate
    ) -> CredentialOut:
        secret = (payload.secret or "").strip()
        touch_secret = bool(secret)
        kind_value = payload.kind.value if payload.kind is not None else None
        plugin_name = DEFAULT_PLUGIN[payload.kind] if payload.kind is not None else None
        try:
            row = await self._repo.update_credential(
                credential_id,
                name=payload.name,
                kind=kind_value,
                provider=payload.provider,
                plugin_name=plugin_name,
                model_name=payload.model_name,
                base_url=payload.base_url,
                encrypted_payload=encode_secret(secret) if touch_secret else None,
                key_hint=hint_from_secret(secret) if touch_secret else None,
                extra=dict(payload.extra) if payload.extra is not None else None,
                touch_secret=touch_secret,
                set_base_url="base_url" in payload.model_fields_set,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="credential name already exists") from exc
        if row is None:
            raise HTTPException(status_code=404, detail="credential not found")
        return CredentialOut.model_validate(row)

    async def delete_credential(self, credential_id: UUID) -> None:
        try:
            deleted = await self._repo.delete_credential(credential_id)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="credential is still referenced"
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="credential not found")


def purpose_for_kind(kind: str | CredentialKind) -> str:
    value = kind.value if isinstance(kind, CredentialKind) else kind
    return "embedder" if value == CredentialKind.VECTOR else "generator"
