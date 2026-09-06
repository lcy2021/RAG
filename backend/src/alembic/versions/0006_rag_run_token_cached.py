"""Add rag_runs.token_cached for prompt-cache hit tokens.

Revision ID: 0006_rag_run_token_cached
Revises: 0005_drop_unused_tables
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_rag_run_token_cached"
down_revision = "0005_drop_unused_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_runs", sa.Column("token_cached", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("rag_runs", "token_cached")
