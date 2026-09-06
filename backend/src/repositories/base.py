"""ORM helpers shared by repositories."""

from typing import Any

from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from db.serialize import as_dict


def row_dict(row: Row[Any]) -> dict[str, Any]:
    return dict(row._mapping)


async def persist(session: AsyncSession, instance: Any, **as_dict_kwargs: Any) -> dict[str, Any]:
    session.add(instance)
    await session.flush()
    await session.refresh(instance)
    return as_dict(instance, **as_dict_kwargs)


async def remove_by_pk(session: AsyncSession, model: type[Any], pk: Any) -> bool:
    instance = await session.get(model, pk)
    if instance is None:
        return False
    await session.delete(instance)
    await session.flush()
    return True
