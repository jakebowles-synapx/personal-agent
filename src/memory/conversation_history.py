"""Short-term conversation history storage with thread support."""

import sqlite3
import logging
import uuid
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Keep last N messages per thread
MAX_HISTORY_MESSAGES = 50
# Expire messages older than this
HISTORY_EXPIRY_HOURS = 168  # 1 week


class ConversationHistory:
    """SQLite-backed conversation history with thread support."""

    def __init__(self, db_path: str = "conversation_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with thread support."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create threads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create messages table with thread_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
            )
        """)

        # Create index for efficient thread message queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_thread
            ON messages(thread_id, created_at DESC)
        """)

        conn.commit()
        conn.close()

    # Thread operations
    def create_thread(self, title: str | None = None) -> dict:
        """Create a new conversation thread."""
        thread_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (thread_id, title, now, now)
        )
        conn.commit()
        conn.close()

        logger.info(f"Created thread {thread_id}")
        return {
            "id": thread_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

    def get_thread(self, thread_id: str) -> dict | None:
        """Get a thread by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, created_at, updated_at FROM threads WHERE id = ?",
            (thread_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        }

    def list_threads(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List all threads, sorted by updated_at descending."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, created_at, updated_at
            FROM threads
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            }
            for row in rows
        ]

    def update_thread(self, thread_id: str, title: str) -> dict | None:
        """Update a thread's title."""
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE threads SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, thread_id)
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if not updated:
            return None

        return self.get_thread(thread_id)

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and all its messages."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete messages first (for databases without CASCADE support)
        cursor.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        cursor.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            logger.info(f"Deleted thread {thread_id}")
        return deleted

    def _touch_thread(self, cursor: sqlite3.Cursor, thread_id: str) -> None:
        """Update thread's updated_at timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?",
            (now, thread_id)
        )

    # Message operations
    def add_message(self, thread_id: str, role: str, content: str) -> dict:
        """Add a message to a thread."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, now)
        )
        message_id = cursor.lastrowid

        # Update thread's updated_at
        self._touch_thread(cursor, thread_id)

        conn.commit()
        conn.close()

        return {
            "id": message_id,
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "created_at": now,
        }

    def add_exchange(self, thread_id: str, user_message: str, assistant_message: str) -> tuple[dict, dict]:
        """Add a user/assistant exchange to a thread."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()

        # Add user message
        cursor.execute(
            "INSERT INTO messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, "user", user_message, now)
        )
        user_msg_id = cursor.lastrowid

        # Add assistant message
        cursor.execute(
            "INSERT INTO messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, "assistant", assistant_message, now)
        )
        assistant_msg_id = cursor.lastrowid

        # Update thread's updated_at
        self._touch_thread(cursor, thread_id)

        conn.commit()
        conn.close()

        return (
            {"id": user_msg_id, "thread_id": thread_id, "role": "user", "content": user_message, "created_at": now},
            {"id": assistant_msg_id, "thread_id": thread_id, "role": "assistant", "content": assistant_message, "created_at": now},
        )

    def get_thread_messages(self, thread_id: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
        """Get messages for a thread, oldest first."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, role, content, created_at FROM (
                SELECT id, role, content, created_at
                FROM messages
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
        """, (thread_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": row[0], "role": row[1], "content": row[2], "created_at": row[3]}
            for row in rows
        ]

    def get_recent_messages(self, thread_id: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
        """Get recent messages for a thread as role/content dicts (for LLM context)."""
        messages = self.get_thread_messages(thread_id, limit)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def clear_thread_messages(self, thread_id: str) -> None:
        """Clear all messages in a thread."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        conn.commit()
        conn.close()
        logger.info(f"Cleared messages for thread {thread_id}")

    # Auto-title generation helper
    def set_thread_title_if_empty(self, thread_id: str, title: str) -> None:
        """Set thread title only if it's currently empty."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE threads SET title = ? WHERE id = ? AND (title IS NULL OR title = '')",
            (title, thread_id)
        )
        conn.commit()
        conn.close()
