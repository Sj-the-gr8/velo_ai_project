from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connection() as connection:
            connection.executescript(schema)
            # Databases created before the action column existed.
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(agent_actions)")}
            if "action" not in columns:
                connection.execute("ALTER TABLE agent_actions ADD COLUMN action TEXT")

    def agent_run_outcome(self, run_id: str) -> str | None:
        """Return the action of a run's final row ("success" or "stopped"), or None if it never finished."""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT action FROM agent_actions WHERE run_id = ? ORDER BY step_number DESC, id DESC LIMIT 1", (run_id,)
            ).fetchone()
        return row["action"] if row and row["action"] in ("success", "stopped") else None

    def mark_cancelled(self, subscription_id: int) -> None:
        """Record a confirmed cancellation: the subscription stops counting as active and its alerts close."""
        with self.connection() as connection:
            connection.execute("UPDATE subscriptions SET status = 'cancelled' WHERE id = ?", (subscription_id,))
            connection.execute("UPDATE alerts SET resolved = 1 WHERE subscription_id = ? AND resolved = 0", (subscription_id,))

    def log_agent_action(self, run_id: str, step_number: int, screenshot_path: str, label: str | None, reasoning: str, action: str | None = None) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO agent_actions (run_id, step_number, screenshot_path, chosen_element_label, action, reasoning_text, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, step_number, screenshot_path, label, action, reasoning, datetime.now(timezone.utc).isoformat()),
            )
