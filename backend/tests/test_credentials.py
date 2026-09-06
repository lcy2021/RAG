import pytest
from pydantic import ValidationError

from infra.secrets import decode_secret, encode_secret, hint_from_secret
from models.schemas import CredentialCreate
from services.settings import purpose_for_kind


def test_credential_create_requires_secret() -> None:
    with pytest.raises(ValidationError):
        CredentialCreate(name="v", kind="vector", model_name="m", secret="   ")


def test_credential_create_accepts_vector_and_llm() -> None:
    vector = CredentialCreate(
        name="embed",
        kind="vector",
        model_name="text-embedding-3-small",
        secret="sk-test",
        extra={"dim": 1536},
    )
    llm = CredentialCreate(name="chat", kind="llm", model_name="gpt-4o-mini", secret="sk-test")
    assert vector.kind.value == "vector"
    assert llm.kind.value == "llm"


def test_secret_roundtrip_and_hint() -> None:
    payload = encode_secret("sk-live-abcd")
    assert decode_secret(payload) == "sk-live-abcd"
    assert hint_from_secret("sk-live-abcd") == "...abcd"


def test_purpose_for_kind() -> None:
    assert purpose_for_kind("vector") == "embedder"
    assert purpose_for_kind("llm") == "generator"
