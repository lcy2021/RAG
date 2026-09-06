"""PostgreSQL enum columns. Values match schema type names."""

from enum import Enum

from sqlalchemy import Enum as SAEnum

_CACHE: dict[str, SAEnum] = {}


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Reuse one SQLAlchemy Enum per PG type (like a shared EF Core value converter)."""
    cached = _CACHE.get(name)
    if cached is not None:
        return cached
    mapped = SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        create_constraint=False,
        values_callable=lambda cls: [item.value for item in cls],
    )
    _CACHE[name] = mapped
    return mapped
