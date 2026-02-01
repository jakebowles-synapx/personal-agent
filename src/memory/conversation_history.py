"""Short-term conversation history storage."""

import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Keep last N messages per user
MAX_HISTORY_MESSAGES = 20
# Expire messages older than this
HISTORY_EXPIRY_HOURS = 24


class ConversationHistory:
    """SQLite-backed short-term conversation history."""

    def __init__(self, db_path: str = "conversation_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_user_id
            ON messages(user_id, created_at DESC)
        """)
        conn.commit()
        conn.close()

    def add_message(self, user_id: str, role: str, content: str) -> None:
        """Add a message to the history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, now)
        )
        conn.commit()

        # Prune old messages for this user
        self._prune_messages(cursor, user_id)
        conn.commit()
        conn.close()

    def add_exchange(self, user_id: str, user_message: str, assistant_message: str) -> None:
        """Add a user/assistant exchange to history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, "user", user_message, now)
        )
        cursor.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, "assistant", assistant_message, now)
        )
        conn.commit()

        # Prune old messages
        self._prune_messages(cursor, user_id)
        conn.commit()
        conn.close()

    def get_recent_messages(self, user_id: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
        """Get recent messages for a user, oldest first."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get messages within expiry window
        expiry_cutoff = (datetime.now(timezone.utc) - timedelta(hours=HISTORY_EXPIRY_HOURS)).isoformat()

        cursor.execute("""
            SELECT role, content FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE user_id = ? AND created_at > ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
        """, (user_id, expiry_cutoff, limit))

        rows = cursor.fetchall()
        conn.close()

        return [{"role": row[0], "content": row[1]} for row in rows]

    def _prune_messages(self, cursor: sqlite3.Cursor, user_id: str) -> None:
        """Remove old messages beyond the limit."""
        # Delete messages beyond the limit
        cursor.execute("""
            DELETE FROM messages
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            )
        """, (user_id, user_id, MAX_HISTORY_MESSAGES))

        # Delete expired messages
        expiry_cutoff = (datetime.now(timezone.utc) - timedelta(hours=HISTORY_EXPIRY_HOURS)).isoformat()
        cursor.execute(
            "DELETE FROM messages WHERE created_at < ?",
            (expiry_cutoff,)
        )

    def clear_history(self, user_id: str) -> None:
        """Clear all history for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Cleared conversation history for user {user_id}")
