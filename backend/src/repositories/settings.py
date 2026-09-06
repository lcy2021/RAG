"""Credential rows. API dicts never include the secret payload."""

from __future__ import annotations

from datetime import UTC, datetime
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

    async def update_credential(
        self,
        credential_id: UUID,
        *,
        name: str | None = None,
        kind: str | None = None,
        provider: str | None = None,
        plugin_name: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        encrypted_payload: bytes | None = None,
        key_hint: str | None = None,
        extra: dict[str, Any] | None = None,
        touch_secret: bool = False,
        set_base_url: bool = False,
    ) -> dict[str, Any] | None:
        row = await self._session.get(Credential, credential_id)
        if row is None:
            return None
        if name is not None:
            row.name = name
        if kind is not None:
            row.kind = CredentialKind(kind)
        if provider is not None:
            row.provider = provider
        if plugin_name is not None:
            row.plugin_name = plugin_name
        if model_name is not None:
            row.model_name = model_name
        if set_base_url:
            row.base_url = base_url
        if touch_secret:
            row.secret_backend = SecretBackend.ENCRYPTED
            row.env_var_name = None
            row.encrypted_payload = encrypted_payload
            row.key_hint = key_hint
        if extra is not None:
            row.extra = extra
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return as_dict(row, exclude=_CREDENTIAL_SECRET)

    async def delete_credential(self, credential_id: UUID) -> bool:
        return await remove_by_pk(self._session, Credential, credential_id)
