"""Credential secret helpers. Payloads are stored as UTF-8 bytes (lab local use)."""


def hint_from_secret(secret: str) -> str:
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"...{tail}"


def encode_secret(secret: str) -> bytes:
    """Store the pasted secret as UTF-8 bytes (no at-rest encryption)."""
    return secret.encode("utf-8")


def decode_secret(payload: bytes) -> str:
    """Read a UTF-8 secret payload written by encode_secret."""
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("credential payload could not be decoded") from exc
