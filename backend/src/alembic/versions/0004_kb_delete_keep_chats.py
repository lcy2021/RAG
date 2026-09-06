"""Keep chat history when knowledge bases are deleted.

Revision ID: 0004_kb_delete_keep_chats
Revises: 0003_kb_soft_delete
"""

from sqlalchemy import inspect, text

from alembic import op

revision = "0004_kb_delete_keep_chats"
down_revision = "0003_kb_soft_delete"
branch_labels = None
depends_on = None


def _fk_names(insp, table: str, referred: str) -> list[str]:
    if table not in insp.get_table_names():
        return []
    names: list[str] = []
    for fk in insp.get_foreign_keys(table):
        if fk.get("referred_table") == referred:
            name = fk.get("name")
            if name:
                names.append(name)
    return names


def _repoint_fk(
    conn,
    *,
    table: str,
    column: str,
    referred: str,
    constraint_name: str,
    ondelete: str,
    nullable: bool,
) -> None:
    insp = inspect(conn)
    for name in _fk_names(insp, table, referred):
        conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"'))
    null_sql = "" if nullable else " SET NOT NULL"
    if nullable:
        conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL'))
    else:
        conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}"{null_sql}'))
    conn.execute(
        text(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{constraint_name}" '
            f'FOREIGN KEY ("{column}") REFERENCES "{referred}" (id) ON DELETE {ondelete}'
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if "conversations" in insp.get_table_names():
        _repoint_fk(
            conn,
            table="conversations",
            column="knowledge_base_id",
            referred="knowledge_bases",
            constraint_name="conversations_knowledge_base_id_fkey",
            ondelete="SET NULL",
            nullable=True,
        )
    if "rag_runs" in insp.get_table_names():
        _repoint_fk(
            conn,
            table="rag_runs",
            column="knowledge_base_id",
            referred="knowledge_bases",
            constraint_name="rag_runs_knowledge_base_id_fkey",
            ondelete="SET NULL",
            nullable=True,
        )
        _repoint_fk(
            conn,
            table="rag_runs",
            column="vector_collection_id",
            referred="vector_collections",
            constraint_name="rag_runs_vector_collection_id_fkey",
            ondelete="SET NULL",
            nullable=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Cannot restore NOT NULL if orphaned rows exist; only restore RESTRICT-style FKs.
    insp = inspect(conn)
    if "conversations" in insp.get_table_names():
        for name in _fk_names(insp, "conversations", "knowledge_bases"):
            conn.execute(text(f'ALTER TABLE "conversations" DROP CONSTRAINT IF EXISTS "{name}"'))
        conn.execute(
            text(
                'ALTER TABLE "conversations" ADD CONSTRAINT "conversations_knowledge_base_id_fkey" '
                'FOREIGN KEY ("knowledge_base_id") REFERENCES "knowledge_bases" (id)'
            )
        )
    if "rag_runs" in insp.get_table_names():
        for name in _fk_names(insp, "rag_runs", "knowledge_bases"):
            conn.execute(text(f'ALTER TABLE "rag_runs" DROP CONSTRAINT IF EXISTS "{name}"'))
        for name in _fk_names(insp, "rag_runs", "vector_collections"):
            conn.execute(text(f'ALTER TABLE "rag_runs" DROP CONSTRAINT IF EXISTS "{name}"'))
        conn.execute(
            text(
                'ALTER TABLE "rag_runs" ADD CONSTRAINT "rag_runs_knowledge_base_id_fkey" '
                'FOREIGN KEY ("knowledge_base_id") REFERENCES "knowledge_bases" (id)'
            )
        )
        conn.execute(
            text(
                'ALTER TABLE "rag_runs" ADD CONSTRAINT "rag_runs_vector_collection_id_fkey" '
                'FOREIGN KEY ("vector_collection_id") REFERENCES "vector_collections" (id)'
            )
        )
