import sqlite3

from db.db import Database


def test_schema_migration_creates_required_tables(tmp_path):
    path = tmp_path / "velo.db"
    Database(path).migrate()
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"subscriptions", "billing_events", "alerts", "agent_actions"} <= tables
