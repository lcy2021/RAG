"""Initial schema from ORM metadata (EF Core first migration analogue)."""

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    from db import entities as _entities  # noqa: F401
    from db.base import Base

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from alembic import op

    from db import entities as _entities  # noqa: F401
    from db.base import Base

    Base.metadata.drop_all(bind=op.get_bind())
