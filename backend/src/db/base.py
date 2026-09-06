"""SQLAlchemy declarative base. Alembic autogenerate uses Base.metadata."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
