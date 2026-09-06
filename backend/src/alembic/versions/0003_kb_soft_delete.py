"""Add knowledge_bases.deleted_at for async KB deletion.

Revision ID: 0003_kb_soft_delete
Revises: 0002_unified_credentials
"""

import sqlalchemy as sa
from sqlalchemy import inspect, text

from alembic import op

revision = "0003_kb_soft_delete"
down_revision = "0002_unified_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    columns = {col["name"] for col in insp.get_columns("knowledge_bases")}
    if "deleted_at" not in columns:
        op.add_column(
            "knowledge_bases",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS knowledge_bases_deleted_at_idx "
            "ON knowledge_bases (deleted_at) WHERE deleted_at IS NULL"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS knowledge_bases_deleted_at_idx"))
    conn = op.get_bind()
    insp = inspect(conn)
    columns = {col["name"] for col in insp.get_columns("knowledge_bases")}
    if "deleted_at" in columns:
        op.drop_column("knowledge_bases", "deleted_at")
