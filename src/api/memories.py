"""Memory API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.agent import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memories", tags=["memories"])

# Default user ID for single-user mode (no auth)
DEFAULT_USER_ID = "default"

# Dependency to get orchestrator instance
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _orchestrator


def set_orchestrator(orchestrator: AgentOrchestrator) -> None:
    """Set the global orchestrator instance."""
    global _orchestrator
    _orchestrator = orchestrator


# Response models
class MemoryResponse(BaseModel):
    id: str
    memory: str
    created_at: str | None = None
    updated_at: str | None = None


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """List all memories."""
    memories = orchestrator.get_user_memories(user_id=DEFAULT_USER_ID)
    return [
        {
            "id": m.get("id", ""),
            "memory": m.get("memory", ""),
            "created_at": m.get("created_at"),
            "updated_at": m.get("updated_at"),
        }
        for m in memories
    ]


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Delete a specific memory."""
    try:
        orchestrator.memory.delete(memory_id=memory_id)
        return None
    except Exception as e:
        logger.error(f"Error deleting memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("", status_code=204)
async def clear_all_memories(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Clear all memories."""
    try:
        orchestrator.clear_user_memories(user_id=DEFAULT_USER_ID)
        return None
    except Exception as e:
        logger.error(f"Error clearing memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
