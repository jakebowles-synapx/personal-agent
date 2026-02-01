"""Microsoft 365 connection API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.agent import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/microsoft", tags=["microsoft"])

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
class StatusResponse(BaseModel):
    connected: bool


class AuthUrlResponse(BaseModel):
    url: str


@router.get("/status", response_model=StatusResponse)
async def get_status(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Get Microsoft 365 connection status."""
    connected = orchestrator.is_microsoft_connected(user_id=DEFAULT_USER_ID)
    return {"connected": connected}


@router.get("/auth-url", response_model=AuthUrlResponse)
async def get_auth_url(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Get the Microsoft OAuth authorization URL."""
    url = orchestrator.get_microsoft_auth_url(user_id=DEFAULT_USER_ID)
    return {"url": url}


@router.post("/disconnect", status_code=204)
async def disconnect(
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
):
    """Disconnect Microsoft 365 account."""
    orchestrator.disconnect_microsoft(user_id=DEFAULT_USER_ID)
    return None
