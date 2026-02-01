"""Database module with SQLite schema for agents, recommendations, and knowledge."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(settings.data_dir, "agent_system.db")


def get_db_path() -> str:
    """Get the database path."""
    return DB_PATH


@contextmanager
def get_connection():
    """Get a database connection with context management."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database with required tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Agent activity log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                summary TEXT,
                items_processed INTEGER DEFAULT 0,
                error_message TEXT
            )
        """)

        # Recommendations from agents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                viewed_at TEXT,
                acted_at TEXT,
                metadata TEXT
            )
        """)

        # Fixed knowledge items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                embedding_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name
            ON agent_runs(agent_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at
            ON agent_runs(started_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recommendations_status
            ON recommendations(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recommendations_agent
            ON recommendations(agent_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_category
            ON knowledge(category)
        """)

        logger.info("Database initialized successfully")


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert a sqlite3.Row to a dictionary."""
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert a list of sqlite3.Row to a list of dictionaries."""
    return [dict(row) for row in rows]


# Agent Runs CRUD
class AgentRunsDB:
    """Database operations for agent runs."""

    @staticmethod
    def create(agent_name: str, status: str = "running") -> int:
        """Create a new agent run record. Returns the run ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_runs (agent_name, started_at, status)
                VALUES (?, ?, ?)
                """,
                (agent_name, _now_iso(), status)
            )
            return cursor.lastrowid

    @staticmethod
    def complete(
        run_id: int,
        status: str = "completed",
        summary: str | None = None,
        items_processed: int = 0,
        error_message: str | None = None
    ) -> None:
        """Mark an agent run as completed."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE agent_runs
                SET completed_at = ?, status = ?, summary = ?,
                    items_processed = ?, error_message = ?
                WHERE id = ?
                """,
                (_now_iso(), status, summary, items_processed, error_message, run_id)
            )

    @staticmethod
    def get(run_id: int) -> dict | None:
        """Get an agent run by ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
            return _row_to_dict(cursor.fetchone())

    @staticmethod
    def list_recent(
        agent_name: str | None = None,
        limit: int = 50,
        hours: int = 24
    ) -> list[dict]:
        """List recent agent runs."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        with get_connection() as conn:
            cursor = conn.cursor()
            if agent_name:
                cursor.execute(
                    """
                    SELECT * FROM agent_runs
                    WHERE agent_name = ? AND started_at > ?
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (agent_name, cutoff, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM agent_runs
                    WHERE started_at > ?
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (cutoff, limit)
                )
            return _rows_to_list(cursor.fetchall())

    @staticmethod
    def get_last_run(agent_name: str) -> dict | None:
        """Get the most recent run for an agent."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM agent_runs
                WHERE agent_name = ?
                ORDER BY started_at DESC LIMIT 1
                """,
                (agent_name,)
            )
            return _row_to_dict(cursor.fetchone())


# Recommendations CRUD
class RecommendationsDB:
    """Database operations for recommendations."""

    @staticmethod
    def create(
        agent_name: str,
        title: str,
        content: str,
        priority: str = "normal",
        metadata: dict | None = None
    ) -> int:
        """Create a new recommendation. Returns the recommendation ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO recommendations
                (agent_name, title, content, priority, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_name,
                    title,
                    content,
                    priority,
                    _now_iso(),
                    json.dumps(metadata) if metadata else None
                )
            )
            return cursor.lastrowid

    @staticmethod
    def get(recommendation_id: int) -> dict | None:
        """Get a recommendation by ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM recommendations WHERE id = ?",
                (recommendation_id,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get("metadata"):
                    result["metadata"] = json.loads(result["metadata"])
                return result
            return None

    @staticmethod
    def update_status(
        recommendation_id: int,
        status: str
    ) -> bool:
        """Update recommendation status."""
        timestamp_field = None
        if status == "viewed":
            timestamp_field = "viewed_at"
        elif status in ("actioned", "dismissed"):
            timestamp_field = "acted_at"

        with get_connection() as conn:
            cursor = conn.cursor()
            if timestamp_field:
                cursor.execute(
                    f"""
                    UPDATE recommendations
                    SET status = ?, {timestamp_field} = ?
                    WHERE id = ?
                    """,
                    (status, _now_iso(), recommendation_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE recommendations SET status = ? WHERE id = ?
                    """,
                    (status, recommendation_id)
                )
            return cursor.rowcount > 0

    @staticmethod
    def list(
        agent_name: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """List recommendations with optional filters."""
        conditions = []
        params = []

        if agent_name:
            conditions.append("agent_name = ?")
            params.append(agent_name)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM recommendations
                WHERE {where_clause}
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                result = dict(row)
                if result.get("metadata"):
                    result["metadata"] = json.loads(result["metadata"])
                results.append(result)
            return results

    @staticmethod
    def count_pending() -> int:
        """Count pending recommendations."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM recommendations WHERE status = 'pending'"
            )
            return cursor.fetchone()[0]

    @staticmethod
    def delete(recommendation_id: int) -> bool:
        """Delete a recommendation."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM recommendations WHERE id = ?",
                (recommendation_id,)
            )
            return cursor.rowcount > 0


# Knowledge CRUD
class KnowledgeDB:
    """Database operations for knowledge items."""

    VALID_CATEGORIES = ["strategy", "team", "processes", "clients", "projects"]

    @staticmethod
    def create(
        category: str,
        title: str,
        content: str,
        source: str | None = None,
        embedding_id: str | None = None
    ) -> int:
        """Create a new knowledge item. Returns the knowledge ID."""
        if category not in KnowledgeDB.VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {KnowledgeDB.VALID_CATEGORIES}")

        now = _now_iso()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO knowledge
                (category, title, content, source, embedding_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (category, title, content, source, embedding_id, now, now)
            )
            return cursor.lastrowid

    @staticmethod
    def get(knowledge_id: int) -> dict | None:
        """Get a knowledge item by ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,))
            return _row_to_dict(cursor.fetchone())

    @staticmethod
    def update(
        knowledge_id: int,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        embedding_id: str | None = None
    ) -> bool:
        """Update a knowledge item."""
        if category and category not in KnowledgeDB.VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")

        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if embedding_id is not None:
            updates.append("embedding_id = ?")
            params.append(embedding_id)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(_now_iso())
        params.append(knowledge_id)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE knowledge SET {', '.join(updates)} WHERE id = ?",
                params
            )
            return cursor.rowcount > 0

    @staticmethod
    def delete(knowledge_id: int) -> bool:
        """Delete a knowledge item."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))
            return cursor.rowcount > 0

    @staticmethod
    def list(
        category: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """List knowledge items with optional category filter."""
        with get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    """
                    SELECT * FROM knowledge
                    WHERE category = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (category, limit, offset)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM knowledge
                    ORDER BY category, updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                )
            return _rows_to_list(cursor.fetchall())

    @staticmethod
    def count_by_category() -> dict[str, int]:
        """Get count of knowledge items by category."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM knowledge
                GROUP BY category
                """
            )
            return {row["category"]: row["count"] for row in cursor.fetchall()}

    @staticmethod
    def search_by_title(query: str, limit: int = 10) -> list[dict]:
        """Search knowledge items by title."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM knowledge
                WHERE title LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (f"%{query}%", limit)
            )
            return _rows_to_list(cursor.fetchall())
