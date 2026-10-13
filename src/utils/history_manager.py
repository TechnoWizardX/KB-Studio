from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from src.utils.config_manager import ConfigManager


class HistoryManager:
    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path or (
            ConfigManager.get_config_path().parent / "chat_history.sqlite3"
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return closing(sqlite3.connect(self.database_path, timeout=5))

    def _initialize(self) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_message(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported message role: {role!r}")
        if not isinstance(content, str):
            raise TypeError("Message content must be a string")

        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, created_at),
            )

    def get_messages(self, limit: int | None = None) -> list[dict[str, str]]:
        with self._connect() as connection, connection:
            connection.row_factory = sqlite3.Row
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT role, content, created_at
                    FROM messages
                    ORDER BY id ASC
                    """
                ).fetchall()
            else:
                if isinstance(limit, bool) or not isinstance(limit, int):
                    raise TypeError("Message limit must be an integer or None")
                if limit < 1:
                    raise ValueError("Message limit must be greater than zero")
                rows = connection.execute(
                    """
                    SELECT role, content, created_at
                    FROM (
                        SELECT id, role, content, created_at
                        FROM messages
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    ORDER BY id ASC
                    """,
                    (limit,),
                ).fetchall()

        return [dict(row) for row in rows]
