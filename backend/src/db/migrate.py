"""Alembic upgrade (EF Core `Update-Database`). Revisions live in this package."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine.url import make_url

from configs.settings import get_settings

# Maintenance DB used only to CREATE DATABASE when the target DB is missing.
_ADMIN_DATABASE = "postgres"


def package_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def alembic_script_location() -> Path:
    return package_dir() / "alembic"


def alembic_url(database_url: str) -> str:
    url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _psycopg_conninfo(database_url: str, *, database: str | None = None) -> str:
    """Build a libpq URL for psycopg from a SQLAlchemy-style URL."""
    url = make_url(alembic_url(database_url))
    if database is not None:
        url = url.set(database=database)
    return url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )


def ensure_database(database_url: str | None = None) -> bool:
    """Create the target database if it does not exist.

    Connects to the server's ``postgres`` maintenance DB (same host/user/password),
    then runs ``CREATE DATABASE`` when needed. Returns True when a new DB was created.
    """
    target_url = database_url or get_settings().database_url
    parsed = make_url(alembic_url(target_url))
    db_name = parsed.database
    if not db_name or db_name == _ADMIN_DATABASE:
        return False

    conninfo = _psycopg_conninfo(target_url, database=_ADMIN_DATABASE)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone() is not None:
                return False
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    return True


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_script_location()))
    cfg.set_main_option("sqlalchemy.url", alembic_url(get_settings().database_url))
    return cfg


def upgrade_head() -> None:
    """Ensure the database exists, then apply pending migrations (API lifespan / CLI)."""
    ensure_database()
    command.upgrade(alembic_config(), "head")


def main() -> None:
    upgrade_head()


if __name__ == "__main__":
    main()
