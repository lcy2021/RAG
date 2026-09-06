"""Resolve credentials to runtime secrets without putting keys in params."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from infra.secrets import decode_secret
from repositories.settings import SettingsRepository
from services.settings import purpose_for_kind


@dataclass
class ResolvedBinding:
    id: UUID
    name: str
    purpose: str
    plugin_name: str
    model_name: str
    base_url: str | None
    extra: dict[str, Any]
    api_key: str


class BindingResolver:
    """Looks up a credential by id (plugin params still call this binding_id)."""

    def __init__(self, repo: SettingsRepository) -> None:
        self._repo = repo

    async def resolve(self, binding_id: UUID) -> ResolvedBinding:
        credential = await self._repo.get_credential_secret(binding_id)
        if not credential:
            raise ValueError(f"credential not found: {binding_id}")
        api_key = self._read_secret(credential)
        extra = credential.get("extra") or {}
        if not isinstance(extra, dict):
            extra = dict(extra)
        return ResolvedBinding(
            id=credential["id"],
            name=credential["name"],
            purpose=purpose_for_kind(str(credential["kind"])),
            plugin_name=str(credential["plugin_name"]),
            model_name=str(credential["model_name"]),
            base_url=credential.get("base_url"),
            extra=extra,
            api_key=api_key,
        )

    def _read_secret(self, credential: dict[str, Any]) -> str:
        backend = str(credential.get("secret_backend") or "encrypted")
        if backend == "env":
            env_name = credential.get("env_var_name")
            if not env_name:
                raise ValueError("env credential is missing env_var_name")
            value = os.environ.get(env_name)
            if not value:
                raise ValueError(f"environment variable {env_name} is not set")
            return value
        payload = credential.get("encrypted_payload")
        if payload is None:
            raise ValueError("credential secret is empty")
        return decode_secret(bytes(payload))
