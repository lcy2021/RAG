"""Merge model_bindings into credentials (vector | llm, encrypted secret).

Revision ID: 0002_unified_credentials
Revises: 0001_initial
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0002_unified_credentials"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table)}


def _drop_fks_to(conn, table: str, referred: str) -> None:
    rows = conn.execute(
        text(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = :table
              AND ccu.table_name = :referred
            """
        ),
        {"table": table, "referred": referred},
    ).fetchall()
    for row in rows:
        conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{row[0]}"'))


def _add_fk(conn, table: str, name: str, column: str, referred: str = "credentials") -> None:
    conn.execute(
        text(
            f"""
            DO $$ BEGIN
                ALTER TABLE "{table}"
                  ADD CONSTRAINT "{name}"
                  FOREIGN KEY ({column}) REFERENCES {referred}(id);
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    cred_cols = _columns(insp, "credentials")
    if not cred_cols:
        return

    conn.execute(
        text(
            """
            DO $$ BEGIN
                CREATE TYPE credential_kind AS ENUM ('vector', 'llm');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    for stmt in (
        "ALTER TABLE credentials ADD COLUMN IF NOT EXISTS kind credential_kind",
        "ALTER TABLE credentials ADD COLUMN IF NOT EXISTS plugin_name text",
        "ALTER TABLE credentials ADD COLUMN IF NOT EXISTS model_name text",
        "ALTER TABLE credentials ADD COLUMN IF NOT EXISTS base_url text",
        "ALTER TABLE credentials ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb",
    ):
        conn.execute(text(stmt))

    if "model_bindings" in insp.get_table_names():
        conn.execute(
            text(
                """
                INSERT INTO credentials (
                    id, name, kind, provider, plugin_name, model_name, base_url,
                    secret_backend, env_var_name, encrypted_payload, key_hint, extra
                )
                SELECT
                    mb.id,
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM credentials c2
                            WHERE c2.name = mb.name AND c2.id <> mb.id
                        )
                        THEN mb.name || '-' || mb.id::text
                        ELSE mb.name
                    END,
                    CASE
                        WHEN mb.purpose::text = 'embedder' THEN 'vector'::credential_kind
                        ELSE 'llm'::credential_kind
                    END,
                    COALESCE(c.provider, 'openai'),
                    mb.plugin_name,
                    mb.model_name,
                    mb.base_url,
                    COALESCE(c.secret_backend, 'encrypted'::secret_backend),
                    c.env_var_name,
                    c.encrypted_payload,
                    c.key_hint,
                    COALESCE(mb.extra, '{}'::jsonb)
                FROM model_bindings mb
                LEFT JOIN credentials c ON c.id = mb.credential_id
                ON CONFLICT (id) DO UPDATE SET
                    kind = EXCLUDED.kind,
                    plugin_name = EXCLUDED.plugin_name,
                    model_name = EXCLUDED.model_name,
                    base_url = EXCLUDED.base_url,
                    extra = EXCLUDED.extra
                """
            )
        )
        conn.execute(
            text(
                """
                DELETE FROM credentials c
                WHERE NOT EXISTS (SELECT 1 FROM model_bindings mb WHERE mb.id = c.id)
                """
            )
        )
        for table in ("knowledge_bases", "vector_collections", "eval_experiments"):
            if table in insp.get_table_names():
                _drop_fks_to(conn, table, "model_bindings")
        conn.execute(text("DROP TABLE IF EXISTS model_bindings"))

    conn.execute(
        text(
            """
            UPDATE credentials SET
                kind = COALESCE(kind, 'llm'::credential_kind),
                plugin_name = COALESCE(plugin_name, 'chat'),
                model_name = COALESCE(model_name, 'unknown')
            WHERE kind IS NULL OR plugin_name IS NULL OR model_name IS NULL
            """
        )
    )
    conn.execute(text("ALTER TABLE credentials ALTER COLUMN kind SET NOT NULL"))
    conn.execute(text("ALTER TABLE credentials ALTER COLUMN plugin_name SET NOT NULL"))
    conn.execute(text("ALTER TABLE credentials ALTER COLUMN model_name SET NOT NULL"))

    insp = inspect(conn)
    if "knowledge_bases" in insp.get_table_names():
        _drop_fks_to(conn, "knowledge_bases", "credentials")
        _add_fk(
            conn,
            "knowledge_bases",
            "knowledge_bases_embedder_credential_fk",
            "default_embedder_binding_id",
        )
        _add_fk(
            conn,
            "knowledge_bases",
            "knowledge_bases_generator_credential_fk",
            "default_generator_binding_id",
        )
    if "vector_collections" in insp.get_table_names():
        _drop_fks_to(conn, "vector_collections", "credentials")
        _add_fk(
            conn,
            "vector_collections",
            "vector_collections_embedder_credential_fk",
            "embedder_binding_id",
        )
    if "eval_experiments" in insp.get_table_names():
        _drop_fks_to(conn, "eval_experiments", "credentials")
        _add_fk(
            conn,
            "eval_experiments",
            "eval_experiments_judge_credential_fk",
            "judge_binding_id",
        )


def downgrade() -> None:
    pass
