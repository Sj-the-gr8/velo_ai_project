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

    def log_agent_action(self, run_id: str, step_number: int, screenshot_path: str, label: str | None, reasoning: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO agent_actions (run_id, step_number, screenshot_path, chosen_element_label, reasoning_text, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, step_number, screenshot_path, label, reasoning, datetime.now(timezone.utc).isoformat()),
            )
