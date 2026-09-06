"""Dump mapped instances to dicts (enum → value) for existing services."""

from enum import Enum
from typing import Any

from sqlalchemy import inspect

_RENAME = {"extra_metadata": "metadata"}


def as_dict(
    instance: Any,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    mapper = inspect(instance).mapper
    data: dict[str, Any] = {}
    for attr in mapper.column_attrs:
        key = attr.key
        if include is not None and key not in include:
            continue
        if exclude is not None and key in exclude:
            continue
        value = getattr(instance, key)
        if isinstance(value, Enum):
            value = value.value
        data[_RENAME.get(key, key)] = value
    return data
