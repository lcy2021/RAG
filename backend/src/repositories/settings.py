"""Credential rows. API dicts never include the secret payload."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.entities import Credential
from db.serialize import as_dict
from models.enums import CredentialKind, SecretBackend
from repositories.base import persist, remove_by_pk

_CREDENTIAL_SECRET = {"encrypted_payload"}

DEFAULT_PLUGIN = {
    CredentialKind.VECTOR: "openai_embedder",
    CredentialKind.LLM: "chat",
}


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_credentials(self) -> list[dict[str, Any]]:
        result = await self._session.scalars(select(Credential).order_by(Credential.name))
        return [as_dict(row, exclude=_CREDENTIAL_SECRET) for row in result]

    async def get_credential(self, credential_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(Credential, credential_id)
        return as_dict(row, exclude=_CREDENTIAL_SECRET) if row else None

    async def get_credential_secret(self, credential_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(Credential, credential_id)
        return as_dict(row) if row else None

    async def insert_credential(
        self,
        *,
        name: str,
        kind: str,
        provider: str,
        plugin_name: str,
        model_name: str,
        base_url: str | None,
        encrypted_payload: bytes,
        key_hint: str | None,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            Credential(
                name=name,
                kind=CredentialKind(kind),
                provider=provider,
                plugin_name=plugin_name,
                model_name=model_name,
                base_url=base_url,
                secret_backend=SecretBackend.ENCRYPTED,
                env_var_name=None,
                encrypted_payload=encrypted_payload,
                key_hint=key_hint,
                extra=extra,
            ),
            exclude=_CREDENTIAL_SECRET,
        )

    async def delete_credential(self, credential_id: UUID) -> bool:
        return await remove_by_pk(self._session, Credential, credential_id)
