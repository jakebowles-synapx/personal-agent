"""Recommendation store for agent recommendations."""

import logging
from typing import Literal

from src.db import RecommendationsDB

logger = logging.getLogger(__name__)

# Valid priority levels
PRIORITY_LEVELS = ["low", "normal", "high", "urgent"]

# Valid statuses
STATUS_VALUES = ["pending", "viewed", "actioned", "dismissed"]

PriorityType = Literal["low", "normal", "high", "urgent"]
StatusType = Literal["pending", "viewed", "actioned", "dismissed"]


class RecommendationStore:
    """
    Store for agent recommendations.

    Wraps RecommendationsDB with additional business logic and validation.
    """

    @staticmethod
    def create(
        agent_name: str,
        title: str,
        content: str,
        priority: PriorityType = "normal",
        metadata: dict | None = None,
    ) -> int:
        """
        Create a new recommendation.

        Args:
            agent_name: Name of the agent creating the recommendation
            title: Short title
            content: Detailed content
            priority: Priority level (low, normal, high, urgent)
            metadata: Optional metadata dict

        Returns:
            Recommendation ID
        """
        if priority not in PRIORITY_LEVELS:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {PRIORITY_LEVELS}")

        rec_id = RecommendationsDB.create(
            agent_name=agent_name,
            title=title,
            content=content,
            priority=priority,
            metadata=metadata,
        )
        logger.info(f"Created recommendation {rec_id}: {title} (priority: {priority})")
        return rec_id

    @staticmethod
    def get(recommendation_id: int) -> dict | None:
        """Get a recommendation by ID."""
        return RecommendationsDB.get(recommendation_id)

    @staticmethod
    def mark_viewed(recommendation_id: int) -> bool:
        """Mark a recommendation as viewed."""
        return RecommendationsDB.update_status(recommendation_id, "viewed")

    @staticmethod
    def mark_actioned(recommendation_id: int) -> bool:
        """Mark a recommendation as actioned."""
        return RecommendationsDB.update_status(recommendation_id, "actioned")

    @staticmethod
    def dismiss(recommendation_id: int) -> bool:
        """Dismiss a recommendation."""
        return RecommendationsDB.update_status(recommendation_id, "dismissed")

    @staticmethod
    def update_status(recommendation_id: int, status: StatusType) -> bool:
        """
        Update recommendation status.

        Args:
            recommendation_id: ID of the recommendation
            status: New status

        Returns:
            True if updated successfully
        """
        if status not in STATUS_VALUES:
            raise ValueError(f"Invalid status: {status}. Must be one of {STATUS_VALUES}")
        return RecommendationsDB.update_status(recommendation_id, status)

    @staticmethod
    def list_pending(limit: int = 50) -> list[dict]:
        """List pending recommendations."""
        return RecommendationsDB.list(status="pending", limit=limit)

    @staticmethod
    def list_by_agent(agent_name: str, limit: int = 50) -> list[dict]:
        """List recommendations from a specific agent."""
        return RecommendationsDB.list(agent_name=agent_name, limit=limit)

    @staticmethod
    def list_by_priority(priority: PriorityType, limit: int = 50) -> list[dict]:
        """List recommendations by priority."""
        if priority not in PRIORITY_LEVELS:
            raise ValueError(f"Invalid priority: {priority}")
        return RecommendationsDB.list(priority=priority, limit=limit)

    @staticmethod
    def list_all(
        agent_name: str | None = None,
        status: StatusType | None = None,
        priority: PriorityType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        List recommendations with optional filters.

        Args:
            agent_name: Filter by agent
            status: Filter by status
            priority: Filter by priority
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of recommendations
        """
        return RecommendationsDB.list(
            agent_name=agent_name,
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def count_pending() -> int:
        """Count pending recommendations."""
        return RecommendationsDB.count_pending()

    @staticmethod
    def delete(recommendation_id: int) -> bool:
        """Delete a recommendation."""
        return RecommendationsDB.delete(recommendation_id)

    @staticmethod
    def get_urgent() -> list[dict]:
        """Get all urgent recommendations."""
        return RecommendationsDB.list(priority="urgent", status="pending")

    @staticmethod
    def get_stats() -> dict:
        """
        Get recommendation statistics.

        Returns:
            Dict with counts by status and priority
        """
        pending = RecommendationsDB.list(status="pending", limit=1000)

        by_priority = {"low": 0, "normal": 0, "high": 0, "urgent": 0}
        by_agent: dict[str, int] = {}

        for rec in pending:
            priority = rec.get("priority", "normal")
            by_priority[priority] = by_priority.get(priority, 0) + 1

            agent = rec.get("agent_name", "unknown")
            by_agent[agent] = by_agent.get(agent, 0) + 1

        return {
            "total_pending": len(pending),
            "by_priority": by_priority,
            "by_agent": by_agent,
        }
