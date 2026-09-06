"""Unit tests for automatic CREATE DATABASE before migrations."""

from unittest.mock import MagicMock, patch

from db.migrate import ensure_database


def test_ensure_database_skips_when_missing_db_name() -> None:
    assert ensure_database("postgresql+asyncpg://postgres:postgres@localhost:5433") is False


def test_ensure_database_skips_when_already_exists() -> None:
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (1,)

    with patch("db.migrate.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = mock_conn
        created = ensure_database(
            "postgresql+asyncpg://postgres:postgres@localhost:5433/raglab"
        )

    assert created is False
    mock_cur.execute.assert_called_once()
    assert "pg_database" in mock_cur.execute.call_args.args[0]


def test_ensure_database_creates_when_missing() -> None:
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    with patch("db.migrate.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = mock_conn
        created = ensure_database(
            "postgresql+asyncpg://postgres:postgres@localhost:5433/raglab"
        )

    assert created is True
    assert mock_cur.execute.call_count == 2
