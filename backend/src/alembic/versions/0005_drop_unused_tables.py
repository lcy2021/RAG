"""Drop unused reserved tables and rag_runs.compare_group_id.

Revision ID: 0005_drop_unused_tables
Revises: 0004_kb_delete_keep_chats
"""

from sqlalchemy import inspect, text

from alembic import op

revision = "0005_drop_unused_tables"
down_revision = "0004_kb_delete_keep_chats"
branch_labels = None
depends_on = None


def _drop_fks_to(conn, table: str, referred: str) -> None:
    insp = inspect(conn)
    if table not in insp.get_table_names():
        return
    for fk in insp.get_foreign_keys(table):
        if fk.get("referred_table") != referred:
            continue
        name = fk.get("name")
        if name:
            conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"'))


def _drop_column_fks(conn, table: str, column: str) -> None:
    insp = inspect(conn)
    if table not in insp.get_table_names():
        return
    for fk in insp.get_foreign_keys(table):
        if column not in (fk.get("constrained_columns") or []):
            continue
        name = fk.get("name")
        if name:
            conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"'))


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    tables = set(insp.get_table_names())

    # Break circular FKs between compare_groups and rag_runs, then drop both sides.
    if "rag_runs" in tables:
        _drop_column_fks(conn, "rag_runs", "compare_group_id")
    if "compare_groups" in tables:
        _drop_fks_to(conn, "compare_groups", "rag_runs")
        conn.execute(text('DROP TABLE IF EXISTS "compare_groups" CASCADE'))
    if "rag_runs" in tables:
        cols = {c["name"] for c in inspect(conn).get_columns("rag_runs")}
        if "compare_group_id" in cols:
            conn.execute(text('ALTER TABLE "rag_runs" DROP COLUMN IF EXISTS "compare_group_id"'))

    for table in (
        "conversation_memories",
        "message_embeddings",
        "sparse_index_refs",
    ):
        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS "sparse_index_refs" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                knowledge_base_id UUID NOT NULL
                    REFERENCES "knowledge_bases" (id) ON DELETE CASCADE,
                indexer_plugin TEXT NOT NULL,
                collection_name TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                CONSTRAINT uq_sparse_index_refs
                    UNIQUE (knowledge_base_id, indexer_plugin, collection_name)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS "conversation_memories" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL
                    REFERENCES "conversations" (id) ON DELETE CASCADE,
                summary TEXT NOT NULL,
                valid_from_turn INTEGER NOT NULL,
                source_message_id UUID
                    REFERENCES "messages" (id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS conversation_memories_latest_idx "
            'ON "conversation_memories" (conversation_id, valid_from_turn)'
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS "message_embeddings" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                message_id UUID NOT NULL
                    REFERENCES "messages" (id) ON DELETE CASCADE,
                embedder_plugin TEXT NOT NULL,
                embedding vector NOT NULL,
                dim INTEGER NOT NULL,
                CONSTRAINT uq_message_embeddings UNIQUE (message_id, embedder_plugin),
                CONSTRAINT message_embeddings_dim CHECK (vector_dims(embedding) = dim)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS "compare_groups" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                compare_spec_id UUID NOT NULL REFERENCES "compare_specs" (id),
                conversation_id UUID NOT NULL
                    REFERENCES "conversations" (id) ON DELETE CASCADE,
                trigger_message_id UUID NOT NULL
                    REFERENCES "messages" (id) ON DELETE CASCADE,
                label TEXT,
                selected_run_id UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )

    insp = inspect(conn)
    if "rag_runs" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("rag_runs")}
        if "compare_group_id" not in cols:
            conn.execute(text('ALTER TABLE "rag_runs" ADD COLUMN "compare_group_id" UUID'))
        _drop_column_fks(conn, "rag_runs", "compare_group_id")
        conn.execute(
            text(
                'ALTER TABLE "rag_runs" ADD CONSTRAINT "rag_runs_compare_group_id_fkey" '
                'FOREIGN KEY ("compare_group_id") REFERENCES "compare_groups" (id) '
                "ON DELETE SET NULL"
            )
        )

    _drop_fks_to(conn, "compare_groups", "rag_runs")
    conn.execute(
        text(
            'ALTER TABLE "compare_groups" ADD CONSTRAINT "compare_groups_selected_run_fk" '
            'FOREIGN KEY ("selected_run_id") REFERENCES "rag_runs" (id) ON DELETE SET NULL'
        )
    )
