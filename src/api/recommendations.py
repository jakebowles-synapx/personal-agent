"""Recommendations API endpoints."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from src.recommendations.store import RecommendationStore, PRIORITY_LEVELS, STATUS_VALUES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


# Request/Response models
class RecommendationResponse(BaseModel):
    id: int
    agent_name: str
    title: str
    content: str
    priority: str
    status: str
    created_at: str
    viewed_at: str | None
    acted_at: str | None
    metadata: dict | None


class RecommendationUpdate(BaseModel):
    status: Literal["pending", "viewed", "actioned", "dismissed"]


class RecommendationStats(BaseModel):
    total_pending: int
    by_priority: dict[str, int]
    by_agent: dict[str, int]


# Endpoints
@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(
    agent_name: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List recommendations with optional filters."""
    if status and status not in STATUS_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {STATUS_VALUES}"
        )

    if priority and priority not in PRIORITY_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority. Must be one of: {PRIORITY_LEVELS}"
        )

    return RecommendationStore.list_all(
        agent_name=agent_name,
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@router.get("/pending", response_model=list[RecommendationResponse])
async def list_pending(limit: int = Query(default=50, le=200)):
    """List pending recommendations."""
    return RecommendationStore.list_pending(limit=limit)


@router.get("/urgent", response_model=list[RecommendationResponse])
async def list_urgent():
    """List urgent pending recommendations."""
    return RecommendationStore.get_urgent()


@router.get("/stats", response_model=RecommendationStats)
async def get_stats():
    """Get recommendation statistics."""
    return RecommendationStore.get_stats()


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(recommendation_id: int):
    """Get a specific recommendation."""
    rec = RecommendationStore.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.patch("/{recommendation_id}", response_model=RecommendationResponse)
async def update_recommendation(
    recommendation_id: int,
    body: RecommendationUpdate,
):
    """Update recommendation status."""
    success = RecommendationStore.update_status(recommendation_id, body.status)
    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return RecommendationStore.get(recommendation_id)


@router.post("/{recommendation_id}/view", response_model=RecommendationResponse)
async def mark_viewed(recommendation_id: int):
    """Mark a recommendation as viewed."""
    success = RecommendationStore.mark_viewed(recommendation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return RecommendationStore.get(recommendation_id)


@router.post("/{recommendation_id}/action", response_model=RecommendationResponse)
async def mark_actioned(recommendation_id: int):
    """Mark a recommendation as actioned."""
    success = RecommendationStore.mark_actioned(recommendation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return RecommendationStore.get(recommendation_id)


@router.post("/{recommendation_id}/dismiss", response_model=RecommendationResponse)
async def dismiss_recommendation(recommendation_id: int):
    """Dismiss a recommendation."""
    success = RecommendationStore.dismiss(recommendation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return RecommendationStore.get(recommendation_id)


@router.delete("/{recommendation_id}", status_code=204)
async def delete_recommendation(recommendation_id: int):
    """Delete a recommendation."""
    success = RecommendationStore.delete(recommendation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return None


# Knowledge approval dependency
_knowledge_manager = None


def set_knowledge_manager_for_recommendations(manager) -> None:
    """Set the knowledge manager for recommendations API."""
    global _knowledge_manager
    _knowledge_manager = manager


class KnowledgeApprovalResponse(BaseModel):
    success: bool
    knowledge_id: int | None = None
    message: str


@router.post("/{recommendation_id}/approve-knowledge", response_model=KnowledgeApprovalResponse)
async def approve_knowledge_proposal(recommendation_id: int):
    """
    Approve a knowledge proposal recommendation.

    This takes a recommendation with type='knowledge_proposal' in its metadata,
    extracts the proposed knowledge, adds it to the knowledge base, and marks
    the recommendation as actioned.
    """
    if _knowledge_manager is None:
        raise HTTPException(status_code=503, detail="Knowledge manager not initialized")

    # Get the recommendation
    rec = RecommendationStore.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    # Check if it's a knowledge proposal
    metadata = rec.get("metadata", {})
    if metadata.get("type") != "knowledge_proposal":
        raise HTTPException(
            status_code=400,
            detail="This recommendation is not a knowledge proposal"
        )

    # Extract proposed knowledge
    category = metadata.get("proposed_category")
    title = metadata.get("proposed_title")
    content = metadata.get("proposed_content")

    if not all([category, title, content]):
        raise HTTPException(
            status_code=400,
            detail="Invalid knowledge proposal - missing required fields"
        )

    try:
        # Add to knowledge base
        knowledge_id = await _knowledge_manager.add(
            category=category,
            title=title,
            content=content,
            source="agent_proposal",
        )

        # Mark recommendation as actioned
        RecommendationStore.mark_actioned(recommendation_id)

        logger.info(f"Approved knowledge proposal {recommendation_id} -> knowledge {knowledge_id}")

        return {
            "success": True,
            "knowledge_id": knowledge_id,
            "message": f"Knowledge '{title}' added to {category} category",
        }

    except Exception as e:
        logger.error(f"Failed to approve knowledge proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
